import SwiftUI

/// DAW-style scrolling waveform (Logic Pro / GarageBand feel): a fixed playhead
/// with the audio waveform scrolling right→left as the sample plays.
struct WaveformTrackView: View {
    @ObservedObject var session: PianoSession

    private let pxPerSec: Double = 96
    private let playheadFrac: Double = 0.34

    @State private var dragging = false
    @State private var grabX: CGFloat = 0
    @State private var grabT: Double = 0

    var body: some View {
        TimelineView(.animation(paused: session.mode == .idle && session.liveTracks.isEmpty && session.pressed.isEmpty && !session.scrubbing)) { _ in
            GeometryReader { geo in
                Canvas { ctx, size in
                    draw(ctx, size, session.currentSampleTime())
                }
                .background(session.scene.paper)
                .overlay(alignment: .topLeading) {
                    if session.wavePeaks.isEmpty {
                        Text("Temps / Time · glisse pour naviguer / drag to scrub")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundStyle(session.scene.muted)
                            .padding(.leading, 8)
                            .padding(.top, 6)
                    }
                }
                .contentShape(Rectangle())
                .gesture(
                    DragGesture(minimumDistance: 0)
                        .onChanged { value in
                            if !dragging {
                                dragging = true
                                grabX = value.startLocation.x
                                grabT = session.currentSampleTime()
                                session.beginScrub()
                            }
                            let dt = Double(value.location.x - grabX) / pxPerSec
                            session.scrub(toTime: grabT - dt)
                        }
                        .onEnded { _ in
                            dragging = false
                            session.endScrub()
                        }
                )
                .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                        .stroke(session.scene.muted.opacity(0.35), lineWidth: 1)
                )
            }
        }
        .frame(minHeight: 68)
    }

    private func draw(_ ctx: GraphicsContext, _ size: CGSize, _ t: Double) {
        let w = size.width
        let h = size.height
        let tracks = session.liveTracks
        let n = max(1, tracks.count)
        let laneH = h / CGFloat(n)
        let liveLike = session.mode == .live || !tracks.isEmpty
        let playheadX = w * (liveLike ? 0.92 : playheadFrac)
        let ink = session.scene.ink

        if tracks.isEmpty {
            let mid = h / 2
            var base = Path()
            base.move(to: CGPoint(x: 0, y: mid))
            base.addLine(to: CGPoint(x: w, y: mid))
            ctx.stroke(base, with: .color(session.scene.muted.opacity(0.25)), lineWidth: 1)
            let peaks = session.wavePeaks
            if !peaks.isEmpty {
                let amp = mid - 3
                var path = Path()
                var xi = 0
                while xi <= Int(w) {
                    let x = CGFloat(xi)
                    let b = min(peaks.count - 1, Int(Double(xi) / Double(max(1, w)) * Double(peaks.count)))
                    let a = CGFloat(peaks[b]) * amp
                    if a > 0.5 {
                        path.move(to: CGPoint(x: x, y: mid - a))
                        path.addLine(to: CGPoint(x: x, y: mid + a))
                    }
                    xi += 1
                }
                ctx.stroke(path, with: .color(Color(red: 0.28, green: 0.49, blue: 0.60)), lineWidth: 1)
            }
        } else {
            for (i, track) in tracks.enumerated() {
                let y0 = CGFloat(i) * laneH
                let mid = y0 + laneH / 2
                let dim = !session.trackIsOn(track.id)
                let hist = session.energyHist(for: track.id)
                let color = track.pitchClass.color.opacity(dim ? 0.28 : 0.95)
                var path = Path()
                var xi = 0
                let amp = laneH * 0.42
                while xi <= Int(w) {
                    let x = CGFloat(xi)
                    let b = hist.isEmpty ? 0 : min(hist.count - 1, Int(Double(xi) / Double(max(1, w)) * Double(hist.count)))
                    let a = CGFloat(hist.isEmpty ? 0 : hist[b]) * amp
                    if a > 0.4 {
                        path.move(to: CGPoint(x: x, y: mid - a))
                        path.addLine(to: CGPoint(x: x, y: mid + a))
                    }
                    xi += 1
                }
                ctx.stroke(path, with: .color(color), lineWidth: 1)
            }
        }

        var ph = Path()
        ph.move(to: CGPoint(x: playheadX, y: 0))
        ph.addLine(to: CGPoint(x: playheadX, y: h))
        ctx.stroke(ph, with: .color(ink), lineWidth: 2)
    }
}
