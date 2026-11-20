// Settings › Her places (Elder mode, HERDAY_SPEC.md §2, §6): location on/off with the permission state,
// «Εδώ είναι το σπίτι», and the learned places — see, retype, delete, clear all. Coordinates are never shown or sent;
// the family sets this up on her phone (Settings opens from a long press on the clock).

import SwiftUI

struct PlacesSection: View {
    @EnvironmentObject var m: AppModel
    var L: Strings
    @State private var confirmClear = false

    var body: some View {
        let _ = m.herDayVersion
        let home = m.visits.homeID()
        Section {
            Toggle(L.hdLocationOn, isOn: $m.locationOn)
            if m.locationOn {
                Text(L.hdAuth(m.locationAuth)).font(.footnote).foregroundStyle(.secondary)
            }
            Button { m.setHomeHere() } label: { Label(L.hdThisIsHome, systemImage: "house") }
                .disabled(!m.locationOn)
            if let r = m.homeSetResult { Text(r).font(.footnote).foregroundStyle(.secondary) }
            if m.visits.places.isEmpty {
                Text(L.hdNoPlaces).foregroundStyle(.secondary)
            }
            ForEach(m.visits.places) { p in
                let isHome = p.id == home
                let n = m.visits.visits.filter { $0.placeID == p.id }.count
                HStack(spacing: Palette.s12) {
                    Image(systemName: isHome ? PlaceType.home.symbol : p.type.symbol)
                        .foregroundStyle(Palette.primary)
                        .frame(width: 28)
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(isHome ? L.placeName(.home) : L.placeName(p.type))
                        Text([p.name, L.hdVisits(n)].compactMap { $0 }.joined(separator: " · "))
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 0)
                    if !isHome {
                        Menu {
                            ForEach(PlaceType.allCases.filter { $0 != .home }) { t in
                                Button { m.setPlaceType(p.id, t) } label: { Label(L.placeName(t), systemImage: t.symbol) }
                            }
                        } label: {
                            Image(systemName: "pencil.circle")
                        }
                        .accessibilityLabel(L.placeName(p.type))
                    }
                }
                .swipeActions {
                    Button(role: .destructive) { m.removePlace(p.id) } label: { Label(L.forget, systemImage: "trash") }
                }
            }
            if !m.visits.places.isEmpty {
                Button(L.hdClearPlaces, role: .destructive) { confirmClear = true }
                    .confirmationDialog(L.hdClearPlaces, isPresented: $confirmClear) {
                        Button(L.hdClearPlaces, role: .destructive) { m.clearPlaces() }
                    }
            }
        } header: { Text(L.hdPlaces) } footer: { Text(L.hdPlacesNote) }
    }
}
