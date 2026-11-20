// THE TOWER outbox: every SMS the Tower sends (or, in DRY-RUN, would send), one item per recipient, as a pure state
// machine (no clock, no network: `now` and the send result come in from outside), persisted by TowerEngine.
//
//   enqueue ─┬─ duplicate      same dedupe key + same number inside the window (urgent 10 min, others 30 min): dropped
//            ├─ skipped        rate limit: more than 6 SMS to one number in a rolling hour (urgent: hard cap 20/h)
//            └─ queued ──(due)──> sending ──┬─ sent
//                    ^                       ├─ transient error (offline, 429, 5xx) -> queued, retry after 30 s, 60 s,
//                    └───────────────────────┘    120 s … max 15 min; after 8 attempts -> failed
//                                            └─ permanent error (bad number, wrong credentials) -> failed at once
//   a queued item older than 3 h is failed ("expired"): a help SMS that late would mislead.
//   «Retry» on a failed item -> queued again now (attempts reset). "No SMS storms" = dedupe + rate limit + backoff.

import Foundation

enum SendResult: Equatable {
    case sent(providerID: String?)
    case transient(String)
    case permanent(String)
}

struct OutboxItem: Codable, Equatable, Identifiable {
    enum Status: String, Codable { case queued, sending, sent, failed, skipped }
    var id: String
    var createdAt: Date
    var dedupeKey: String
    var priority: SMSPriority
    var to: String                     // E.164
    var contactName: String
    var body: String
    var status: Status = .queued
    var attempts = 0
    var nextAttemptAt: Date?
    var lastError: String?
    var sentAt: Date?
    var providerID: String?
    /// DRY-RUN: shown exactly as it would be sent, never sent (no credentials, or a demo / SIMULATION event).
    var dryRun: Bool
    var simulated = false
    /// nil = Twilio (items saved before the Shortcut sender existed); .shortcut = through the iPhone Shortcut.
    var sender: SMSSender?
}

struct OutboxPolicy: Equatable {
    var dedupeUrgent: TimeInterval = 10 * 60
    var dedupeOther: TimeInterval = 30 * 60
    var perNumberPerHour = 6
    var urgentHardCapPerHour = 20
    var backoffBase: TimeInterval = 30
    var backoffMax: TimeInterval = 15 * 60
    var maxAttempts = 8
    var expireAfter: TimeInterval = 3 * 3600
    var keep = 200

    func backoff(afterAttempt n: Int) -> TimeInterval {
        min(backoffMax, backoffBase * pow(2, Double(max(0, n - 1))))
    }
}

enum EnqueueResult: Equatable {
    case queued(id: String)
    case duplicate
    case skipped(id: String)      // rate limit: recorded so the owner sees it, never sent
}

struct Outbox: Codable, Equatable {
    private(set) var items: [OutboxItem] = []      // oldest first
    var policy: OutboxPolicy { OutboxPolicy() }
    private(set) var droppedDuplicates = 0

    enum CodingKeys: String, CodingKey { case items, droppedDuplicates }

    /// One SMS to one number. Dedupe + rate limit decided here.
    @discardableResult
    mutating func enqueue(body: String, to: String, contactName: String, dedupeKey: String, priority: SMSPriority,
                          dryRun: Bool, simulated: Bool = false, sender: SMSSender? = nil, now: Date,
                          policy p: OutboxPolicy = OutboxPolicy()) -> EnqueueResult {
        let window = priority == .urgent ? p.dedupeUrgent : p.dedupeOther
        if items.contains(where: { $0.to == to && $0.dedupeKey == dedupeKey && $0.status != .failed && $0.status != .skipped
                                   && $0.simulated == simulated && now.timeIntervalSince($0.createdAt) < window }) {
            droppedDuplicates += 1
            return .duplicate
        }
        let lastHour = items.filter { $0.to == to && $0.simulated == simulated && ($0.status != .skipped && $0.status != .failed)
                                      && now.timeIntervalSince($0.createdAt) < 3600 }.count
        let limit = priority == .urgent ? p.urgentHardCapPerHour : p.perNumberPerHour
        var it = OutboxItem(id: UUID().uuidString, createdAt: now, dedupeKey: dedupeKey, priority: priority, to: to,
                            contactName: contactName, body: body, nextAttemptAt: now, dryRun: dryRun, simulated: simulated,
                            sender: sender)
        if lastHour >= limit {
            it.status = .skipped
            it.nextAttemptAt = nil
            it.lastError = "rate limit: \(limit) SMS / hour to this number"
            append(it, p)
            return .skipped(id: it.id)
        }
        append(it, p)
        return .queued(id: it.id)
    }

    private mutating func append(_ it: OutboxItem, _ p: OutboxPolicy) {
        items.append(it)
        if items.count > p.keep {
            // drop the oldest finished items first; never a queued / sending one
            var excess = items.count - p.keep
            items.removeAll { x in
                guard excess > 0, [.sent, .failed, .skipped].contains(x.status) else { return false }
                excess -= 1; return true
            }
        }
    }

    /// Items to send now, most urgent first (expired ones are failed here).
    mutating func due(now: Date, policy p: OutboxPolicy = OutboxPolicy()) -> [OutboxItem] {
        for i in items.indices where items[i].status == .queued && now.timeIntervalSince(items[i].createdAt) > p.expireAfter {
            items[i].status = .failed
            items[i].lastError = "expired: not sent within \(Int(p.expireAfter / 3600)) h"
            items[i].nextAttemptAt = nil
        }
        return items.filter { $0.status == .queued && ($0.nextAttemptAt ?? now) <= now }
            .sorted { ($0.priority, $1.createdAt) > ($1.priority, $0.createdAt) }
    }

    mutating func markSending(_ id: String) {
        guard let i = items.firstIndex(where: { $0.id == id }), items[i].status == .queued else { return }
        items[i].status = .sending
        items[i].attempts += 1
    }

    mutating func complete(_ id: String, _ r: SendResult, now: Date, policy p: OutboxPolicy = OutboxPolicy()) {
        guard let i = items.firstIndex(where: { $0.id == id }), items[i].status == .sending else { return }
        switch r {
        case .sent(let pid):
            items[i].status = .sent; items[i].sentAt = now; items[i].providerID = pid
            items[i].lastError = nil; items[i].nextAttemptAt = nil
        case .permanent(let e):
            items[i].status = .failed; items[i].lastError = e; items[i].nextAttemptAt = nil
        case .transient(let e):
            items[i].lastError = e
            if items[i].attempts >= p.maxAttempts {
                items[i].status = .failed; items[i].nextAttemptAt = nil
            } else {
                items[i].status = .queued
                items[i].nextAttemptAt = now.addingTimeInterval(p.backoff(afterAttempt: items[i].attempts))
            }
        }
    }

    /// After a crash / relaunch an item may be left "sending": put it back in the queue (Twilio may then send twice;
    /// a duplicate SMS is better than a lost help SMS).
    mutating func recoverSending(now: Date) {
        for i in items.indices where items[i].status == .sending {
            items[i].status = .queued; items[i].nextAttemptAt = now
        }
    }

    /// «Retry» on a failed / skipped item, and «Retry now» on a queued one waiting for its backoff.
    mutating func retry(_ id: String, now: Date) {
        guard let i = items.firstIndex(where: { $0.id == id }), [.failed, .skipped, .queued].contains(items[i].status) else { return }
        items[i].status = .queued; items[i].attempts = 0; items[i].nextAttemptAt = now
        items[i].createdAt = max(items[i].createdAt, now.addingTimeInterval(-60))   // not expired straight away
    }

    /// A note on an item in flight (e.g. "waiting for a tap on the notification"); cleared when it completes as sent.
    mutating func note(_ id: String, _ text: String?) {
        guard let i = items.firstIndex(where: { $0.id == id }) else { return }
        items[i].lastError = text
    }

    /// The earliest time something waits for (the engine's retry timer).
    var nextWake: Date? { items.filter { $0.status == .queued }.compactMap { $0.nextAttemptAt }.min() }

    mutating func removeSimulated() { items.removeAll { $0.simulated } }
    mutating func clear() { items = []; droppedDuplicates = 0 }
}
