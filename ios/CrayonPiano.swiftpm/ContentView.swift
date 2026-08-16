import SwiftUI

struct ContentView: View {
    @StateObject private var session = PianoSession()

    var body: some View {
        ZStack {
            session.scene.background.ignoresSafeArea()
            VStack(spacing: 0) {
                header
                    .padding(.horizontal, 14)
                    .padding(.top, 10)
                    .padding(.bottom, 8)
                GeometryReader { geo in
                    let wide = geo.size.width >= 720
                    let pianoH = max(260, min(380, geo.size.height * 0.42))
                    VStack(spacing: 10) {
                        HStack(alignment: .top, spacing: 10) {
                            VStack(alignment: .leading, spacing: 10) {
                                ViewThatFits(in: .horizontal) {
                                    HStack(alignment: .center, spacing: 10) {
                                        controls
                                        toggles
                                    }
                                    VStack(alignment: .leading, spacing: 10) {
                                        controls
                                        toggles
                                    }
                                }
                                trackRow
                                HStack(alignment: .center, spacing: 10) {
                                    WaveformTrackView(session: session)
                                    clock
                                }
                                .frame(height: session.waveStackHeight)
                                if !session.tuneLine.isEmpty {
                                    Text(session.tuneLine)
                                        .font(.subheadline.weight(.semibold).monospacedDigit())
                                        .foregroundStyle(session.scene.ink)
                                }
                                if let err = session.errorMessage {
                                    Text(err)
                                        .font(.subheadline.weight(.semibold))
                                        .foregroundStyle(Color(red: 0.54, green: 0.29, blue: 0.30))
                                }
                                chromaRow
                                chipsRow
                            }
                            if wide {
                                specBlock
                                    .frame(width: min(460, geo.size.width * 0.38))
                            }
                        }
                        if !wide {
                            specBlock
                                .frame(maxWidth: .infinity)
                                .frame(height: 200)
                        }
                        DualKeyboardView(session: session)
                        Spacer(minLength: 0)
                        piano
                            .frame(height: min(140, pianoH * 0.42))
                    }
                    .padding(.horizontal, 10)
                    .padding(.bottom, 10)
                }
            }
        }
        .preferredColorScheme(session.scene.colorScheme)
        .statusBarHidden(false)
        .animation(.easeInOut(duration: 0.22), value: session.sceneChoice)
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 12) {
            Text("Piano-crayon")
                .font(.title2.weight(.semibold))
                .foregroundStyle(session.scene.ink)
            Text("\(session.scoreValue) · best \(session.bestScore) · \(session.kbLayout.uppercased())")
                .font(.caption.monospacedDigit().weight(.semibold))
                .foregroundStyle(session.scene.muted)
            Spacer(minLength: 8)
            scenePicker
        }
    }

    private var scenePicker: some View {
        HStack(spacing: 6) {
            Button {
                session.enableSceneAuto()
            } label: {
                Text("A")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(session.scene.ink)
                    .frame(width: 28, height: 28)
                    .background(session.scene.paper, in: Circle())
                    .overlay(
                        Circle().stroke(
                            session.sceneAuto ? session.scene.ink : session.scene.muted.opacity(0.45),
                            lineWidth: session.sceneAuto ? 2 : 1
                        )
                    )
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Auto")
            .accessibilityAddTraits(session.sceneAuto ? .isSelected : [])
            ForEach(SceneStyle.allCases) { style in
                Button {
                    session.pickScene(style)
                } label: {
                    Circle()
                        .fill(style.swatch)
                        .overlay(
                            Circle().stroke(
                                style.isLight
                                    ? Color.black.opacity(0.22)
                                    : Color.white.opacity(0.35),
                                lineWidth: 1
                            )
                        )
                        .overlay(
                            Circle().stroke(
                                !session.sceneAuto && session.sceneChoice == style ? session.scene.ink : Color.clear,
                                lineWidth: 2
                            )
                        )
                        .frame(width: 28, height: 28)
                        .padding(4)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(style.french)
                .accessibilityAddTraits(!session.sceneAuto && session.sceneChoice == style ? .isSelected : [])
            }
        }
        .padding(.horizontal, 4)
        .background(session.scene.paper.opacity(session.scene == .stealth ? 0.55 : 0.88), in: Capsule())
        .overlay(Capsule().stroke(session.scene.muted.opacity(0.35), lineWidth: 1))
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Ambiance")
    }

    private var specBlock: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Spectre · sources regroupées")
                .font(.caption.weight(.semibold))
                .foregroundStyle(session.scene.muted)
            SpectrumPlotView(
                scene: session.scene,
                bus: session.specBus,
                paused: session.mode == .idle && session.pressed.isEmpty && session.liveTracks.isEmpty
            )
                .frame(minHeight: 180)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private var controls: some View {
        HStack(spacing: 8) {
            Button(session.mode == .replay ? "Arrêter" : "Rejouer") {
                session.toggleReplay()
            }
            .buttonStyle(QuietChipStyle(on: session.mode == .replay, scene: session.scene))

            Button(session.mode == .live ? "Arrêter" : "Écouter") {
                session.toggleListen()
            }
            .buttonStyle(QuietChipStyle(on: session.mode == .live, scene: session.scene))
        }
    }

    private var toggles: some View {
        HStack(spacing: 8) {
            labeledToggle(session.chordsOn, title: "Accords", hint: "Jusqu’à 8 notes à la fois") {
                session.chordsOn.toggle()
            }
            labeledToggle(session.unmute, title: "Son", hint: "Entendre la relecture, doucement") {
                session.unmute.toggle()
                session.applyUnmute()
            }
            labeledToggle(session.autotune, title: "La auto", hint: "Estimer le la du concert ; sinon 440 Hz") {
                session.autotune.toggle()
            }
            if !session.statusLine.isEmpty {
                Text(session.statusLine)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(session.scene.ink)
                    .lineLimit(1)
            }
        }
    }

    private func labeledToggle(_ on: Bool, title: String, hint: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.caption.weight(.semibold))
                .padding(.horizontal, 12)
                .frame(height: 36)
                .foregroundStyle(session.scene.ink)
                .background(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .fill(on ? session.scene.ink.opacity(0.12) : session.scene.paper)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(session.scene.muted.opacity(0.45), lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
        .accessibilityLabel(hint)
        .accessibilityAddTraits(on ? .isSelected : [])
    }

    private var trackRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
            Button {
                session.selectAllTracks()
            } label: {
                Text("\(session.liveTracks.count)")
                    .font(.caption.weight(.semibold).monospacedDigit())
                    .foregroundStyle(session.scene.muted)
                    .frame(width: 28, height: 44)
                    .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Toutes les pistes")
            if session.liveTracks.isEmpty {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(session.scene.muted.opacity(0.35), lineWidth: 1)
                    .frame(width: 44, height: 44)
                    .opacity(0.28)
            } else {
                ForEach(session.liveTracks) { track in
                    Button {
                        session.toggleTrack(track.id)
                    } label: {
                        Text(track.caption)
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(track.pitchClass.labelColor)
                            .frame(minWidth: 44, minHeight: 44)
                            .background(track.pitchClass.color.opacity(track.energy > 0.18 ? 1 : 0.28), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                    }
                    .buttonStyle(.plain)
                    .opacity(session.trackIsOn(track.id) ? (track.energy > 0.18 ? 1 : 0.4) : 0.28)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(session.trackIsOn(track.id) ? session.scene.ink.opacity(0.5) : Color.clear, lineWidth: 1)
                    )
                    .accessibilityLabel("\(track.caption) \(Int(track.f0.rounded())) Hz")
                }
            }
            }
        }
    }

    private var chromaRow: some View {
        HStack(spacing: 2) {
            ForEach(NoteName.allCases, id: \.self) { name in
                let db = session.chroma[name] ?? -120
                let on = session.lit.contains { $0.name == name }
                VStack {
                    Spacer(minLength: 0)
                    Capsule()
                        .fill(name.color)
                        .frame(height: max(4, min(48, CGFloat((db + 80) * 1.2))))
                }
                .frame(maxWidth: .infinity, minHeight: 52)
                .overlay(alignment: .bottom) {
                    Text(name.french)
                        .font(.system(size: 8, weight: .semibold))
                        .foregroundStyle(on ? name.labelColor : session.scene.muted)
                        .padding(.bottom, 2)
                }
                .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 4))
            }
        }
        .padding(4)
        .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 10))
    }

    private var chipsRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                if session.lit.isEmpty && session.pressed.isEmpty {
                    Color.clear.frame(height: 8)
                } else {
                    ForEach((session.lit + session.pressed.map { LitNote(midi: $0, db: 0, freq: 0) }).uniquedMidis) { note in
                        Text(note.label)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(note.name.labelColor)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 5)
                            .background(note.name.color, in: RoundedRectangle(cornerRadius: 6))
                    }
                }
            }
        }
        .frame(minHeight: 28)
    }

    private var piano: some View {
        PianoKeyboardView(
            lit: session.lit,
            harmonics: session.harmonics,
            pressed: session.pressed.union(session.boundPressed),
            binds: session.keyBinds,
            scene: session.scene,
            onPressed: { session.setPressed($0) }
        )
        .frame(maxWidth: .infinity)
        .frame(minHeight: 260)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(session.scene.muted.opacity(0.35), lineWidth: 1)
        )
        .shadow(
            color: session.scene == .stealth ? .clear : session.scene.ink.opacity(session.scene.isLight ? 0.08 : 0.28),
            radius: session.scene == .stealth ? 0 : 18,
            y: session.scene == .stealth ? 0 : 8
        )
    }

    private var legend: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Crayons")
                .font(.caption.weight(.semibold))
                .foregroundStyle(session.scene.ink)
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 4), count: 6), spacing: 4) {
                ForEach(NoteName.allCases, id: \.self) { name in
                    Button {
                        session.setPressed([60 + (NoteName.allCases.firstIndex(of: name) ?? 0)])
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                            session.setPressed([])
                        }
                    } label: {
                        VStack(spacing: 1) {
                            Text(name.french).font(.caption.weight(.semibold))
                            Text("\(name.rawValue) · \(name.pencil)").font(.system(size: 8, weight: .semibold))
                            Text("~\(Int(name.hz.rounded())) Hz").font(.system(size: 8).monospacedDigit())
                        }
                        .foregroundStyle(name.labelColor)
                        .frame(maxWidth: .infinity, minHeight: 52)
                        .background(name.color, in: RoundedRectangle(cornerRadius: 8))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var clock: some View {
        TimelineView(.animation(paused: session.mode != .replay && !session.scrubbing)) { _ in
            Text(clockText)
                .font(.caption.monospacedDigit().weight(.semibold))
                .foregroundStyle(session.scene.ink)
                .fixedSize()
        }
    }

    private var clockText: String {
        func fmt(_ s: Double) -> String {
            let t = max(0, s)
            let m = Int(t) / 60
            let sec = t - Double(m * 60)
            return String(format: "%d:%04.1f", m, sec)
        }
        return "\(fmt(session.currentSampleTime())) / \(fmt(session.sampleDuration))"
    }
}

private struct QuietChipStyle: ButtonStyle {
    var on: Bool
    var scene: SceneStyle

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 12)
            .frame(height: 36)
            .foregroundStyle(scene.ink)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(on ? scene.ink.opacity(0.12) : scene.paper)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(scene.muted.opacity(0.45), lineWidth: 1)
            )
            .opacity(configuration.isPressed ? 0.85 : 1)
    }
}

private extension Array where Element == LitNote {
    var uniquedMidis: [LitNote] {
        var seen = Set<Int>()
        return filter { seen.insert($0.midi).inserted }
    }
}

#Preview {
    ContentView()
}
