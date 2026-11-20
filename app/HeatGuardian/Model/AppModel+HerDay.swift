// Her Day in AppModel (HERDAY_SPEC.md §6): the phone that holds her routine (her own phone in Elder mode, or the
// demo) computes the plan and sends DAY_PLAN — tomorrow's every evening (>= 18:00), today's at the first connection
// of the day — and forwards her visits as VISIT frames (queued while the band is away). The family phone only reads
// the band's PLAN_ITEM / VISIT events (BandHerDay). Demo: everything is logged as SIMULATION and the events the band
// would echo go into the demo log through the same decoder.

import Foundation

extension AppModel {
    static let eveningSendMinute = HerDay.eveningSendMinute

    // MARK: inputs

    /// "Now" for Her Day: the demo clock while a demo runs.
    var herDayNow: Date { isDemo ? (currentAt ?? Date()) : now }

    /// The events Her Day reads (demo log while a demo runs).
    var herEntries: [LogEntry] { activeStore.entries }

    /// This phone computes and sends the plan: the demo, or her phone with learned visits.
    var holdsRoutine: Bool { isDemo || (AppMode.current == .elder && !visits.visits.isEmpty) }

    /// The visits her routine is learned from: her phone's own store when it has one, else the band's VISIT events.
    func herVisitSamples(now: Date) -> [VisitSample] {
        if !isDemo && AppMode.current == .elder && !visits.visits.isEmpty { return visits.samples(now: now) }
        return BandHerDay.samples(herEntries)
    }

    var herBed: Int { isDemo ? HerDayDemo.bed : routine.bedOrDefault }

    /// The forecast for today (0) / tomorrow (1): the demo's constructed heat-wave days, else the loaded plan when
    /// its date is that day.
    func herDayPlan(_ offset: Int, now: Date) -> Plan? {
        guard let d = Calendar.current.date(byAdding: .day, value: offset, to: now) else { return nil }
        if isDemo {
            let wave = offset == 1 && demoHotterTomorrow ? 3 : offset + 1
            return Indoor.adjust(HerDayDemo.plan(date: d, waveDay: wave), to: routine.homeClass)
        }
        guard let p = herPlan, p.date == AppModel.dayString(d), p.hours.count == 24 else { return nil }
        return p
    }

    /// The engine's result for today (0) / tomorrow (1), from the routine this phone can see.
    func herDay(_ offset: Int, now: Date) -> HerDayResult? {
        guard let p = herDayPlan(offset, now: now),
              let d = Calendar.current.date(byAdding: .day, value: offset, to: now) else { return nil }
        let outs = RoutineModel.outings(herVisitSamples(now: now), on: d, now: now)
        return HerDay.compute(plan: p, outings: outs, bed: herBed, day: offset)
    }

    /// The family's Her Day timeline for today (0) / tomorrow (1).
    func herDayDisplay(_ offset: Int) -> HerDayDisplay? {
        let t = herDayNow
        return HerDayDisplay.make(L: L, offset: offset, now: t, plan: herDayPlan(offset, now: t), local: herDay(offset, now: t),
                                  entries: herEntries, simulated: isDemo)
    }

    // MARK: wiring

    func wireHerDay() {
        visitMonitor.onVisit = { [weak self] lat, lon, a, d in self?.onVisit(lat: lat, lon: lon, arrive: a, leave: d) }
        visitMonitor.onAuth = { [weak self] a in self?.locationAuth = a }
        visitMonitor.onHere = { [weak self] lat, lon in
            guard let self = self else { return }
            self.visits.setHome(lat: lat, lon: lon)
            self.visits.save()
            self.homeSetResult = self.L.hdHomeSet
            self.herDayChanged()
        }
        visitMonitor.onHereFailed = { [weak self] in self?.homeSetResult = self?.L.hdHomeFailed }
        updateLocation()
    }

    /// Visits monitoring runs only in Elder mode with the switch on.
    func updateLocation() {
        if AppMode.current == .elder && locationOn { visitMonitor.start() } else { visitMonitor.stop() }
        locationAuth = visitMonitor.auth
    }

    func herDayChanged() { herDayVersion += 1 }

    /// Every 30 s: the evening / first-of-day DAY_PLAN check (live band).
    func herDayTick() {
        guard !isDemo else { return }
        sendDayPlansIfNeeded()
    }

    // MARK: her visits (Elder mode)

    func onVisit(lat: Double, lon: Double, arrive: Date?, leave: Date?) {
        guard AppMode.current == .elder, locationOn else { return }
        let (p, isNew) = visits.record(lat: lat, lon: lon, arrive: arrive, leave: leave)
        visits.save()
        herDayChanged()
        if isNew || !p.typed {
            // type the place first (once), then send: the band should hear «αγορά», not «έξοδο»
            VisitMonitor.lookupType(lat: p.lat, lon: p.lon) { [weak self] t, name in
                guard let self = self else { return }
                self.visits.setType(p.id, t, name: name, byUser: false)
                self.visits.save()
                self.herDayChanged()
                self.flushVisits()
            }
        } else {
            flushVisits()
        }
    }

    /// Sends the queued VISIT frames to a connected band.
    func flushVisits() {
        guard !isDemo, link.isConnected, AppMode.current == .elder else { return }
        let fr = visits.pendingFrames()
        guard !fr.isEmpty else { return }
        for (p, b) in fr { link.send(b, label: p.edge == .arrive ? "VISIT ARRIVE" : "VISIT LEAVE") }
        visits.markSent(fr.map { $0.0 })
        visits.save()
    }

    func setHomeHere() {
        homeSetResult = nil
        visitMonitor.requestHere()
    }

    func setPlaceType(_ id: String, _ t: PlaceType) {
        visits.setType(id, t, byUser: true)
        visits.save()
        herDayChanged()
    }

    func removePlace(_ id: String) {
        visits.remove(id)
        visits.save()
        herDayChanged()
    }

    func clearPlaces() {
        visits.clearAll()
        visits.save()
        herDayChanged()
    }

    // MARK: DAY_PLAN

    /// Today's plan (once per day and whenever it changes) and, from 18:00, tomorrow's. Live: only with a connected
    /// band and only on the phone that holds her routine. Each day's set goes as index 1..n (or one "clear" frame).
    func sendDayPlansIfNeeded(now: Date? = nil) {
        guard holdsRoutine, isDemo || link.isConnected else { return }
        let t = now ?? herDayNow
        for offset in [0, 1] {
            if offset == 1 && t.minuteOfDay < AppModel.eveningSendMinute { continue }
            guard let r = herDay(offset, now: t), let frames = try? Frames.dayPlanFrames(r.items, day: offset) else { continue }
            let key = "hg.dayplan." + r.date
            let sig = frames.map(Frames.toHex).joined(separator: ",")
            if isDemo {
                guard demoHerDayFired.insert(key + "|" + sig).inserted else { continue }
                for (i, f) in frames.enumerated() { logWrite("DAY_PLAN \(offset == 0 ? "today" : "tomorrow") \(i + 1)/\(frames.count)", Frames.toHex(f), simulated: true) }
                echoDemoPlan(r.items, day: offset, at: t)
            } else {
                let ud = UserDefaults.standard
                if ud.string(forKey: key) == sig {
                    // Sent before. The band commits a day only when all n items arrived and then echoes them as
                    // PLAN_ITEM: no echo 3 min after the send (a disconnect mid-way) -> send the set again.
                    let echoed = r.items.isEmpty || !BandHerDay.planItems(herEntries, for: Calendar.current.date(byAdding: .day, value: offset, to: t) ?? t).items.isEmpty
                    let at = ud.object(forKey: key + ".at") as? Date ?? .distantPast
                    if echoed || t.timeIntervalSince(at) < 180 { continue }
                }
                for (i, f) in frames.enumerated() { link.send(f, label: "DAY_PLAN \(offset) \(i + 1)/\(frames.count)") }
                ud.set(sig, forKey: key)
                ud.set(t, forKey: key + ".at")
            }
        }
    }

    // MARK: demo (ΠΡΟΣΟΜΟΙΩΣΗ)

    /// Demo controls: tomorrow becomes heat-wave day 3 (hot from 08:00) so a "go after" suggestion shows too.
    func setDemoHotterTomorrow(_ on: Bool) {
        guard isDemo, demoHotterTomorrow != on else { return }
        demoHotterTomorrow = on
        herDayChanged()
        if let t = currentAt { sendDayPlansIfNeeded(now: t) }
    }

    /// A demo band event through the real encoder + decoder, into the demo log.
    private func addDemoBandEvent(_ ev: BandEvent, at: Date) {
        guard let back = try? Frames.decodeEvent(Frames.encodeEvent(ev)),
              let e = LogEntry.fromBand(back, receivedAt: at, simulated: true) else { return }
        demoStore.add(e)
    }

    private func demoVisitEvent(_ edge: VisitEdge, _ p: PlaceType, _ t: Date) {
        demoSeq += 1
        let u = UInt32(max(0, t.timeIntervalSince1970))
        addDemoBandEvent(Frames.visitEvent(seq: demoSeq, boot: 0, unix: u, VisitEvent(edge: edge, place: p, unix: u)), at: t)
    }

    /// The band's PLAN_ITEM echo of a plan the demo "sent".
    private func echoDemoPlan(_ items: [DayPlanItem], day: Int, at: Date) {
        for it in items {
            demoSeq += 1
            addDemoBandEvent(Frames.planItemEvent(seq: demoSeq, boot: 0, unix: UInt32(max(0, at.timeIntervalSince1970)), it), at: at)
        }
    }

    /// Two weeks of her scripted visits as the band's VISIT events (the family phone learns her routine from them).
    func seedHerDayDemo() {
        guard isDemo else { return }
        for v in HerDayDemo.pastVisits(today: Date()) {
            demoVisitEvent(.arrive, v.place, v.arrive)
            if let l = v.leave { demoVisitEvent(.leave, v.place, l) }
        }
    }

    /// Called for every demo minute: today's scripted visits as the clock passes them, today's plan at the start,
    /// tomorrow's from 18:00, and the band's EVENING_BRIEF (nudge 7) at bedtime - 60. Returns true when it added.
    func synthHerDayDemo(at: Date) -> Bool {
        guard isDemo else { return false }
        let before = demoStore.entries.count
        let d0 = Calendar.current.startOfDay(for: at)
        let m = at.minuteOfDay
        for (start, p, dur) in HerDayDemo.todayScript {
            if m >= start && demoHerDayFired.insert("a\(start)").inserted {
                demoVisitEvent(.leave, .home, d0.addingTimeInterval(Double((start - 8) * 60)))
                demoVisitEvent(.arrive, p, d0.addingTimeInterval(Double(start * 60)))
            }
            if m >= start + dur && demoHerDayFired.insert("l\(start)").inserted {
                demoVisitEvent(.leave, p, d0.addingTimeInterval(Double((start + dur) * 60)))
                demoVisitEvent(.arrive, .home, d0.addingTimeInterval(Double((start + dur + 8) * 60)))
            }
        }
        // the engine runs on the first demo minute and then every 15 demo minutes (the evening send at 18:00 included)
        if m % 15 == 0 || demoHerDayFired.insert("p").inserted { sendDayPlansIfNeeded(now: at) }
        let briefAt = HerDayDemo.bed - 60
        if m >= briefAt, demoHerDayFired.insert("n7").inserted,
           let r = herDay(1, now: at), r.items.contains(where: { $0.kind != .airOpen }) {
            demoSeq += 1
            addDemoBandEvent(BandEvent(seq: demoSeq, boot: 0, unix: UInt32(max(0, d0.addingTimeInterval(Double(briefAt * 60)).timeIntervalSince1970)),
                                       kindRaw: BandEvent.Kind.nudgeShown.rawValue, arg: NudgeID.eveningBrief.rawValue), at: at)
        }
        return demoStore.entries.count != before
    }
}
