// Minimal SwiftUI/Combine API stubs for Linux type-checking only. Approximations of Apple's signatures.
@_exported import Foundation
@_exported import UIKit
@_exported import Combine



// MARK: core
public protocol View { associatedtype Body: View; @ViewBuilder var body: Body { get } }
extension Never: View { public var body: Never { fatalError() } }
public struct MV: View { public init() {}; public var body: Never { fatalError() } }
public struct EmptyView: View { public init() {}; public var body: Never { fatalError() } }
public struct TupleView: View { public var body: Never { fatalError() } }
public struct CondView<T: View, F: View>: View { public var body: Never { fatalError() } }
extension Optional: View where Wrapped: View { public var body: Never { fatalError() } }

@resultBuilder public enum ViewBuilder {
    public static func buildBlock() -> EmptyView { EmptyView() }
    public static func buildBlock<C: View>(_ c: C) -> C { c }
    public static func buildBlock<each C: View>(_ c: repeat each C) -> TupleView { TupleView() }
    public static func buildExpression<C: View>(_ c: C) -> C { c }
    public static func buildIf<C: View>(_ c: C?) -> C? { c }
    public static func buildEither<T: View, F: View>(first: T) -> CondView<T, F> { CondView() }
    public static func buildEither<T: View, F: View>(second: F) -> CondView<T, F> { CondView() }
}

public struct Text: View {
    public init<S: StringProtocol>(_ s: S) {}
    public init(verbatim: String) {}
    public init<F: FormatStyle>(_ input: F.FormatInput, format: F) where F.FormatInput: Equatable, F.FormatOutput == String {}
    public init(_ d: Date, style: DateStyle) {}
    public struct DateStyle { public static let time = DateStyle(), date = DateStyle(), relative = DateStyle(), offset = DateStyle(), timer = DateStyle() }
    public func fontWeight(_ w: Font.Weight?) -> Text { self }
    public func foregroundStyle<S: ShapeStyle>(_ s: S) -> Text { self }
    public func monospacedDigit() -> Text { self }
    public static func + (a: Text, b: Text) -> Text { a }
    public var body: Never { fatalError() }
    public func font(_ f: Font?) -> Text { self }
    public func bold() -> Text { self }
}
public struct Image: View {
    public init(systemName: String) {}
    public var body: Never { fatalError() }
}
public struct Label<T: View, I: View>: View {
    public var body: Never { fatalError() }
    public init(@ViewBuilder title: () -> T, @ViewBuilder icon: () -> I) {}
}
extension Label where T == Text, I == Image {
    public init<S: StringProtocol>(_ t: S, systemImage: String) {}
}
public enum HorizontalAlignment { case leading, center, trailing }
public enum VerticalAlignment { case top, center, bottom, firstTextBaseline }
public struct Alignment { public static let leading = Alignment(), center = Alignment(), topLeading = Alignment(), bottom = Alignment(), top = Alignment(), trailing = Alignment(), topTrailing = Alignment() }
public struct VStack<C: View>: View { public init(alignment: HorizontalAlignment = .center, spacing: CGFloat? = nil, @ViewBuilder content: () -> C) {}; public var body: Never { fatalError() } }
public struct HStack<C: View>: View { public init(alignment: VerticalAlignment = .center, spacing: CGFloat? = nil, @ViewBuilder content: () -> C) {}; public var body: Never { fatalError() } }
public struct ZStack<C: View>: View { public init(alignment: Alignment = .center, @ViewBuilder content: () -> C) {}; public var body: Never { fatalError() } }
public struct ScrollView<C: View>: View { public init(@ViewBuilder content: () -> C) {}; public var body: Never { fatalError() } }
public struct NavigationStack<C: View>: View { public init(@ViewBuilder root: () -> C) {}; public var body: Never { fatalError() } }
public struct NavigationLink<L: View, D: View>: View { public init(@ViewBuilder destination: () -> D, @ViewBuilder label: () -> L) {}; public var body: Never { fatalError() } }
public struct Spacer: View { public init(minLength: CGFloat? = nil) {}; public var body: Never { fatalError() } }
public struct GeometryProxy { public var size: CGSize { fatalError() } }
public struct GeometryReader<C: View>: View { public init(@ViewBuilder content: @escaping (GeometryProxy) -> C) {}; public var body: Never { fatalError() } }
public struct ForEach<D, ID: Hashable, C> { public init(_stub: Void) {} }
extension ForEach: View where C: View { public var body: Never { fatalError() } }
extension ForEach where D: RandomAccessCollection, C: View {
    public init(_ data: D, id: KeyPath<D.Element, ID>, @ViewBuilder content: @escaping (D.Element) -> C) {}
}
extension ForEach where D: RandomAccessCollection, D.Element: Identifiable, ID == D.Element.ID, C: View {
    public init(_ data: D, @ViewBuilder content: @escaping (D.Element) -> C) {}
}
extension ForEach where D == Range<Int>, ID == Int, C: View {
    public init(_ data: Range<Int>, @ViewBuilder content: @escaping (Int) -> C) {}
}
public struct GridItem { public struct Size { public static func flexible(minimum: CGFloat = 10, maximum: CGFloat = .infinity) -> Size { Size() } }
    public init(_ size: Size = .flexible(), spacing: CGFloat? = nil) {} }
public struct LazyVGrid<C: View>: View { public init(columns: [GridItem], spacing: CGFloat? = nil, @ViewBuilder content: () -> C) {}; public var body: Never { fatalError() } }
public struct ButtonRole { public static let destructive = ButtonRole() }
public struct Button<L: View>: View {
    public init(action: @escaping () -> Void, @ViewBuilder label: () -> L) {}
    public init(role: ButtonRole?, action: @escaping () -> Void, @ViewBuilder label: () -> L) {}
    public var body: Never { fatalError() }
}
public struct ButtonStyleConfiguration { public var label: MV { fatalError() }; public var isPressed: Bool { false } }
public protocol ButtonStyle { associatedtype B: View; typealias Configuration = ButtonStyleConfiguration; @ViewBuilder func makeBody(configuration: Configuration) -> B }
public protocol PrimitiveButtonStyle {}
public struct BorderedProminentButtonStyle: PrimitiveButtonStyle {}
public struct BorderedButtonStyle: PrimitiveButtonStyle {}
extension PrimitiveButtonStyle where Self == BorderedProminentButtonStyle { public static var borderedProminent: Self { .init() } }
extension PrimitiveButtonStyle where Self == BorderedButtonStyle { public static var bordered: Self { .init() } }
public struct ButtonBorderShape { public static func roundedRectangle(radius: CGFloat) -> ButtonBorderShape { .init() } }
public struct Form<C: View>: View { public init(@ViewBuilder content: () -> C) {}; public var body: Never { fatalError() } }
public struct Section<H: View, C: View, F: View>: View { public var body: Never { fatalError() } }
extension Section where H == EmptyView, F == EmptyView { public init(@ViewBuilder content: () -> C) {} }
extension Section where H == Text, F == EmptyView { public init<S: StringProtocol>(_ t: S, @ViewBuilder content: () -> C) {} }
extension Section { public init(@ViewBuilder content: () -> C, @ViewBuilder header: () -> H, @ViewBuilder footer: () -> F) {} }
extension Section where H == EmptyView { public init(@ViewBuilder content: () -> C, @ViewBuilder footer: () -> F) {} }
extension Section where F == EmptyView { public init(@ViewBuilder content: () -> C, @ViewBuilder header: () -> H) {} }
public struct Picker<L: View, Sel: Hashable, C: View>: View { public var body: Never { fatalError() } }
extension Picker where L == Text { public init<S: StringProtocol>(_ t: S, selection: Binding<Sel>, @ViewBuilder content: () -> C) {} }
public protocol PickerStyle {}
public struct SegmentedPickerStyle: PickerStyle {}
extension PickerStyle where Self == SegmentedPickerStyle { public static var segmented: Self { .init() } }
public struct Toggle<L: View>: View { public var body: Never { fatalError() } }
extension Toggle where L == Text { public init<S: StringProtocol>(_ t: S, isOn: Binding<Bool>) {} }
public struct Stepper<L: View>: View { public var body: Never { fatalError() }
    public init<V: Strideable>(value: Binding<V>, in r: ClosedRange<V>, step: V.Stride = 1, @ViewBuilder label: () -> L) {} }
public struct TextField<L: View>: View { public var body: Never { fatalError() } }
extension TextField where L == Text { public init<S: StringProtocol>(_ t: S, text: Binding<String>) {} }
public struct Slider: View { public var body: Never { fatalError() }
    public init<V: BinaryFloatingPoint>(value: Binding<V>, in r: ClosedRange<V>, step: V.Stride = 1) where V.Stride: BinaryFloatingPoint {} }
public struct DisclosureGroup<L: View, C: View>: View { public var body: Never { fatalError() } }
extension DisclosureGroup where L == Text { public init<S: StringProtocol>(_ t: S, @ViewBuilder content: @escaping () -> C) {} }
public struct TabView<Sel: Hashable, C: View>: View { public var body: Never { fatalError() } }
extension TabView where Sel == Int { public init(@ViewBuilder content: () -> C) {} }
public struct _TabContentView<T>: View { public var body: Never { fatalError() } }

// MARK: shapes & paint
public protocol ShapeStyle {}
public struct Color: View, ShapeStyle, Hashable {
    public var body: Never { fatalError() }
    public init(red: Double, green: Double, blue: Double) {}
    public init(_ ui: UIColor) {}
    public init(uiColor: UIColor) {}
    public init(white: Double, opacity: Double = 1) {}
    public init(red: Double, green: Double, blue: Double, opacity: Double) {}
    public func opacity(_ o: Double) -> Color { self }
    public static let white = Color(red: 1, green: 1, blue: 1), black = white, red = white, green = white, pink = white,
                      orange = white, teal = white, primary = white, secondary = white, clear = white, blue = white
}
public struct HierarchicalShapeStyle: ShapeStyle {}
extension ShapeStyle where Self == Color {
    public static var white: Color { .white }; public static var red: Color { .red }; public static var green: Color { .green }
    public static var pink: Color { .pink }; public static var orange: Color { .orange }; public static var teal: Color { .teal }
}
extension ShapeStyle where Self == HierarchicalShapeStyle {
    public static var secondary: HierarchicalShapeStyle { .init() }; public static var primary: HierarchicalShapeStyle { .init() }
}
public struct UnitPoint { public static let top = UnitPoint(), bottom = UnitPoint(), center = UnitPoint() }
public struct LinearGradient: ShapeStyle, View { public var body: Never { fatalError() }
    public init(colors: [Color], startPoint: UnitPoint, endPoint: UnitPoint) {}
    public init(stops: [Gradient.Stop], startPoint: UnitPoint, endPoint: UnitPoint) {}
    public init(gradient: Gradient, startPoint: UnitPoint, endPoint: UnitPoint) {} }
public struct Gradient { public struct Stop { public init(color: Color, location: CGFloat) {} }
    public init(colors: [Color]) {}; public init(stops: [Stop]) {} }
public struct RadialGradient: ShapeStyle, View { public var body: Never { fatalError() }
    public init(colors: [Color], center: UnitPoint, startRadius: CGFloat, endRadius: CGFloat) {} }
public enum CGLineCap { case round, butt }
public enum CGLineJoin { case round, miter }
public struct StrokeStyle { public init(lineWidth: CGFloat = 1, lineCap: CGLineCap = .butt, lineJoin: CGLineJoin = .miter, dash: [CGFloat] = []) {} }
public protocol Shape: View {}
extension Shape {
    public var body: Never { fatalError() }
    public func fill<S: ShapeStyle>(_ s: S) -> MV { MV() }
    public func stroke<S: ShapeStyle>(_ s: S, lineWidth: CGFloat = 1) -> MV { MV() }
    public func stroke<S: ShapeStyle>(_ s: S, style: StrokeStyle) -> MV { MV() }
    public func strokeBorder<S: ShapeStyle>(_ s: S, lineWidth: CGFloat = 1) -> MV { MV() }
}
public enum RoundedCornerStyle { case continuous, circular }
public struct Circle: Shape { public init() {} }
public struct Rectangle: Shape { public init() {} }
public struct Capsule: Shape { public init() {} }
public struct RoundedRectangle: Shape { public init(cornerRadius: CGFloat, style: RoundedCornerStyle = .circular) {} }
public struct Path: Shape {
    public init() {}
    public init(_ f: (inout Path) -> Void) {}
    public mutating func move(to p: CGPoint) {}
    public mutating func addLine(to p: CGPoint) {}
    public mutating func addLines(_ ps: [CGPoint]) {}
    public mutating func closeSubpath() {}
}

// MARK: fonts
public struct Font {
    public enum TextStyle { case largeTitle, title, title2, title3, headline, subheadline, body, callout, footnote, caption, caption2 }
    public enum Design { case `default`, rounded, monospaced }
    public struct Weight { public static let ultraLight = Weight(), thin = Weight(), light = Weight(), regular = Weight(), medium = Weight(), semibold = Weight(), bold = Weight(), heavy = Weight(), black = Weight() }
    public static let largeTitle = Font(), title = Font(), title2 = Font(), title3 = Font(), headline = Font(), subheadline = Font(),
                      body = Font(), callout = Font(), footnote = Font(), caption = Font(), caption2 = Font()
    public static func system(size: CGFloat, weight: Weight = .regular, design: Design = .default) -> Font { Font() }
    public static func system(_ s: TextStyle, design: Design = .default) -> Font { Font() }
    public func weight(_ w: Weight) -> Font { self }
    public func monospacedDigit() -> Font { self }
    public func monospaced() -> Font { self }
}

// MARK: state & environment
@propertyWrapper public struct State<V> {
    public init(wrappedValue: V) {}
    public init(initialValue: V) {}
    public var wrappedValue: V { get { fatalError() } nonmutating set {} }
    public var projectedValue: Binding<V> { fatalError() }
}
@propertyWrapper @dynamicMemberLookup public struct Binding<V> {
    public init(get: @escaping () -> V, set: @escaping (V) -> Void) {}
    public init(projectedValue: Binding<V>) {}
    public var wrappedValue: V { get { fatalError() } nonmutating set {} }
    public var projectedValue: Binding<V> { self }
    public subscript<T>(dynamicMember kp: WritableKeyPath<V, T>) -> Binding<T> { fatalError() }
}
@propertyWrapper public struct StateObject<O: ObservableObject> {
    public init(wrappedValue: @autoclosure @escaping () -> O) {}
    public var wrappedValue: O { fatalError() }
}
@propertyWrapper public struct EnvironmentObject<O: ObservableObject> {
    public init() {}
    public var wrappedValue: O { fatalError() }
    public var projectedValue: Wrapper { fatalError() }
    @dynamicMemberLookup public struct Wrapper {
        public subscript<T>(dynamicMember kp: ReferenceWritableKeyPath<O, T>) -> Binding<T> { fatalError() }
    }
}
public enum DynamicTypeSize { case large; public var isAccessibilitySize: Bool { false } }
public enum ScenePhase { case active, inactive, background }
public struct EnvironmentValues {
    public var dynamicTypeSize: DynamicTypeSize { .large }
    public var scenePhase: ScenePhase { .active }
    public var locale: Locale { get { .current } set {} }
}
@propertyWrapper public struct Environment<V> {
    public init(_ kp: KeyPath<EnvironmentValues, V>) {}
    public var wrappedValue: V { fatalError() }
}
@propertyWrapper public struct ScaledMetric<V> {
    public init(wrappedValue: V, relativeTo: Font.TextStyle) {}
    public var wrappedValue: V { fatalError() }
}

// MARK: animation / transitions / effects
public struct Animation {
    public static let `default` = Animation()
    public static func spring(response: Double = 0.5, dampingFraction: Double = 0.8) -> Animation { Animation() }
    public static func easeInOut(duration: Double) -> Animation { Animation() }
    public static func easeOut(duration: Double) -> Animation { Animation() }
    public func repeatForever(autoreverses: Bool = true) -> Animation { self }
    public func delay(_ d: Double) -> Animation { self }
}
public func withAnimation<R>(_ a: Animation? = .default, _ body: () throws -> R) rethrows -> R { try body() }
public struct ContentTransition {
    public static let opacity = ContentTransition()
    public static func numericText() -> ContentTransition { .init() }
    public static func symbolEffect<E: SymbolEffect>(_ e: E) -> ContentTransition { .init() }
}
public protocol SymbolEffect {}
public struct PulseSymbolEffect: SymbolEffect {}
public struct ReplaceSymbolEffect: SymbolEffect {}
extension SymbolEffect where Self == PulseSymbolEffect { public static var pulse: PulseSymbolEffect { .init() } }
extension SymbolEffect where Self == ReplaceSymbolEffect { public static var replace: ReplaceSymbolEffect { .init() } }
public struct SymbolEffectOptions { public static let repeating = SymbolEffectOptions(), `default` = SymbolEffectOptions() }
public struct PresentationDetent: Hashable { public static let medium = PresentationDetent(), large = PresentationDetent() }
public struct Edge { public struct Set { public static let top = Set(), bottom = Set(), horizontal = Set(), vertical = Set(), leading = Set(), trailing = Set(), all = Set() } }
public struct ToolbarItemPlacement { public static let topBarTrailing = ToolbarItemPlacement(), primaryAction = ToolbarItemPlacement() }
public struct ToolbarItem<ID, C: View> { }
extension ToolbarItem where ID == () { public init(placement: ToolbarItemPlacement = .automatic, @ViewBuilder content: () -> C) {} }
public enum TextContentType { case name, givenName, familyName, telephoneNumber, emailAddress, username }
public enum UIKeyboardType { case phonePad, decimalPad, emailAddress, numberPad }
public struct ProposedViewSize { public static let unspecified = ProposedViewSize(); public var width: CGFloat?; public init() {}; public init(_ s: CGSize) {} }
public struct LayoutSubview { public func sizeThatFits(_ p: ProposedViewSize) -> CGSize { fatalError() }; public func place(at: CGPoint, proposal: ProposedViewSize) {} }
public protocol Layout {
    typealias Subviews = [LayoutSubview]
    associatedtype Cache = Void
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache) -> CGSize
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache)
}
extension Layout { public func callAsFunction<V: View>(@ViewBuilder _ content: () -> V) -> MV { MV() } }
public enum Visibility { case hidden, automatic, visible }
public struct AccessibilityChildBehavior { public static let combine = AccessibilityChildBehavior(), ignore = AccessibilityChildBehavior() }

extension View {
    public func font(_ f: Font?) -> MV { MV() }
    public func foregroundStyle<S: ShapeStyle>(_ s: S) -> MV { MV() }
    public func padding(_ l: CGFloat? = nil) -> MV { MV() }
    public func padding(_ e: Edge.Set, _ l: CGFloat? = nil) -> MV { MV() }
    public func frame(width: CGFloat? = nil, height: CGFloat? = nil, alignment: Alignment = .center) -> MV { MV() }
    public func frame(minWidth: CGFloat? = nil, idealWidth: CGFloat? = nil, maxWidth: CGFloat? = nil, minHeight: CGFloat? = nil,
                      idealHeight: CGFloat? = nil, maxHeight: CGFloat? = nil, alignment: Alignment = .center) -> MV { MV() }
    public func background<V: View>(_ v: V) -> MV { MV() }
    public func overlay<V: View>(_ v: V) -> MV { MV() }
    public func ignoresSafeArea() -> MV { MV() }
    public func navigationTitle<S: StringProtocol>(_ s: S) -> MV { MV() }
    public func toolbar<C: View>(@ViewBuilder content: () -> C) -> MV { MV() }
    public func sheet<C: View>(isPresented: Binding<Bool>, @ViewBuilder content: @escaping () -> C) -> MV { MV() }
    public func fullScreenCover<I: Identifiable, C: View>(item: Binding<I?>, @ViewBuilder content: @escaping (I) -> C) -> MV { MV() }
    public func presentationDetents(_ d: Set<PresentationDetent>) -> MV { MV() }
    public func environmentObject<O: ObservableObject>(_ o: O) -> MV { MV() }
    public func environment<V>(_ kp: WritableKeyPath<EnvironmentValues, V>, _ v: V) -> MV { MV() }
    public func onAppear(perform: (() -> Void)? = nil) -> MV { MV() }
    public func onChange<V: Equatable>(of v: V, _ action: @escaping (V, V) -> Void) -> MV { MV() }
    public func tabItem<V: View>(@ViewBuilder _ l: () -> V) -> MV { MV() }
    public func multilineTextAlignment(_ a: TextAlignment) -> MV { MV() }
    public func lineLimit(_ n: Int?) -> MV { MV() }
    public func minimumScaleFactor(_ f: CGFloat) -> MV { MV() }
    public func fixedSize() -> MV { MV() }
    public func fixedSize(horizontal: Bool, vertical: Bool) -> MV { MV() }
    public func monospacedDigit() -> MV { MV() }
    public func tracking(_ t: CGFloat) -> MV { MV() }
    public func contentTransition(_ t: ContentTransition) -> MV { MV() }
    public func symbolEffect<E: SymbolEffect>(_ e: E, options: SymbolEffectOptions = .default, isActive: Bool = true) -> MV { MV() }
    public func animation<V: Equatable>(_ a: Animation?, value: V) -> MV { MV() }
    public func scaleEffect(_ s: CGFloat) -> MV { MV() }
    public func opacity(_ o: Double) -> MV { MV() }
    public func shadow(color: Color, radius: CGFloat, x: CGFloat = 0, y: CGFloat = 0) -> MV { MV() }
    public func offset(x: CGFloat = 0, y: CGFloat = 0) -> MV { MV() }
    public func position(x: CGFloat, y: CGFloat) -> MV { MV() }
    public func clipped() -> MV { MV() }
    public func accessibilityHidden(_ h: Bool) -> MV { MV() }
    public func accessibilityElement(children: AccessibilityChildBehavior) -> MV { MV() }
    public func accessibilityLabel<S: StringProtocol>(_ s: S) -> MV { MV() }
    public func accessibilityAction(named: Text, _ h: @escaping () -> Void) -> MV { MV() }
    public func buttonStyle<S: ButtonStyle>(_ s: S) -> MV { MV() }
    public func buttonStyle<S: PrimitiveButtonStyle>(_ s: S) -> MV { MV() }
    public func buttonBorderShape(_ s: ButtonBorderShape) -> MV { MV() }
    public func pickerStyle<S: PickerStyle>(_ s: S) -> MV { MV() }
    public func textContentType(_ t: TextContentType?) -> MV { MV() }
    public func keyboardType(_ t: UIKeyboardType) -> MV { MV() }
    public func textSelection(_ t: TextSelectability) -> MV { MV() }
    public func autocorrectionDisabled(_ d: Bool = true) -> MV { MV() }
    public func onOpenURL(perform action: @escaping (URL) -> ()) -> MV { MV() }
    public func id<H: Hashable>(_ h: H) -> MV { MV() }
    public func tag<H: Hashable>(_ h: H) -> MV { MV() }
    public func fileImporter(isPresented: Binding<Bool>, allowedContentTypes: [UTTypeStub], onCompletion: @escaping (Result<URL, Error>) -> Void) -> MV { MV() }
}
public enum TextAlignment { case leading, center, trailing }
public struct TextSelectability { public static let enabled = TextSelectability() }
public struct UTTypeStub { public init() {}; public static let json = UTTypeStub() }

// MARK: app
public protocol Scene {}
public struct WindowGroup<C: View>: Scene { public init(@ViewBuilder content: () -> C) {} }
extension Scene { public func onChange<V: Equatable>(of v: V, _ action: @escaping (V, V) -> Void) -> some Scene { self } }
@resultBuilder public enum SceneBuilder { public static func buildBlock<S: Scene>(_ s: S) -> S { s } }
public protocol App { associatedtype B: Scene; init(); @SceneBuilder var body: B { get } }
extension App { public static func main() {} }
extension URL { public func startAccessingSecurityScopedResource() -> Bool { true }; public func stopAccessingSecurityScopedResource() {} }

// MARK: added for the iOS 26 UI (APP-UI). Signatures follow developer.apple.com/documentation/swiftui (approximate).
public struct Group<C: View>: View { public init(@ViewBuilder content: () -> C) {}; public var body: Never { fatalError() } }
public struct LazyVStack<C: View>: View { public init(alignment: HorizontalAlignment = .center, spacing: CGFloat? = nil, @ViewBuilder content: () -> C) {}; public var body: Never { fatalError() } }
public struct Link<L: View>: View { public init(destination: URL, @ViewBuilder label: () -> L) {}; public var body: Never { fatalError() } }
extension Link where L == Text { public init<S: StringProtocol>(_ t: S, destination: URL) {} }
public struct LabeledContent<L: View, C: View>: View { public var body: Never { fatalError() } }
extension LabeledContent where L == Text, C == Text { public init<S: StringProtocol, V: StringProtocol>(_ t: S, value: V) {} }
extension LabeledContent where L == Text { public init<S: StringProtocol>(_ t: S, @ViewBuilder content: () -> C) {} }
public struct DatePickerComponents: OptionSet { public let rawValue: UInt; public init(rawValue: UInt) { self.rawValue = rawValue }
    public static let hourAndMinute = DatePickerComponents(rawValue: 1), date = DatePickerComponents(rawValue: 2) }
public struct DatePicker<L: View>: View { public var body: Never { fatalError() } }
extension DatePicker where L == Text {
    public init<S: StringProtocol>(_ t: S, selection: Binding<Date>, displayedComponents: DatePickerComponents = [.hourAndMinute, .date]) {}
    public init<S: StringProtocol>(_ t: S, selection: Binding<Date>, in r: ClosedRange<Date>, displayedComponents: DatePickerComponents = [.hourAndMinute, .date]) {}
}
extension Button where L == Text { public init<S: StringProtocol>(_ t: S, action: @escaping () -> Void) {}
    public init<S: StringProtocol>(_ t: S, role: ButtonRole?, action: @escaping () -> Void) {} }
extension Button where L == Label<Text, Image> { public init<S: StringProtocol>(_ t: S, systemImage: String, action: @escaping () -> Void) {} }
extension ButtonRole { public static let cancel = ButtonRole() }

// TimelineView
public protocol TimelineSchedule {}
public struct EveryMinuteTimelineSchedule: TimelineSchedule {}
public struct PeriodicTimelineSchedule: TimelineSchedule {}
extension TimelineSchedule where Self == EveryMinuteTimelineSchedule { public static var everyMinute: EveryMinuteTimelineSchedule { .init() } }
extension TimelineSchedule where Self == PeriodicTimelineSchedule { public static func periodic(from: Date, by: TimeInterval) -> PeriodicTimelineSchedule { .init() } }
public struct TimelineViewDefaultContext { public var date: Date { Date() } }
public struct TimelineView<S: TimelineSchedule, C: View>: View { public var body: Never { fatalError() }
    public init(_ schedule: S, @ViewBuilder content: @escaping (TimelineViewDefaultContext) -> C) {} }

// Tabs (iOS 18 Tab API) + iOS 26 minimize behaviour
public protocol TabContent<TabValue> { associatedtype TabValue: Hashable }
public struct DefaultTabLabel: View { public var body: Never { fatalError() } }
public struct Tab<Value: Hashable, C: View, L: View>: TabContent { public typealias TabValue = Value }
extension Tab where L == DefaultTabLabel {
    public init<S: StringProtocol>(_ t: S, systemImage: String, value: Value, @ViewBuilder content: () -> C) {}
}
public struct TupleTabContent<V: Hashable>: TabContent { public typealias TabValue = V }
@resultBuilder public enum TabContentBuilder<V: Hashable> {
    public static func buildBlock<C: TabContent>(_ c: C) -> C where C.TabValue == V { c }
    public static func buildBlock<each C: TabContent>(_ c: repeat each C) -> TupleTabContent<V> { .init() }
}
extension TabView {
    public init<T: TabContent>(selection: Binding<Sel>, @TabContentBuilder<Sel> content: () -> T) where T.TabValue == Sel, C == _TabContentView<T> {}
}
public struct TabBarMinimizeBehavior { public static let automatic = TabBarMinimizeBehavior(), onScrollDown = TabBarMinimizeBehavior(), onScrollUp = TabBarMinimizeBehavior(), never = TabBarMinimizeBehavior() }

// Toolbar
public protocol ToolbarContent {}
extension ToolbarItem: ToolbarContent {}
extension Optional: ToolbarContent where Wrapped: ToolbarContent {}
public struct TupleToolbarContent: ToolbarContent {}
public struct CondToolbarContent<T: ToolbarContent, F: ToolbarContent>: ToolbarContent {}
@resultBuilder public enum ToolbarContentBuilder {
    public static func buildExpression<C: ToolbarContent>(_ c: C) -> C { c }
    public static func buildBlock<C: ToolbarContent>(_ c: C) -> C { c }
    public static func buildBlock<each C: ToolbarContent>(_ c: repeat each C) -> TupleToolbarContent { .init() }
    public static func buildIf<C: ToolbarContent>(_ c: C?) -> C? { c }
    public static func buildEither<T: ToolbarContent, F: ToolbarContent>(first: T) -> CondToolbarContent<T, F> { .init() }
    public static func buildEither<T: ToolbarContent, F: ToolbarContent>(second: F) -> CondToolbarContent<T, F> { .init() }
}
extension ToolbarItemPlacement { public static let topBarLeading = ToolbarItemPlacement(), confirmationAction = ToolbarItemPlacement(),
    cancellationAction = ToolbarItemPlacement(), principal = ToolbarItemPlacement(), automatic = ToolbarItemPlacement(), bottomBar = ToolbarItemPlacement() }
public enum ToolbarTitleDisplayMode { case automatic, inline, large, inlineLarge }
public struct NavigationBarItem { public enum TitleDisplayMode { case automatic, inline, large } }

// Environment additions
public enum ColorScheme { case light, dark }
public struct DismissAction { public func callAsFunction() {} }
extension EnvironmentValues {
    public var colorScheme: ColorScheme { .light }
    public var accessibilityReduceMotion: Bool { false }
    public var accessibilityReduceTransparency: Bool { false }
    public var dismiss: DismissAction { fatalError() }
    public subscript<K: EnvironmentKey>(key: K.Type) -> K.Value { get { fatalError() } set {} }
}
public protocol EnvironmentKey { associatedtype Value; static var defaultValue: Value { get } }
@propertyWrapper public struct AppStorage<V> {
    public init(_stub: Void) {}
    public var wrappedValue: V { get { fatalError() } nonmutating set {} }
    public var projectedValue: Binding<V> { fatalError() }
}
extension AppStorage where V == String { public init(wrappedValue: String, _ key: String, store: UserDefaults? = nil) {} }
extension AppStorage where V == Bool { public init(wrappedValue: Bool, _ key: String, store: UserDefaults? = nil) {} }
extension AppStorage where V == Int { public init(wrappedValue: Int, _ key: String, store: UserDefaults? = nil) {} }
@propertyWrapper public struct ObservedObject<O: ObservableObject> {
    public init(wrappedValue: O) {}
    public var wrappedValue: O { fatalError() }
    public var projectedValue: EnvironmentObject<O>.Wrapper { fatalError() }
}
@propertyWrapper public struct UIApplicationDelegateAdaptor<D: NSObject> {
    public init(_ t: D.Type) {}
    public var wrappedValue: D { fatalError() }
}

// ViewModifier
public struct _ViewModifier_Content<M>: View { public var body: Never { fatalError() } }
public protocol ViewModifier { associatedtype B: View; typealias Content = _ViewModifier_Content<Self>; @ViewBuilder func body(content: Content) -> B }
extension View { public func modifier<M: ViewModifier>(_ m: M) -> MV { MV() } }

// Liquid Glass (iOS 26)
public struct Glass {
    public static var regular: Glass { Glass() }; public static var clear: Glass { Glass() }; public static var identity: Glass { Glass() }
    public func tint(_ c: Color?) -> Glass { self }; public func interactive(_ on: Bool = true) -> Glass { self }
}
public struct DefaultGlassEffectShape: Shape { public init() {} }
public struct GlassEffectContainer<C: View>: View { public init(spacing: CGFloat? = nil, @ViewBuilder content: () -> C) {}; public var body: Never { fatalError() } }
public struct GlassButtonStyle: PrimitiveButtonStyle {}
public struct GlassProminentButtonStyle: PrimitiveButtonStyle {}
public struct PlainButtonStyle: PrimitiveButtonStyle {}
extension PrimitiveButtonStyle where Self == GlassButtonStyle { public static var glass: Self { .init() } }
extension PrimitiveButtonStyle where Self == GlassProminentButtonStyle { public static var glassProminent: Self { .init() } }
extension PrimitiveButtonStyle where Self == PlainButtonStyle { public static var plain: Self { .init() } }
extension ButtonBorderShape { public static let circle = ButtonBorderShape(), capsule = ButtonBorderShape(), automatic = ButtonBorderShape() }
public enum ControlSize { case mini, small, regular, large, extraLarge }

// Gestures / feedback / accessibility / misc
public protocol Gesture {}
public struct TapGesture: Gesture { public init(count: Int = 1) {}; public func onEnded(_ a: @escaping () -> Void) -> TapGesture { self } }
public struct SensoryFeedback: Equatable {
    public struct Weight: Equatable { public static let light = Weight(), medium = Weight(), heavy = Weight() }
    public struct Flexibility: Equatable { public static let rigid = Flexibility(), solid = Flexibility(), soft = Flexibility() }
    public static let success = SensoryFeedback(), warning = SensoryFeedback(), error = SensoryFeedback(), selection = SensoryFeedback(),
                      increase = SensoryFeedback(), decrease = SensoryFeedback(), start = SensoryFeedback(), stop = SensoryFeedback(), alignment = SensoryFeedback(),
                      levelChange = SensoryFeedback()
    public static let impact = SensoryFeedback()
    public static func impact(weight: Weight = .medium, intensity: Double = 1.0) -> SensoryFeedback { .init() }
    public static func impact(flexibility: Flexibility, intensity: Double = 1.0) -> SensoryFeedback { .init() }
}
public struct AccessibilityTraits: OptionSet { public let rawValue: Int; public init(rawValue: Int) { self.rawValue = rawValue }
    public static let isHeader = Self(rawValue: 1), isButton = Self(rawValue: 2), isSelected = Self(rawValue: 4), updatesFrequently = Self(rawValue: 8), isStaticText = Self(rawValue: 16) }
public struct AccessibilityActionKind { public static let `default` = AccessibilityActionKind(), escape = AccessibilityActionKind() }
public struct Angle { public static func degrees(_ d: Double) -> Angle { Angle() }; public static func radians(_ r: Double) -> Angle { Angle() } }
public struct ScrollIndicatorVisibility { public static let hidden = ScrollIndicatorVisibility(), visible = ScrollIndicatorVisibility(), automatic = ScrollIndicatorVisibility(), never = ScrollIndicatorVisibility() }
public struct AnyTransition { public static let opacity = AnyTransition(), identity = AnyTransition(), scale = AnyTransition()
    public static func move(edge: Edge) -> AnyTransition { .init() }; public func combined(with o: AnyTransition) -> AnyTransition { self } }
extension Edge { public static let top = Edge(), bottom = Edge(), leading = Edge(), trailing = Edge() }
public struct FillStyle { public init(eoFill: Bool = false, antialiased: Bool = true) {} }
public struct _TrimmedShape: Shape {}
extension Shape { public func trim(from: CGFloat = 0, to: CGFloat = 1) -> _TrimmedShape { .init() } }
extension Animation {
    public static func linear(duration: Double) -> Animation { Animation() }
    public static let easeInOut = Animation(), easeOut = Animation(), linear = Animation(), smooth = Animation(), snappy = Animation(), bouncy = Animation()
    public static func easeIn(duration: Double) -> Animation { Animation() }
    public static func smooth(duration: Double = 0.5, extraBounce: Double = 0) -> Animation { Animation() }
}
extension View {
    public func glassEffect<S: Shape>(_ glass: Glass = .regular, in shape: S) -> MV { MV() }
    public func glassEffect(_ glass: Glass = .regular) -> MV { MV() }
    public func tabBarMinimizeBehavior(_ b: TabBarMinimizeBehavior) -> MV { MV() }
    public func tint<S: ShapeStyle>(_ s: S?) -> MV { MV() }
    public func tint(_ c: Color?) -> MV { MV() }
    public func controlSize(_ s: ControlSize) -> MV { MV() }
    public func toolbar<C: ToolbarContent>(@ToolbarContentBuilder content: () -> C) -> MV { MV() }
    public func toolbarTitleDisplayMode(_ m: ToolbarTitleDisplayMode) -> MV { MV() }
    public func navigationBarTitleDisplayMode(_ m: NavigationBarItem.TitleDisplayMode) -> MV { MV() }
    public func scrollIndicators(_ v: ScrollIndicatorVisibility, axes: Axis.Set = [.vertical, .horizontal]) -> MV { MV() }
    public func sensoryFeedback<T: Equatable>(_ f: SensoryFeedback, trigger: T) -> MV { MV() }
    public func sensoryFeedback<T: Equatable>(_ f: SensoryFeedback, trigger: T, condition: @escaping (_ oldValue: T, _ newValue: T) -> Bool) -> MV { MV() }
    public func sensoryFeedback<T: Equatable>(trigger: T, _ f: @escaping (_ oldValue: T, _ newValue: T) -> SensoryFeedback?) -> MV { MV() }
    public func accessibilityAddTraits(_ t: AccessibilityTraits) -> MV { MV() }
    public func accessibilityRemoveTraits(_ t: AccessibilityTraits) -> MV { MV() }
    public func accessibilityHint<S: StringProtocol>(_ s: S) -> MV { MV() }
    public func accessibilityValue<S: StringProtocol>(_ s: S) -> MV { MV() }
    public func accessibilityAction(_ k: AccessibilityActionKind = .default, _ h: @escaping () -> Void) -> MV { MV() }
    public func accessibilityAction<S: StringProtocol>(named: S, _ h: @escaping () -> Void) -> MV { MV() }
    public func contentShape<S: Shape>(_ s: S, eoFill: Bool = false) -> MV { MV() }
    public func onLongPressGesture(minimumDuration: Double = 0.5, maximumDistance: CGFloat = 10, perform action: @escaping () -> Void, onPressingChanged: ((Bool) -> Void)? = nil) -> MV { MV() }
    public func simultaneousGesture<G: Gesture>(_ g: G, including mask: GestureMask = .all) -> MV { MV() }
    public func onTapGesture(count: Int = 1, perform action: @escaping () -> Void) -> MV { MV() }
    public func rotationEffect(_ a: Angle, anchor: UnitPoint = .center) -> MV { MV() }
    public func blur(radius: CGFloat, opaque: Bool = false) -> MV { MV() }
    public func transition(_ t: AnyTransition) -> MV { MV() }
    public func background<S: ShapeStyle, T: Shape>(_ s: S, in shape: T, fillStyle: FillStyle = FillStyle()) -> MV { MV() }
    public func background<V: View>(alignment: Alignment = .center, @ViewBuilder content: () -> V) -> MV { MV() }
    public func background<S: ShapeStyle>(_ s: S, ignoresSafeAreaEdges edges: Edge.Set = .all) -> MV { MV() }
    public func overlay<V: View>(alignment: Alignment = .center, @ViewBuilder content: () -> V) -> MV { MV() }
    public func preferredColorScheme(_ c: ColorScheme?) -> MV { MV() }
    public func task(priority: TaskPriority = .userInitiated, _ action: @escaping @Sendable () async -> Void) -> MV { MV() }
    public func onDisappear(perform: (() -> Void)? = nil) -> MV { MV() }
    public func disabled(_ d: Bool) -> MV { MV() }
    public func clipShape<S: Shape>(_ s: S, style: FillStyle = FillStyle()) -> MV { MV() }
    public func sheet<I: Identifiable, C: View>(item: Binding<I?>, @ViewBuilder content: @escaping (I) -> C) -> MV { MV() }
    public func fullScreenCover<C: View>(isPresented: Binding<Bool>, @ViewBuilder content: @escaping () -> C) -> MV { MV() }
    public func navigationDestination<D: Hashable, C: View>(for d: D.Type, @ViewBuilder destination: @escaping (D) -> C) -> MV { MV() }
    public func symbolRenderingMode(_ m: SymbolRenderingMode?) -> MV { MV() }
    public func layoutPriority(_ p: Double) -> MV { MV() }
    public func compositingGroup() -> MV { MV() }
    public func drawingGroup() -> MV { MV() }
    public func allowsHitTesting(_ b: Bool) -> MV { MV() }
}
public struct GestureMask: OptionSet { public let rawValue: Int; public init(rawValue: Int) { self.rawValue = rawValue }; public static let all = GestureMask(rawValue: 7) }
public enum Axis { case horizontal, vertical; public struct Set: OptionSet { public let rawValue: Int; public init(rawValue: Int) { self.rawValue = rawValue }
    public static let horizontal = Set(rawValue: 1), vertical = Set(rawValue: 2) } }
public struct SymbolRenderingMode { public static let hierarchical = SymbolRenderingMode(), monochrome = SymbolRenderingMode(), palette = SymbolRenderingMode(), multicolor = SymbolRenderingMode() }

// Her Day (APP-HERDAY): Menu, swipe actions, confirmation dialog, position
public struct Menu<L: View, C: View>: View { public init(@ViewBuilder content: () -> C, @ViewBuilder label: () -> L) {}; public var body: Never { fatalError() } }
public enum HorizontalEdge { case leading, trailing }
extension View {
    public func swipeActions<T: View>(edge: HorizontalEdge = .trailing, allowsFullSwipe: Bool = true, @ViewBuilder content: () -> T) -> MV { MV() }
    public func confirmationDialog<A: View>(_ title: String, isPresented: Binding<Bool>, titleVisibility: Visibility = .automatic, @ViewBuilder actions: () -> A) -> MV { MV() }
}

// APP-REPORT: share sheet, editable lists, Text accessibility labels, Toggle with a label view
public struct ShareLink<L: View>: View { public init(item: URL, @ViewBuilder label: () -> L) {}; public var body: Never { fatalError() } }
extension ForEach where C: View {
    public init<E: Identifiable>(_ data: Binding<[E]>, @ViewBuilder content: @escaping (Binding<E>) -> C) where D == [E], ID == E.ID {}
}
extension ForEach where C: View { public func onDelete(perform: ((IndexSet) -> Void)?) -> MV { MV() } }
extension Array { public mutating func remove(atOffsets: IndexSet) {} }
extension Toggle { public init(isOn: Binding<Bool>, @ViewBuilder label: () -> L) {} }
extension View { public func accessibilityLabel(_ t: Text) -> MV { MV() } }

// APP-TOWER: List, SecureField, wheel date picker, UIViewControllerRepresentable (MailView)
public struct List<C: View>: View { public init(@ViewBuilder content: () -> C) {}; public var body: Never { fatalError() } }
public struct SecureField<L: View>: View { public var body: Never { fatalError() } }
extension SecureField where L == Text { public init<S: StringProtocol>(_ t: S, text: Binding<String>) {} }
public protocol DatePickerStyle {}
public struct WheelDatePickerStyle: DatePickerStyle {}
extension DatePickerStyle where Self == WheelDatePickerStyle { public static var wheel: Self { .init() } }
extension View { public func datePickerStyle<S: DatePickerStyle>(_ s: S) -> MV { MV() } }
public struct UIViewControllerRepresentableContext<R: UIViewControllerRepresentable> { public var coordinator: R.Coordinator { fatalError() } }
public protocol UIViewControllerRepresentable: View where Body == Never {
    associatedtype UIViewControllerType: UIViewController
    associatedtype Coordinator = Void
    typealias Context = UIViewControllerRepresentableContext<Self>
    func makeUIViewController(context: Context) -> UIViewControllerType
    func updateUIViewController(_ vc: UIViewControllerType, context: Context)
    func makeCoordinator() -> Coordinator
}
extension UIViewControllerRepresentable { public var body: Never { fatalError() } }
extension Color { public static let gray = Color.white }
extension View {
    public func position(_ p: CGPoint) -> MV { MV() }
    public func accessibilityElement() -> MV { MV() }
    public func labelsHidden() -> MV { MV() }
}
extension View {
    public func textCase(_ c: Text.Case?) -> MV { MV() }
    public func monospaced() -> MV { MV() }
}
extension Text { public enum Case { case uppercase, lowercase } }
extension Path { public mutating func addArc(center: CGPoint, radius: CGFloat, startAngle: Angle, endAngle: Angle, clockwise: Bool) {} }
