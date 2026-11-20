// Her medicines for the doctor's report (Foivos, Nov 18): free text + an optional class, stored ON THIS PHONE ONLY
// (Application Support/medicines.json), never sent to the band or anywhere else. The heat-risk classes are the ones the
// research report names (diuretics, beta-blockers, anticholinergics, antipsychotics, SGLT2 inhibitors); the report only
// says "ask your doctor whether this matters in heat" — never advice to change a medicine.
// (Separate from the band's PROFILE medicine bits in Settings › Medicines, which tune the band's own rules.)

import Foundation

enum MedClass: String, Codable, CaseIterable, Identifiable {
    case diuretic, betaBlocker, anticholinergic, antipsychotic, sglt2, other
    var id: String { rawValue }
    /// One of the classes known to matter in heat (research report, "What the product must not claim or do").
    var heatRisk: Bool { self != .other }
}

struct Medication: Codable, Equatable, Identifiable {
    var id = UUID()
    var name: String
    /// Chosen in Settings; nil = not chosen (the report may show a guessed class, marked as a guess).
    var cls: MedClass?
}

enum MedGuess {
    /// A small list of common generic names (lower case, Latin and Greek spelling) -> class. Only a hint: the report
    /// marks it "guessed from the name — please check"; the class she or the family pick always wins.
    static let names: [(MedClass, [String])] = [
        (.diuretic, ["furosemide", "φουροσεμίδη", "lasix", "hydrochlorothiazide", "υδροχλωροθειαζίδη", "chlorthalidone", "indapamide",
                     "ινδαπαμίδη", "torasemide", "torsemide", "spironolactone", "σπιρονολακτόνη", "bumetanide", "amiloride", "eplerenone"]),
        (.betaBlocker, ["metoprolol", "μετοπρολόλη", "bisoprolol", "βισοπρολόλη", "atenolol", "ατενολόλη", "carvedilol", "καρβεδιλόλη",
                        "nebivolol", "νεμπιβολόλη", "propranolol", "προπρανολόλη", "sotalol"]),
        (.anticholinergic, ["oxybutynin", "οξυβουτυνίνη", "tolterodine", "solifenacin", "σολιφενακίνη", "trospium", "amitriptyline",
                            "αμιτριπτυλίνη", "biperiden", "hyoscine", "scopolamine", "diphenhydramine", "hydroxyzine", "υδροξυζίνη"]),
        (.antipsychotic, ["quetiapine", "κουετιαπίνη", "olanzapine", "ολανζαπίνη", "risperidone", "ρισπεριδόνη", "haloperidol",
                          "αλοπεριδόλη", "aripiprazole", "αριπιπραζόλη", "clozapine", "κλοζαπίνη"]),
        (.sglt2, ["empagliflozin", "εμπαγλιφλοζίνη", "jardiance", "dapagliflozin", "δαπαγλιφλοζίνη", "forxiga", "canagliflozin",
                  "ertugliflozin", "sotagliflozin", "synjardy", "xigduo"]),
    ]

    static func guess(_ name: String) -> MedClass? {
        let n = name.lowercased().folding(options: [.diacriticInsensitive], locale: Locale(identifier: "el_GR"))
        for (c, ks) in names where ks.contains(where: { n.contains($0.folding(options: [.diacriticInsensitive], locale: Locale(identifier: "el_GR"))) }) {
            return c
        }
        return nil
    }
}

/// On-device list (JSON in Application Support). `fileName` nil = in memory (tests, demo).
final class MedStore {
    private(set) var meds: [Medication] = []
    private let url: URL?

    init(fileName: String? = "medicines.json") {
        if let f = fileName {
            url = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent(f)
            if let u = url, let d = try? Data(contentsOf: u), let m = try? JSONDecoder().decode([Medication].self, from: d) { meds = m }
        } else {
            url = nil
        }
    }

    func set(_ m: [Medication]) {
        meds = m.filter { !$0.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || $0.cls != nil }
        save()
    }

    func save() {
        guard let u = url else { return }
        try? FileManager.default.createDirectory(at: u.deletingLastPathComponent(), withIntermediateDirectories: true)
        // complete file protection: unreadable while the phone is locked
        if let d = try? JSONEncoder().encode(meds) { try? d.write(to: u, options: [.atomic, .completeFileProtection]) }
    }
}
