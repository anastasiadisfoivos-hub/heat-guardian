// THE TOWER (owner decision Nov 19): her phone turns band alerts into SMS to 1-3 family contacts.
// This file: the family contacts, the owner settings, and the SMS texts — short, Greek by default (English option),
// always with the reason and the time (an SMS can arrive late). Pure Foundation (tested on Linux, TowerTests).

import Foundation

/// One family contact (Setup + Settings). Only on this phone. Email is optional (the report goes by email).
struct FamilyContact: Codable, Equatable, Identifiable {
    var id: String = UUID().uuidString
    var name: String
    var phone: String
    var email: String = ""

    /// E.164 number for Twilio ("+306912345678"), nil when it does not look like a phone number.
    func e164(defaultCountryCode cc: String = TowerPrefs.defaultCountryCode) -> String? {
        PhoneNumber.e164(phone, defaultCountryCode: cc)
    }
    var hasEmail: Bool { PhoneNumber.looksLikeEmail(email) }
}

enum PhoneNumber {
    /// "+30 691 234 5678" -> "+306912345678"; "00306912345678" -> "+306912345678"; "6912345678" + cc "30" ->
    /// "+306912345678" (a leading national 0 is dropped: "0612…" + cc "44" -> "+44612…"). nil: not 7-15 digits.
    static func e164(_ raw: String, defaultCountryCode cc: String) -> String? {
        let t = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty, t.allSatisfy({ "+0123456789 -().".contains($0) }) else { return nil }
        var digits = t.filter { $0.isNumber }
        let plus = t.hasPrefix("+")
        if !plus && digits.hasPrefix("00") { digits.removeFirst(2) }
        else if !plus {
            let c = cc.filter { $0.isNumber }
            if digits.hasPrefix("0") { digits.removeFirst() }
            digits = c + digits
        }
        guard (8...15).contains(digits.count), digits.first != "0" else { return nil }
        return "+" + digits
    }
    static func looksLikeEmail(_ s: String) -> Bool {
        let t = s.trimmingCharacters(in: .whitespaces)
        guard let at = t.firstIndex(of: "@"), !t.contains(" ") else { return false }
        let host = t[t.index(after: at)...]
        return at > t.startIndex && host.contains(".") && !host.hasSuffix(".")
    }
    /// "+306912345678" -> "+30 •••• 5678" (outbox and logs never show a full number to a passer-by).
    static func masked(_ e164: String) -> String {
        let d = e164.filter { $0.isNumber }
        guard d.count > 6 else { return e164 }
        return "+" + d.prefix(2) + " •••• " + d.suffix(4)
    }
}

/// The owner's Tower settings (UserDefaults, no secrets: the Twilio credentials live in the Keychain).
struct TowerPrefs: Codable, Equatable {
    static let defaultCountryCode = "30"
    /// "Water didn't help" / "no response" quiet notes by SMS (owner default: on).
    var notesBySMS = true
    /// Band disconnected: in-app only by default; on = an SMS after `disconnectMinutes`.
    var disconnectSMS = false
    var disconnectMinutes = 60
    /// Language of the SMS texts (Greek by default, English option) — independent of the screen language.
    var smsLang: Lang = .el
    /// Country code added to numbers typed without one.
    var countryCode = TowerPrefs.defaultCountryCode
    /// «Αποστολή SMS και στην προσομοίωση» (owner, Nov 20; default off): SIMULATION events (the app's demo, the band's
    /// `replay noresp`) may send real SMS when Twilio is set; their text then ends with « (δοκιμή)» / « (test)».
    var smsInSimulation = false
    /// [SMS-SHORTCUT] Who sends: nil = automatic (Twilio when its credentials are set, else the iPhone Shortcut).
    var sender: SMSSender?
    /// The name of the owner's Shortcut (Settings › Tower), default «HG SOS».
    var shortcutName = ShortcutAPI.defaultName

    init() {}
    /// Keys missing in an older saved file keep their defaults (a new setting must never reset the others).
    init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        notesBySMS = try c.decodeIfPresent(Bool.self, forKey: .notesBySMS) ?? notesBySMS
        disconnectSMS = try c.decodeIfPresent(Bool.self, forKey: .disconnectSMS) ?? disconnectSMS
        disconnectMinutes = try c.decodeIfPresent(Int.self, forKey: .disconnectMinutes) ?? disconnectMinutes
        smsLang = try c.decodeIfPresent(Lang.self, forKey: .smsLang) ?? smsLang
        countryCode = try c.decodeIfPresent(String.self, forKey: .countryCode) ?? countryCode
        smsInSimulation = try c.decodeIfPresent(Bool.self, forKey: .smsInSimulation) ?? smsInSimulation
        sender = try c.decodeIfPresent(SMSSender.self, forKey: .sender)
        shortcutName = try c.decodeIfPresent(String.self, forKey: .shortcutName) ?? shortcutName
    }
    private enum CodingKeys: String, CodingKey {
        case notesBySMS, disconnectSMS, disconnectMinutes, smsLang, countryCode, smsInSimulation, sender, shortcutName
    }

    private static let key = "hg.tower.prefs"
    static func load(_ ud: UserDefaults = .standard) -> TowerPrefs {
        guard let d = ud.data(forKey: key), let p = try? JSONDecoder().decode(TowerPrefs.self, from: d) else { return TowerPrefs() }
        return p
    }
    func save(_ ud: UserDefaults = .standard) {
        if let d = try? JSONEncoder().encode(self) { ud.set(d, forKey: TowerPrefs.key) }
    }
}

extension Lang: Codable {}

/// What an SMS is about (the router picks it, SMSText words it).
enum SMSKind: Equatable {
    case help(at: Date)
    case helpCancelled(at: Date)
    case escalatedDanger(at: Date)
    case escalatedStillHeating(at: Date, afterWater: Bool)
    case noAnswer(at: Date)                 // a family alert from the band without a ladder event (CHECK unanswered; bands before 0.9.17)
    case waterDidNotHelp(at: Date)
    case noResponse(step: LadderStep, at: Date)
    case responsive(at: Date)
    case settled(at: Date)                  // after an escalation the forecast stopped rising
    case bandDisconnected(minutes: Int)
    case batteryEnded(at: Date)             // band 0.9.18 BATT_CRITICAL: it switched itself off
    case test
}

enum SMSText {
    /// The SMS body. `name` = her name as the family knows it («Μαρία»); empty -> «Η μητέρα σας»-free neutral wording.
    static func body(_ k: SMSKind, name rawName: String, lang: Lang, timeZone: TimeZone = .current) -> String {
        let el = lang == .el
        let name = rawName.trimmingCharacters(in: .whitespacesAndNewlines)
        let who = name.isEmpty ? (el ? "Heat Guardian" : "Heat Guardian") : name
        func hm(_ d: Date) -> String {
            var c = Calendar(identifier: .gregorian); c.timeZone = timeZone
            let x = c.dateComponents([.hour, .minute], from: d)
            return String(format: "%02d:%02d", x.hour ?? 0, x.minute ?? 0)
        }
        switch k {
        case .help(let at):
            return el ? "\(who): ΖΗΤΗΣΕ ΒΟΗΘΕΙΑ από το βραχιόλι στις \(hm(at)). Τηλεφωνήστε της τώρα."
                      : "\(who): ASKED FOR HELP on the band at \(hm(at)). Call her now."
        case .helpCancelled(let at):
            return el ? "\(who): ακύρωσε τη βοήθεια στις \(hm(at)). Ένα τηλεφώνημα θα την ησυχάσει."
                      : "\(who): cancelled the help call at \(hm(at)). A call will reassure her."
        case .escalatedDanger(let at):
            return el ? "\(who): ΚΙΝΔΥΝΟΣ από τη ζέστη στις \(hm(at)). Το σώμα της ζεσταίνεται πολύ. Τηλεφωνήστε της τώρα."
                      : "\(who): HEAT DANGER at \(hm(at)). Her body is getting very hot. Call her now."
        case .escalatedStillHeating(let at, let afterWater):
            if afterWater {
                return el ? "\(who): το νερό δεν βοήθησε, πήγε σε πιο δροσερό μέρος. Συνεχίζει να ζεσταίνεται (\(hm(at))). Τηλεφωνήστε της τώρα."
                          : "\(who): water did not help, she moved somewhere cooler. She is still heating up (\(hm(at))). Call her now."
            }
            return el ? "\(who): πήγε σε πιο δροσερό μέρος αλλά συνεχίζει να ζεσταίνεται (\(hm(at))). Τηλεφωνήστε της τώρα."
                      : "\(who): she moved somewhere cooler but is still heating up (\(hm(at))). Call her now."
        case .noAnswer(let at):
            return el ? "\(who): δεν απάντησε στο βραχιόλι στις \(hm(at)) ενώ κάνει ζέστη. Τηλεφωνήστε της τώρα."
                      : "\(who): did not answer the band at \(hm(at)) in the heat. Call her now."
        case .waterDidNotHelp(let at):
            return el ? "\(who): το νερό δεν βοήθησε (\(hm(at))). Το βραχιόλι της είπε να πάει σε πιο δροσερό μέρος."
                      : "\(who): water did not help (\(hm(at))). The band told her to move somewhere cooler."
        case .noResponse(let step, let at):
            let what = step == .coolerPlace ? (el ? "να πάει σε πιο δροσερό μέρος" : "to move somewhere cooler")
                                            : (el ? "να πιει νερό" : "to drink water")
            return el ? "\(who): δεν απάντησε στην υπενθύμιση \(what) (\(hm(at))). Ίσως ένα τηλεφώνημα."
                      : "\(who): did not respond to the reminder \(what) (\(hm(at))). Maybe give her a call."
        case .responsive(let at):
            return el ? "\(who): πάτησε το κουμπί στις \(hm(at)), σας βλέπει. Η ζέστη συνεχίζεται: η ειδοποίηση μένει."
                      : "\(who): pressed the button at \(hm(at)), she is responsive. The heat continues: the alert stays."
        case .settled(let at):
            return el ? "\(who): σταμάτησε να ζεσταίνεται (\(hm(at))). Μείνετε σε επαφή μαζί της."
                      : "\(who): she has stopped heating up (\(hm(at))). Stay in touch with her."
        case .bandDisconnected(let minutes):
            return el ? "\(who): το βραχιόλι δεν συνδέεται με το κινητό της εδώ και \(minutes) λεπτά. Ειδοποιήσεις δεν φτάνουν."
                      : "\(who): the band has not reached her phone for \(minutes) min. Alerts cannot get through."
        case .batteryEnded(let at):
            return el ? "\(who): η μπαταρία του βραχιολιού τελείωσε (\(hm(at))). Δεν προστατεύεται μέχρι να φορτιστεί."
                      : "\(who): the band's battery ran out (\(hm(at))). She is not protected until it is charged."
        case .test:
            return el ? "Heat Guardian: δοκιμαστικό μήνυμα για \(name.isEmpty ? "το βραχιόλι" : name). Οι ειδοποιήσεις λειτουργούν."
                      : "Heat Guardian: test message for \(name.isEmpty ? "the band" : name). Alerts are working."
        }
    }

    /// The honest end of a SIMULATION SMS (sent only with «Αποστολή SMS και στην προσομοίωση» on).
    static func simulationMarker(_ lang: Lang) -> String { lang == .el ? " (δοκιμή)" : " (test)" }

    /// SMS segments: GSM-7 (160 / 153 per part) when every character is in the GSM basic set, else UCS-2 (70 / 67).
    /// Greek lower-case is not in GSM-7, so a Greek SMS is UCS-2: the texts above aim at 2 parts at most.
    static func segments(_ body: String) -> (ucs2: Bool, count: Int) {
        let ucs2 = !body.allSatisfy { gsm7.contains($0) }
        let units = ucs2 ? body.utf16.count : body.count
        let single = ucs2 ? 70 : 160, part = ucs2 ? 67 : 153
        return (ucs2, units <= single ? 1 : (units + part - 1) / part)
    }
    private static let gsm7: Set<Character> = Set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")
}
