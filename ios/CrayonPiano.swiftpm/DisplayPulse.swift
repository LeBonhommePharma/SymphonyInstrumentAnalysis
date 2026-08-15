import QuartzCore
import UIKit

/// One callback per display refresh (typically 60 or 120 Hz) on the main run loop.
final class DisplayPulse: NSObject {
    var onTick: (() -> Void)?
    private var link: CADisplayLink?

    var isRunning: Bool { link != nil }

    func start() {
        guard link == nil else { return }
        let link = CADisplayLink(target: self, selector: #selector(step(_:)))
        let hz = max(60, UIScreen.main.maximumFramesPerSecond)
        link.preferredFrameRateRange = CAFrameRateRange(
            minimum: 60,
            maximum: Float(hz),
            preferred: Float(hz)
        )
        link.add(to: .main, forMode: .common)
        self.link = link
    }

    func stop() {
        link?.invalidate()
        link = nil
    }

    @objc private func step(_ link: CADisplayLink) {
        onTick?()
    }
}
