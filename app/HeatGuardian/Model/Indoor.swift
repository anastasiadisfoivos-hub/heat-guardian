// Swift port of tomorrow/indoor.py simulate() (two-node lumped building, hourly, exact exponential update), used
// ONLY to move a plan's indoor curve from the plan's home class to HER home class (Routine.homeClass):
//     t_in_her[h] = plan.t_in[h] + (sim(her class)[h] - sim(plan class)[h])
// Both sims run on the plan's own t_out with the default settled start, no sun term (plan.json has no shortwave),
// so the engine's carried-over state and sun gains stay in plan.t_in; only the class difference is added.
// ios/tools/mirror_frames.py checks this port against tomorrow/indoor.py on the bundled plan.

import Foundation

enum Indoor {
    struct HomeClass { let tauS: Double, dT: Double, tauF: Double, gF: Double, anchorMin: Bool }

    static let classes: [String: HomeClass] = [
        "A": HomeClass(tauS: 36, dT: 4.5, tauF: 3, gF: 0.15, anchorMin: false),
        "B": HomeClass(tauS: 72, dT: 3.0, tauF: 3, gF: 0.25, anchorMin: true),
        "C": HomeClass(tauS: 36, dT: 4.0, tauF: 2, gF: 0.30, anchorMin: true),
        "D": HomeClass(tauS: 96, dT: 1.5, tauF: 5, gF: 0.10, anchorMin: true),
    ]

    /// indoor.py simulate(t_out, home_class=…) with shortwave=None, urban_offset=(0,0), t_slow0=None, t_fast0=0.
    static func simulate(_ tOut: [Double], cls: String) -> [Double] {
        guard let p = classes[cls], !tOut.isEmpty else { return tOut }
        let n = tOut.count
        let ks = 1.0 - exp(-1.0 / p.tauS)
        let kf = 1.0 - exp(-1.0 / p.tauF)
        var ref = tOut
        if p.anchorMin {
            for i in 0..<n { ref[i] = tOut[max(0, i - 23)...i].min() ?? tOut[i] }
        }
        let first = Array(tOut.prefix(24))
        var ts = (p.anchorMin ? (first.min() ?? 0) : first.reduce(0, +) / Double(first.count)) + p.dT
        var tf = 0.0
        var out = [Double](repeating: 0, count: n)
        for i in 0..<n {
            out[i] = ts + tf
            let targetF = p.anchorMin ? p.gF * (tOut[i] - ref[i]) : p.gF * (tOut[i] - ts + p.dT)
            ts += ks * (ref[i] + p.dT - ts)
            tf += kf * (targetF - tf)
        }
        return out
    }

    /// The plan with its indoor curve moved to `cls`. Unchanged when cls is nil / the same / t_out is missing.
    static func adjust(_ plan: Plan, to cls: String?) -> Plan {
        guard let cls = cls, classes[cls] != nil else { return plan }
        let from = plan.homeClass ?? "B"
        guard from != cls, classes[from] != nil else { return plan }
        let outs = plan.hours.compactMap { $0.tOut }
        guard outs.count == plan.hours.count else { return plan }
        let a = simulate(outs, cls: cls), b = simulate(outs, cls: from)
        var p = plan
        for i in p.hours.indices {
            p.hours[i].tIn = ((plan.hours[i].tIn + a[i] - b[i]) * 10).rounded() / 10
        }
        p.homeClass = cls
        return p
    }
}
