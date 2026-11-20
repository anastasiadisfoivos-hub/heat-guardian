// «Heat report for the doctor» screen (Family: History toolbar / Settings; Elder: Settings). A system Form like
// Settings (DESIGN.md §5): the first time a plain-language consent card; then period (7 / 14 / 30 days), her name
// on/off, report language, a short preview, «Create PDF» -> the iOS share sheet. The PDF is made on the phone
// (HeatReportPDF) and leaves it only through the share sheet. Elder mode can turn the report off.

import SwiftUI

struct ReportView: View {
    @EnvironmentObject var m: AppModel
    @State private var days = 14
    @State private var includeName = true
    @State private var lang: Lang?
    @State private var agreed = false
    @State private var file: URL?
    @State private var making = false
    @State private var confirmDelete = false
    @State private var showMail = false

    private var isElder: Bool { AppMode.current == .elder }

    var body: some View {
        let L = m.L
        Form {
            if m.isDemo { Section { SimBadge(text: L.sim) } }
            if isElder {
                Section {
                    Toggle(L.rpToggle, isOn: $m.reportOn)
                } footer: { Text(L.rpToggleNote) }
            }
            if !m.reportOn {
                Section { Text(L.rpOff).font(.body) }
            } else if m.reportNeedsConsent {
                consent(L)
            } else {
                options(L)
                preview(L)
                Section {
                    Button(role: .destructive) { confirmDelete = true } label: { Label(L.rpDeleteData, systemImage: "trash") }
                }
            }
        }
        .navigationTitle(L.rpShortTitle)
        .onChange(of: days) { _, _ in file = nil }
        .onChange(of: includeName) { _, _ in file = nil }
        .onChange(of: lang) { _, _ in file = nil }
        .sheet(isPresented: $showMail) {
            if let url = file {
                MailView(to: m.tower.contacts.filter { $0.hasEmail }.map { $0.email.trimmingCharacters(in: .whitespaces) },
                         subject: L.twMailSubject + (includeName && !m.wearerName.isEmpty ? " · " + m.wearerName : ""),
                         body: L.twMailBody, attachment: url) { showMail = false }
                    .ignoresSafeArea()
            }
        }
        .confirmationDialog(L.rpDeleteData, isPresented: $confirmDelete, titleVisibility: .visible) {
            Button(L.rpDeleteData, role: .destructive) { m.deleteReportData(); file = nil; agreed = false }
        }
    }

    private func consent(_ L: Strings) -> some View {
        Section {
            ForEach(Array(L.rpConsentBody.enumerated()), id: \.offset) { _, p in
                Text(p).font(.body).fixedSize(horizontal: false, vertical: true)
            }
            Toggle(isElder ? L.rpConsentElder : L.rpConsentFamily, isOn: $agreed)
            Button { m.acceptReportConsent() } label: {
                Text(L.rpContinue).font(.body.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44)
            }
            .buttonStyle(.glassProminent)
            .disabled(!agreed)
        } header: { Text(L.rpConsentTitle) }
    }

    private func options(_ L: Strings) -> some View {
        Section {
            Picker(L.rpPeriod, selection: $days) {
                ForEach(AppModel.reportPeriods, id: \.self) { Text(L.rpDays($0)).tag($0) }
            }
            .pickerStyle(.segmented)
            Toggle(L.rpIncludeName, isOn: $includeName)
            Picker(L.rpLanguage, selection: Binding(get: { lang ?? m.lang }, set: { lang = $0 })) {
                ForEach(Lang.allCases) { Text($0.native).tag($0) }
            }
            .pickerStyle(.segmented)
        } header: { Text(L.rpTitle) } footer: { Text(L.rpPreviewNote) }
    }

    @ViewBuilder
    private func preview(_ L: Strings) -> some View {
        if !m.reportHasData(days: days) {
            Section { Text(L.rpNoData).foregroundStyle(.secondary) }
        } else {
            let r = m.makeReport(days: days, includeName: includeName, lang: lang ?? m.lang)
            Section {
                ForEach(Array(r.figures.prefix(4).enumerated()), id: \.offset) { _, f in
                    LabeledContent(f.label, value: f.value)
                }
                if let l = r.summary.first { Text(l.text).font(.footnote).foregroundStyle(.secondary) }
                NavigationLink { BodyInHeatView() } label: { Label(L.bhScreenTitle, systemImage: "waveform.path.ecg") }
                if let url = file {
                    // owner decision Nov 19: email to the family (prefilled) or the share sheet; SMS cannot carry a PDF
                    Button { showMail = true } label: { Label(L.twEmailReport, systemImage: "envelope") }
                        .disabled(!MailView.canSend)
                    if !MailView.canSend { Text(L.twNoMail).font(.footnote).foregroundStyle(.secondary) }
                    ShareLink(item: url) { Label(L.twShareReport, systemImage: "square.and.arrow.up") }
                    Text(L.twNoPDFbySMS).font(.footnote).foregroundStyle(.secondary)
                } else {
                    Button {
                        making = true
                        file = try? HeatReportPDF.file(r)
                        making = false
                    } label: {
                        Label(making ? L.rpMaking : L.rpMake, systemImage: "doc.richtext")
                    }
                    .disabled(making)
                }
            } footer: { Text(r.t["disclaimer_el"] ?? "") + Text("\n") + Text(r.t["disclaimer_en"] ?? "") }
        }
    }
}

/// Settings › her medicines for the doctor's report: free text + an optional type, on this phone only.
struct MedListSection: View {
    @EnvironmentObject var m: AppModel
    var L: Strings

    var body: some View {
        Section {
            ForEach($m.meds) { $med in
                VStack(alignment: .leading, spacing: 6) {
                    TextField(L.mlName, text: $med.name)
                    Picker(L.mlClass, selection: $med.cls) {
                        Text(L.mlClassNone).tag(MedClass?.none)
                        ForEach(MedClass.allCases) { Text(L.rpClass($0)).tag(MedClass?.some($0)) }
                    }
                    if med.cls == nil, let g = MedGuess.guess(med.name) {
                        Text(L.mlGuess(g)).font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
            .onDelete { m.meds.remove(atOffsets: $0) }
            Button { m.meds.append(Medication(name: "", cls: nil)) } label: { Label(L.mlAdd, systemImage: "plus.circle") }
            NavigationLink { ReportView() } label: { Label(L.rpShortTitle, systemImage: "doc.text") }
        } header: { Text(L.mlTitle) } footer: { Text(L.mlNote) }
    }
}

#Preview("Report") { NavigationStack { ReportView() }.environmentObject(AppModel.shared) }
