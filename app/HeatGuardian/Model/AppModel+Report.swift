// The doctor's report in AppModel: which data goes in (live: this phone's ledger + the band's log; demo: the
// constructed month, labelled SIMULATION), the on/off switch she controls in Elder mode, the consent, and deleting.

import Foundation

extension AppModel {
    static let reportPeriods = [7, 14, 30]

    /// May this phone make a report now? (Elder mode can turn it off; consent first.)
    var reportAllowed: Bool { reportOn }
    var reportNeedsConsent: Bool { reportConsentAt == nil }

    func acceptReportConsent() { reportConsentAt = Date() }

    /// Withdraws consent and deletes the on-phone report data (day aggregates). The band's log stays (it is the
    /// family log, not the report's).
    func deleteReportData() {
        ledger.clear()
        reportConsentAt = nil
    }

    func makeReport(days: Int, includeName: Bool, lang: Lang) -> HeatReport {
        let now = isDemo ? Calendar.current.startOfDay(for: Date()).addingTimeInterval(13 * 3600) : Date()
        let name = includeName && !wearerName.trimmingCharacters(in: .whitespaces).isEmpty ? wearerName : nil
        let inp: ReportInput
        if isDemo {
            inp = ReportInput(records: HeatReportDemo.records(days: days, today: now), entries: HeatReportDemo.entries(today: now),
                              meds: meds.isEmpty ? HeatReportDemo.meds : meds, name: name, days: days, now: now, simulated: true)
        } else {
            inp = ReportInput(records: ledger.records(last: days, today: now), entries: store.entries, meds: meds, name: name,
                              days: days, now: now, simulated: false)
        }
        return HeatReportBuilder.build(inp, L: Strings(lang: lang))
    }

    /// Enough to be worth a PDF: at least one day with 6 h of band data in the period (or the demo).
    func reportHasData(days: Int) -> Bool {
        isDemo || ledger.records(last: days, today: Date()).contains { $0.minutes >= 360 }
    }
}
