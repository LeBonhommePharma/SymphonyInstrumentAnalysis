import Foundation

/// Compile with BpmTracker.swift (Foundation + Accelerate only, no UIKit):
///   swiftc -O -o /tmp/run_bpm_selftest \
///     ios/CrayonPiano.swiftpm/BpmTracker.swift \
///     scripts/run_bpm_selftest.swift
/// scripts/smoke_test.py runs this wherever swiftc exists, so the Swift port
/// is held to the same synthetic beats as scripts/bpm_tracker.py and
/// web/bpm_tracker.js.
@main
enum RunBpmSelfTest {
    static func main() {
        do {
            print(try BpmSelfTest.run())
        } catch {
            fputs("BpmTracker self-test failed: \(error)\n", stderr)
            exit(1)
        }
    }
}
