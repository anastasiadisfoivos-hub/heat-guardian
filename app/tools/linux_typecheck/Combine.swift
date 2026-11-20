// Combine stubs (ObservableObject / @Published / AnyCancellable) for Linux type-checking only. SwiftUI re-exports it.
@_exported import Foundation
public protocol ObservableObject: AnyObject {}
@propertyWrapper public struct Published<V> {
    public var wrappedValue: V
    public init(wrappedValue: V) { self.wrappedValue = wrappedValue }
}
public protocol Cancellable { func cancel() }
public final class AnyCancellable: Cancellable, Hashable { public init(_ c: @escaping () -> Void) {}; public func cancel() {}
    public static func == (a: AnyCancellable, b: AnyCancellable) -> Bool { a === b }; public func hash(into h: inout Hasher) {}
    public func store(in s: inout Set<AnyCancellable>) {} }
public protocol Scheduler { associatedtype SchedulerTimeType: Strideable where SchedulerTimeType.Stride: SchedulerTimeIntervalConvertible }
public protocol SchedulerTimeIntervalConvertible { static func seconds(_ s: Int) -> Self; static func seconds(_ s: Double) -> Self; static func milliseconds(_ ms: Int) -> Self }
extension DispatchQueue: Scheduler {
    public struct SchedulerTimeType: Strideable { public func distance(to o: Self) -> Stride { fatalError() }; public func advanced(by n: Stride) -> Self { self }
        public struct Stride: SchedulerTimeIntervalConvertible, Comparable, SignedNumeric, ExpressibleByIntegerLiteral {
            public init(integerLiteral v: Int) {}; public init?<T: BinaryInteger>(exactly: T) {}; public var magnitude: Stride { self }
            public static func < (a: Self, b: Self) -> Bool { false }; public static func + (a: Self, b: Self) -> Self { a }; public static func - (a: Self, b: Self) -> Self { a }
            public static func * (a: Self, b: Self) -> Self { a }; public static func *= (a: inout Self, b: Self) {}
            public static func seconds(_ s: Int) -> Self { 0 }; public static func seconds(_ s: Double) -> Self { 0 }; public static func milliseconds(_ ms: Int) -> Self { 0 } } }
}
public protocol Publisher { associatedtype Output; associatedtype Failure: Error }
public struct _Pub<Output, Failure: Error>: Publisher {}
extension Publisher {
    public func debounce<S: Scheduler>(for d: S.SchedulerTimeType.Stride, scheduler: S) -> _Pub<Output, Failure> { .init() }
    public func throttle<S: Scheduler>(for d: S.SchedulerTimeType.Stride, scheduler: S, latest: Bool) -> _Pub<Output, Failure> { .init() }
    public func receive<S: Scheduler>(on s: S) -> _Pub<Output, Failure> { .init() }
    public func map<T>(_ f: @escaping (Output) -> T) -> _Pub<T, Failure> { .init() }
}
extension Publisher where Failure == Never { public func sink(receiveValue: @escaping (Output) -> Void) -> AnyCancellable { AnyCancellable {} } }
public final class ObservableObjectPublisher: Publisher { public typealias Output = Void; public typealias Failure = Never; public init() {}; public func send() {} }
extension ObservableObject { public var objectWillChange: ObservableObjectPublisher { ObservableObjectPublisher() } }
