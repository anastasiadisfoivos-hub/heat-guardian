# RESEARCH_UI — Liquid Glass APIs + elder UX evidence (APP-UI, Nov 16 2026)

DESIGN.md is authoritative; this file records what the build relied on and where the evidence pushes against it.

## 1. iOS 26 SwiftUI Liquid Glass — verified signatures (Apple docs, `.md` endpoints)

| API | Exact declaration (iOS 26.0+) | Used in |
|---|---|---|
| `glassEffect(_:in:)` | `func glassEffect(_ glass: Glass = .regular, in shape: some Shape = DefaultGlassEffectShape()) -> some View` — default shape is a Capsule | `Views/Shared/Glass.swift` |
| `Glass` | `static var regular / clear / identity`, `func tint(Color?) -> Glass`, `func interactive(Bool) -> Glass` | orb, cards |
| `GlassEffectContainer` | `init(spacing: CGFloat?, content: () -> Content)` — combines shapes, improves rendering, lets them morph | Alert buttons, onboarding |
| `glassEffectID(_:in:)` | `func glassEffectID(_ id: (some Hashable & Sendable)?, in namespace: Namespace.ID) -> some View` | not needed (no morphing pair on these screens) |
| `.buttonStyle(.glass)` / `.glassProminent` | `static var glass: GlassButtonStyle`, `static var glassProminent: GlassProminentButtonStyle` | «I'm coming», «Call her», «Έγινε ✓», «Είμαι καλά» |
| `.buttonStyle(.glass(_:))` | listed in the adoption guide; its availability was not verified, so it is not used | — |
| `tabBarMinimizeBehavior(_:)` | `.automatic / .never / .onScrollDown / .onScrollUp` (minimize: iPhone only) | `FamilyRoot` |
| `backgroundExtensionEffect()` | mirrors + blurs a view into the safe area; meant for split-view detail columns; "apply with discretion", clips the view | not used — the colour field already fills the screen with `ignoresSafeArea` |
| `TabView` + `Tab(_:systemImage:value:)` | system floating glass tab bar | `FamilyRoot` |

What NOT to do (Apple "Adopting Liquid Glass"): don't put custom backgrounds on bars, tab bars or toolbars; avoid
overusing glass ("limit these effects to the most important functional elements"); avoid "layering Liquid Glass
elements on top of each other" (so: no `hgGlass` inside toolbar items or glass buttons); combine custom glass in a
`GlassEffectContainer`; test with Reduce Transparency / Reduce Motion / Increase Contrast; give every icon an
accessibility label; hide toolbar items, not their content.

## 2. Older adults (75+) — evidence

| Topic | Evidence | Applied |
|---|---|---|
| Touch targets | Apple HIG: default 44×44 pt, minimum 28×28 pt; ~12 pt padding around bezelled controls. Older users: ≥ 11.4 mm (Jin et al. 2007, via W3C WAI summary); performance kept improving to 20 mm (non-disabled) / 30 mm (motor impaired) (Chen et al. 2013). | Elder buttons 72–88 pt tall, full width (≈ 12–15 mm high, > 50 mm wide); 16 pt gaps |
| Text size | HIG default 17 pt, min 11 pt; systematic review of 40 studies: "at least 30 pt for critical text, 20 pt for secondary" (Morey et al., cited in the JMIR mHealth 2023 review); no consensus on a minimum. | Elder: state word 40 pt, guidance 26 pt, clock 60 pt, buttons 30 pt; Family: nothing below 13 pt (DESIGN §2.4) |
| Contrast | HIG / WCAG AA: 4.5:1 up to 17 pt, 3:1 for ≥ 18 pt or bold. | measured below; text darkened where needed |
| Gestures | JMIR review: prefer direct taps over gestures; complex gestures are forgotten / interrupted by tremor. HIG: "Offer alternatives to gestures", "Minimize time-boxed elements", Assistive Access: confirm twice for hard-to-undo actions. | HELP is long-press by design (see conflict 1); a short tap explains it; VoiceOver default action triggers it; the cancel question never times out |
| Feedback | JMIR review: clear feedback after every tap, don't rely on vibration alone. | «Έγινε ✓» disappears at once + success haptic; HELP turns the whole field red + error haptic |
| Cognitive load | JMIR review: fewer elements per screen, short messages, one clear way out. | Elder = one screen, one sentence, at most 2 buttons + HELP |

## 3. Measured contrast (WCAG) on the DESIGN §4 field tops

| Pair | Ratio | Action |
|---|---|---|
| danger accent #D9480F on #FFD9CC | 3.29 | state word uses #A83A0A (4.90) |
| help accent #C62828 on #FFD1D3 | 4.10 | state word uses #A61F1F (5.40) |
| text/secondary #5B6B7B on danger / help tops | 4.19 / 3.99 | text on the field uses #4A5764 (≥ 5.39 everywhere) |
| white on #E5484D (state/danger) | 3.91 | solid HELP surfaces use #C62828 (5.62) |
| white on #13A89E (health) | 2.95 | «Είμαι καλά» prominent tint #0E7C74 (5.06) |
| text/primary #0B1B2B on every top | ≥ 12.7 | — |

## 4. Conflicts with DESIGN.md (DESIGN.md followed; for Foivos to decide)
1. **Long-press HELP vs "prefer simple taps" (JMIR review, HIG).** Kept the 1.5 s long press (it prevents accidental
   alarms, and mirrors the band). Mitigations: visible «Κρατήστε πατημένο» on the button, a tap shows how, VoiceOver
   double-tap triggers it. Risk: a 75+ user who never learns the hold cannot call for help from the phone (the band's
   own button still works).
2. **"Only the selected tab label shows" vs the system tab bar.** The iOS 26 system tab bar shows every tab's label;
   DESIGN §8 forbids a custom tab bar, so the system one is used as is.
3. **Onboarding language.** DESIGN §1 quotes the English buttons; §8 forbids mixed languages. The question screen
   starts in the phone's language with a toggle; the choice then sets the mode default (Family EN, Elder GR).

## Sources
- Apple: [glassEffect(_:in:)](https://developer.apple.com/documentation/swiftui/view/glasseffect(_:in:)), [Glass](https://developer.apple.com/documentation/swiftui/glass), [GlassEffectContainer](https://developer.apple.com/documentation/swiftui/glasseffectcontainer), [glassEffectID(_:in:)](https://developer.apple.com/documentation/swiftui/view/glasseffectid(_:in:)), [glass](https://developer.apple.com/documentation/swiftui/primitivebuttonstyle/glass), [glassProminent](https://developer.apple.com/documentation/swiftui/primitivebuttonstyle/glassprominent), [tabBarMinimizeBehavior](https://developer.apple.com/documentation/swiftui/view/tabbarminimizebehavior(_:)), [TabBarMinimizeBehavior](https://developer.apple.com/documentation/swiftui/tabbarminimizebehavior), [backgroundExtensionEffect()](https://developer.apple.com/documentation/swiftui/view/backgroundextensioneffect()), [Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass), [HIG Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- [W3C WAI — Summary of research on touch/pointer target size](https://www.w3.org/WAI/GL/mobile-a11y-tf/wiki/Summary_of_Research_on_Touch/Pointer_Target_Size) (Jin et al. 2007; Chen et al. 2013; Gao & Sun 2015)
- [Design Guidelines of Mobile Apps for Older Adults: Systematic Review and Thematic Analysis, JMIR mHealth uHealth 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10557006/)
- Figma reference (read-only): file PvSgiQ0sC6OeOLWU3n4lOo, frame 4:2 and section 8:345 "Today — state tones".
