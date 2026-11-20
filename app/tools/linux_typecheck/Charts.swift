// Swift Charts stubs for Linux type-checking only. Approximations of Apple's signatures.
@_exported import SwiftUI
public protocol Plottable {}
extension Double: Plottable {}
extension Int: Plottable {}
extension String: Plottable {}
extension Date: Plottable {}
public struct PlottableValue<Value: Plottable> {
    public static func value<S: StringProtocol>(_ label: S, _ value: Value) -> PlottableValue<Value> { .init() }
}
public protocol ChartContent {}
public struct InterpolationMethod { public static let linear = InterpolationMethod(), catmullRom = InterpolationMethod(), monotone = InterpolationMethod(), cardinal = InterpolationMethod() }
public struct _ChartMod: ChartContent {}
extension ChartContent {
    public func foregroundStyle<S: ShapeStyle>(_ s: S) -> _ChartMod { .init() }
    public func interpolationMethod(_ m: InterpolationMethod) -> _ChartMod { .init() }
    public func lineStyle(_ s: StrokeStyle) -> _ChartMod { .init() }
    public func symbol<V: View>(@ViewBuilder symbol: () -> V) -> _ChartMod { .init() }
    public func symbolSize(_ s: CGFloat) -> _ChartMod { .init() }
    public func opacity(_ o: Double) -> _ChartMod { .init() }
    public func cornerRadius(_ r: CGFloat, style: RoundedCornerStyle = .circular) -> _ChartMod { .init() }
}
public struct RectangleMark: ChartContent {
    public init<X: Plottable, Y: Plottable>(xStart: PlottableValue<X>, xEnd: PlottableValue<X>, yStart: PlottableValue<Y>, yEnd: PlottableValue<Y>) {}
    public init<X: Plottable>(xStart: PlottableValue<X>, xEnd: PlottableValue<X>, y: Any? = nil) {}
}
public struct AreaMark: ChartContent {
    public init<X: Plottable, Y: Plottable>(x: PlottableValue<X>, y: PlottableValue<Y>) {}
    public init<X: Plottable, Y: Plottable>(x: PlottableValue<X>, yStart: PlottableValue<Y>, yEnd: PlottableValue<Y>) {}
}
public struct LineMark: ChartContent { public init<X: Plottable, Y: Plottable>(x: PlottableValue<X>, y: PlottableValue<Y>) {} }
public struct PointMark: ChartContent { public init<X: Plottable, Y: Plottable>(x: PlottableValue<X>, y: PlottableValue<Y>) {} }
public struct RuleMark: ChartContent { public init<X: Plottable>(x: PlottableValue<X>) {}; public init<Y: Plottable>(y: PlottableValue<Y>) {} }
public struct BarMark: ChartContent { public init<X: Plottable, Y: Plottable>(x: PlottableValue<X>, y: PlottableValue<Y>) {} }
public struct _TupleChartContent: ChartContent {}
public struct _CondChartContent<T, F>: ChartContent {}
extension Optional: ChartContent where Wrapped: ChartContent {}
@resultBuilder public enum ChartContentBuilder {
    public static func buildExpression<C: ChartContent>(_ c: C) -> C { c }
    public static func buildBlock<C: ChartContent>(_ c: C) -> C { c }
    public static func buildBlock<each C: ChartContent>(_ c: repeat each C) -> _TupleChartContent { .init() }
    public static func buildIf<C: ChartContent>(_ c: C?) -> C? { c }
    public static func buildEither<T: ChartContent, F: ChartContent>(first: T) -> _CondChartContent<T, F> { .init() }
    public static func buildEither<T: ChartContent, F: ChartContent>(second: F) -> _CondChartContent<T, F> { .init() }
}
extension ForEach: ChartContent where C: ChartContent {}
extension ForEach where D: RandomAccessCollection, C: ChartContent {
    public init(_ data: D, id: KeyPath<D.Element, ID>, @ChartContentBuilder content: @escaping (D.Element) -> C) { self.init(_stub: ()) }
}
extension ForEach where D: RandomAccessCollection, D.Element: Identifiable, ID == D.Element.ID, C: ChartContent {
    public init(_ data: D, @ChartContentBuilder content: @escaping (D.Element) -> C) { self.init(_stub: ()) }
}
public struct _ChartContentView<C>: View { public var body: Never { fatalError() } }
public struct Chart<Content: View>: View { public var body: Never { fatalError() } }
extension Chart { public init<C: ChartContent>(@ChartContentBuilder content: () -> C) where Content == _ChartContentView<C> { fatalError() } }

// Axes
public protocol AxisContent {}
public protocol AxisMark: AxisContent {}
public struct AxisValue { public func `as`<P: Plottable>(_ t: P.Type) -> P? { nil }; public var index: Int { 0 }; public var count: Int { 0 } }
public struct AxisMarkPosition { public static let automatic = AxisMarkPosition(), leading = AxisMarkPosition(), trailing = AxisMarkPosition(), top = AxisMarkPosition(), bottom = AxisMarkPosition() }
public struct AxisMarkPreset { public static let automatic = AxisMarkPreset(), aligned = AxisMarkPreset(), extended = AxisMarkPreset(), inset = AxisMarkPreset() }
public struct AxisMarkValues { public static let automatic = AxisMarkValues()
    public static func automatic(desiredCount: Int? = nil, roundLowerBound: Bool? = nil, roundUpperBound: Bool? = nil) -> AxisMarkValues { .init() }
    public static func stride(by: Double, roundLowerBound: Bool? = nil, roundUpperBound: Bool? = nil) -> AxisMarkValues { .init() } }
public struct AxisGridLine: AxisMark { public init(centered: Bool? = nil, stroke: StrokeStyle? = nil) {} }
public struct AxisTick: AxisMark { public init(centered: Bool? = nil, length: CGFloat? = nil, stroke: StrokeStyle? = nil) {} }
public struct AxisValueLabel: AxisMark {
    public init(centered: Bool? = nil, anchor: UnitPoint? = nil, multiLabelAlignment: Alignment? = nil, offsetsMarks: Bool? = nil,
                horizontalSpacing: CGFloat? = nil, verticalSpacing: CGFloat? = nil) {}
    public init<C: View>(centered: Bool? = nil, anchor: UnitPoint? = nil, multiLabelAlignment: Alignment? = nil, offsetsMarks: Bool? = nil,
                         horizontalSpacing: CGFloat? = nil, verticalSpacing: CGFloat? = nil, @ViewBuilder content: () -> C) {}
}
public struct _TupleAxisContent: AxisContent {}
@resultBuilder public enum AxisContentBuilder {
    public static func buildExpression<C: AxisContent>(_ c: C) -> C { c }
    public static func buildBlock<C: AxisContent>(_ c: C) -> C { c }
    public static func buildBlock<each C: AxisContent>(_ c: repeat each C) -> _TupleAxisContent { .init() }
}
public struct AxisMarks<Content: AxisContent>: AxisContent {
    public init<Values: Plottable>(preset: AxisMarkPreset = .automatic, position: AxisMarkPosition = .automatic, values: [Values],
                                   stroke: StrokeStyle? = nil, @AxisContentBuilder content: @escaping (AxisValue) -> Content) {}
    public init(preset: AxisMarkPreset = .automatic, position: AxisMarkPosition = .automatic, values: AxisMarkValues = .automatic,
                stroke: StrokeStyle? = nil, @AxisContentBuilder content: @escaping (AxisValue) -> Content) {}
}
public protocol ScaleDomain {}
extension ClosedRange: ScaleDomain where Bound: Plottable {}
extension View {
    public func chartXScale<D: ScaleDomain>(domain: D) -> MV { MV() }
    public func chartYScale<D: ScaleDomain>(domain: D) -> MV { MV() }
    public func chartXAxis<C: AxisContent>(@AxisContentBuilder content: () -> C) -> MV { MV() }
    public func chartYAxis<C: AxisContent>(@AxisContentBuilder content: () -> C) -> MV { MV() }
    public func chartXAxis(_ v: Visibility) -> MV { MV() }
    public func chartYAxis(_ v: Visibility) -> MV { MV() }
    public func chartLegend(_ v: Visibility) -> MV { MV() }
}
// APP-REPORT
extension LineMark { public init<X: Plottable, Y: Plottable, S: Plottable>(x: PlottableValue<X>, y: PlottableValue<Y>, series: PlottableValue<S>) {} }
