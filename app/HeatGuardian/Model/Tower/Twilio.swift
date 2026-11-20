// THE TOWER's SMS transport: the Twilio REST API (POST /2010-04-01/Accounts/{SID}/Messages.json, HTTP Basic auth
// SID:token, form body To / From / Body), plus DRY-RUN. The request is built by a pure function (tested with a fake
// HTTP client, no network in tests). Credentials come from the Keychain (TowerKeychain.swift): never hard-coded,
// never logged (descriptions are redacted), never committed.

import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

struct TwilioCredentials: Codable, Equatable, CustomStringConvertible {
    var accountSID: String
    var authToken: String
    var fromNumber: String          // E.164 Twilio number, or an alphanumeric sender ID where the country allows it

    var trimmed: TwilioCredentials {
        TwilioCredentials(accountSID: accountSID.trimmingCharacters(in: .whitespacesAndNewlines),
                          authToken: authToken.trimmingCharacters(in: .whitespacesAndNewlines),
                          fromNumber: fromNumber.trimmingCharacters(in: .whitespacesAndNewlines))
    }
    /// Account SIDs are "AC" + 32 hex characters; tokens 32 characters; From must be set.
    var problems: [String] {
        let c = trimmed
        var out: [String] = []
        if !(c.accountSID.hasPrefix("AC") && c.accountSID.count == 34 && c.accountSID.dropFirst(2).allSatisfy { $0.isHexDigit }) {
            out.append("sid")
        }
        if c.authToken.count < 32 || c.authToken.contains(" ") { out.append("token") }
        if c.fromNumber.isEmpty { out.append("from") }
        return out
    }
    var isComplete: Bool { problems.isEmpty }
    /// Redacted: "AC…1a2b, token ••••, from +1 •••• 0000". The token never appears in any description or log.
    var description: String {
        "TwilioCredentials(\(accountSID.prefix(2))…\(accountSID.suffix(4)), token ••••, from \(PhoneNumber.masked(fromNumber)))"
    }
}

/// Anything that turns (to, body) into a SendResult. Completion may come on any thread.
protocol SMSTransport: AnyObject {
    var isDryRun: Bool { get }
    func send(to: String, body: String, completion: @escaping (SendResult) -> Void)
}

/// One HTTP round trip (URLSession in the app, a fake in tests).
protocol HTTPClient: AnyObject {
    func perform(_ request: URLRequest, completion: @escaping (_ status: Int?, _ data: Data?, _ error: Error?) -> Void)
}

enum TwilioAPI {
    static let host = "https://api.twilio.com"

    static func messagesURL(accountSID: String) -> URL? {
        let sid = accountSID.addingPercentEncoding(withAllowedCharacters: formSafe) ?? ""
        return URL(string: "\(host)/2010-04-01/Accounts/\(sid)/Messages.json")
    }

    /// application/x-www-form-urlencoded, every byte outside A-Z a-z 0-9 - . _ ~ percent-encoded (UTF-8; "+" -> %2B,
    /// space -> %20), in the given order.
    static func formBody(_ fields: [(String, String)]) -> String {
        fields.map { k, v in
            (k.addingPercentEncoding(withAllowedCharacters: formSafe) ?? "") + "=" + (v.addingPercentEncoding(withAllowedCharacters: formSafe) ?? "")
        }.joined(separator: "&")
    }
    static let formSafe: CharacterSet = {
        var c = CharacterSet()
        c.insert(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
        return c
    }()

    static func basicAuth(sid: String, token: String) -> String {
        "Basic " + Data("\(sid):\(token)".utf8).base64EncodedString()
    }

    /// The POST for one SMS. nil only if the SID cannot make a URL.
    static func request(_ raw: TwilioCredentials, to: String, body: String) -> URLRequest? {
        let c = raw.trimmed
        guard let url = messagesURL(accountSID: c.accountSID) else { return nil }
        var r = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
        r.httpMethod = "POST"
        r.setValue("application/x-www-form-urlencoded; charset=utf-8", forHTTPHeaderField: "Content-Type")
        r.setValue("application/json", forHTTPHeaderField: "Accept")
        r.setValue(basicAuth(sid: c.accountSID, token: c.authToken), forHTTPHeaderField: "Authorization")
        r.httpBody = Data(formBody([("To", to), ("From", c.fromNumber), ("Body", body)]).utf8)
        return r
    }

    /// HTTP outcome -> SendResult. 2xx sent (Twilio's message SID kept); no answer / 408 / 429 / 5xx = transient (retry
    /// with backoff); 401 / 403 = wrong credentials, other 4xx (bad number 21211, unverified trial number 21608 …) =
    /// permanent. Twilio's own message is kept for the outbox (it never contains the token).
    static func classify(status: Int?, data: Data?, error: Error?) -> SendResult {
        guard let s = status else {
            return .transient(error.map { "network: \(($0 as NSError).localizedDescription)" } ?? "network: no answer")
        }
        let json = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
        let msg = json?["message"] as? String
        let code = (json?["code"] as? NSNumber)?.intValue
        switch s {
        case 200..<300: return .sent(providerID: json?["sid"] as? String)
        case 408, 429, 500..<600: return .transient("HTTP \(s)" + (msg.map { ": " + $0 } ?? ""))
        case 401, 403: return .permanent("HTTP \(s): Twilio refused the credentials (Account SID / Auth Token)")
        default:
            return .permanent("HTTP \(s)" + (code.map { " (Twilio \($0))" } ?? "") + (msg.map { ": " + $0 } ?? ""))
        }
    }
}

final class TwilioTransport: SMSTransport {
    let isDryRun = false
    private let creds: TwilioCredentials
    private let http: HTTPClient

    init(credentials: TwilioCredentials, http: HTTPClient) {
        creds = credentials
        self.http = http
    }

    func send(to: String, body: String, completion: @escaping (SendResult) -> Void) {
        guard let r = TwilioAPI.request(creds, to: to, body: body) else {
            completion(.permanent("bad Account SID")); return
        }
        http.perform(r) { status, data, error in completion(TwilioAPI.classify(status: status, data: data, error: error)) }
    }
}

/// DRY-RUN: no credentials (or a SIMULATION event). Nothing leaves the phone; the outbox shows exactly what would go.
final class DryRunTransport: SMSTransport {
    let isDryRun = true
    func send(to: String, body: String, completion: @escaping (SendResult) -> Void) {
        completion(.sent(providerID: nil))
    }
}

/// URLSession, ephemeral (no cookies, no cache on disk).
final class URLSessionHTTP: HTTPClient {
    private let session: URLSession = {
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForRequest = 20
        return URLSession(configuration: c)
    }()

    func perform(_ request: URLRequest, completion: @escaping (Int?, Data?, Error?) -> Void) {
        session.dataTask(with: request) { data, resp, err in
            completion((resp as? HTTPURLResponse)?.statusCode, data, err)
        }.resume()
    }
}

/// Where the credentials live (the Keychain in the app, memory in tests).
protocol CredentialStore: AnyObject {
    func load() -> TwilioCredentials?
    func save(_ c: TwilioCredentials) -> Bool
    func delete()
}

final class MemoryCredentialStore: CredentialStore {
    private var c: TwilioCredentials?
    init(_ c: TwilioCredentials? = nil) { self.c = c }
    func load() -> TwilioCredentials? { c }
    func save(_ c: TwilioCredentials) -> Bool { self.c = c; return true }
    func delete() { c = nil }
}

// MARK: iPhone Shortcut sender ([SMS-SHORTCUT], Nov 20: the Twilio account is blocked)
// The SMS / iMessage goes from the owner's own iPhone through an Apple Shortcut the owner made once:
//   «Receive text input» -> «Send Message» (to the contact, chosen INSIDE the Shortcut) with «Shortcut Input»,
//   «Show When Run» off.
// The app opens shortcuts://x-callback-url/run-shortcut?name=…&input=text&text=…&x-success=…&x-error=…&x-cancel=…
// and Shortcuts comes back to heatguardian://shortcut-done/<outbox id> (or shortcut-error / shortcut-cancel), which
// marks the outbox item sent or failed. The recipient is not in the URL, so the text must stand alone (SMSText does).

/// Who carries the family SMS. Twilio (REST, needs an account) or the owner's iPhone through a Shortcut.
enum SMSSender: String, Codable, CaseIterable, Identifiable {
    case twilio, shortcut
    var id: String { rawValue }
}

enum ShortcutAPI {
    /// The app's URL scheme (Info.plist CFBundleURLTypes). No entitlement or capability is needed for it.
    static let appScheme = "heatguardian"
    static let defaultName = "HG SOS"
    /// The outbox "number" of a Shortcut item: the real recipient is picked inside the Shortcut.
    static let recipient = "shortcut"
    /// A launched Shortcut that never called back (no x-success / x-error) is failed after this long.
    static let timeout: TimeInterval = 10 * 60

    static func name(_ raw: String) -> String {
        let n = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        return n.isEmpty ? defaultName : n
    }

    /// Every byte outside A-Z a-z 0-9 - . _ ~ percent-encoded (UTF-8): Greek, spaces (%20), «+», «&», «?», «:», «/».
    static func enc(_ s: String) -> String { s.addingPercentEncoding(withAllowedCharacters: TwilioAPI.formSafe) ?? "" }

    static func callback(_ kind: String, id: String, scheme: String = appScheme) -> String { "\(scheme)://\(kind)/\(enc(id))" }

    /// The run-shortcut URL for one message. `id` = the outbox item, carried in the callback path.
    static func runURL(name: String, text: String, id: String, scheme: String = appScheme) -> URL? {
        let q = [("name", ShortcutAPI.name(name)), ("input", "text"), ("text", text),
                 ("x-success", callback("shortcut-done", id: id, scheme: scheme)),
                 ("x-error", callback("shortcut-error", id: id, scheme: scheme)),
                 ("x-cancel", callback("shortcut-cancel", id: id, scheme: scheme))]
        return URL(string: "shortcuts://x-callback-url/run-shortcut?" + q.map { enc($0.0) + "=" + enc($0.1) }.joined(separator: "&"))
    }

    /// A callback from Shortcuts -> (outbox id if present, result). nil = not a Shortcut callback.
    /// x-error carries `errorMessage=`; Shortcuts may append its own query (e.g. `result=`), which is ignored.
    static func parseCallback(_ url: URL, scheme: String = appScheme) -> (id: String?, result: SendResult)? {
        guard url.scheme?.lowercased() == scheme.lowercased(), let host = url.host?.lowercased() else { return nil }
        let comps = URLComponents(url: url, resolvingAgainstBaseURL: false)
        let rawID = (comps?.path ?? "").trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let id = rawID.isEmpty ? nil : (rawID.removingPercentEncoding ?? rawID)
        switch host {
        case "shortcut-done":
            return (id, .sent(providerID: nil))
        case "shortcut-error":
            let msg = comps?.queryItems?.first { $0.name == "errorMessage" }?.value
            return (id, .permanent("Shortcuts: " + (msg.map { $0.isEmpty ? "error" : $0 } ?? "error")))
        case "shortcut-cancel":
            return (id, .permanent("Shortcuts: cancelled"))
        default:
            return nil
        }
    }

    /// «Test the Shortcut» text.
    static func testBody(_ lang: Lang) -> String { lang == .el ? "Heat Guardian: δοκιμή αποστολής" : "Heat Guardian: sending test" }
}
