import SwiftUI

struct ContentView: View {
    @StateObject private var session = PianoSession()

    var body: some View {
        ZStack {
            session.scene.background.ignoresSafeArea()
            VStack(alignment: .leading, spacing: 10) {
                header
                controls
                toggles
                trackRow
                Text(session.tuneLine)
                    .font(.subheadline.weight(.semibold).monospacedDigit())
                    .foregroundStyle(session.scene.ink)
                if let err = session.errorMessage {
                    Text(err)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(Color(red: 0.54, green: 0.29, blue: 0.30))
                }
                chromaRow
                chipsRow
                piano
                legend
            }
            .padding(.horizontal, 12)
            .padding(.top, 8)
            .padding(.bottom, 10)
        }
        .preferredColorScheme(session.isStealth ? .dark : .light)
        .statusBarHidden(false)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("Piano-crayon / Crayon piano")
                .font(.title2.weight(.semibold))
                .foregroundStyle(session.scene.ink)
            Text("Même couleur = même son · Tap keys · No server")
                .font(.footnote)
                .foregroundStyle(session.scene.muted)
        }
    }

    private var controls: some View {
        HStack(spacing: 8) {
            Button(session.mode == .replay ? "Stop échantillon / Stop demo" : "Rejouer / Replay demo") {
                session.toggleReplay()
            }
            .buttonStyle(CrayonButtonStyle(kind: session.mode == .replay ? .replayOn : .replay, scene: session.scene))

            Button(session.mode == .live ? "Stop / Arrêter" : "Écouter / Start listening") {
                session.toggleListen()
            }
            .buttonStyle(CrayonButtonStyle(kind: session.mode == .live ? .live : .stop, scene: session.scene))
        }
    }

    private var toggles: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Sensibilité / Sensitivity")
                    .font(.caption)
                    .foregroundStyle(session.scene.muted)
                Slider(value: $session.sensitivity, in: 0...1)
                    .tint(NoteName.gSharp.color)
            }
            if session.mode != .live {
                HStack(alignment: .center, spacing: 10) {
                    WaveformTrackView(session: session)
                    Text(clock)
                        .font(.caption.monospacedDigit().weight(.semibold))
                        .foregroundStyle(session.scene.ink)
                        .fixedSize()
                }
            }
            HStack(spacing: 14) {
                toggle("Accords / Chords", $session.chordsOn)
                toggle("Entendre / Unmute", $session.unmute)
                    .onChange(of: session.unmute) { _, _ in session.applyUnmute() }
                toggle("Auto-accord / Auto-tune", $session.autotune)
                toggle("Stealth / Scène", $session.isStealth)
            }
            Text(session.statusLine)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(session.scene.ink)
            Text(session.hint)
                .font(.caption)
                .foregroundStyle(session.scene.muted)
        }
    }

    private func toggle(_ title: String, _ value: Binding<Bool>) -> some View {
        Toggle(title, isOn: value)
            .font(.caption)
            .foregroundStyle(session.scene.ink)
            .toggleStyle(.switch)
            .labelsHidden()
            .overlay(alignment: .leading) {
                Text(title)
                    .font(.caption2)
                    .foregroundStyle(session.scene.muted)
                    .offset(y: 18)
            }
            .padding(.bottom, 14)
    }

    private var trackRow: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(session.trackLabel)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(session.scene.ink)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    trackChip(
                        title: "Tous",
                        en: "All",
                        hz: "mix FFT",
                        color: session.isStealth ? Color(white: 0.16) : Color(red: 0.957, green: 0.937, blue: 0.902),
                        ink: session.scene.ink,
                        pressed: session.isTous
                    ) {
                        session.selectAllTracks()
                    }
                    ForEach(MusicianTrack.all) { track in
                        trackChip(
                            title: track.french,
                            en: track.english,
                            hz: "\(Int(track.loHz))–\(Int(track.hiHz)) Hz",
                            color: track.color,
                            ink: .white,
                            pressed: session.selectedTracks.contains(track.id)
                        ) {
                            session.toggleTrack(track.id)
                        }
                    }
                }
            }
        }
    }

    private func trackChip(
        title: String,
        en: String,
        hz: String,
        color: Color,
        ink: Color,
        pressed: Bool,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            VStack(spacing: 1) {
                Text(title).font(.caption.weight(.semibold))
                Text(en).font(.caption2)
                Text(hz).font(.system(size: 9, weight: .semibold).monospacedDigit())
            }
            .foregroundStyle(ink)
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .background(color.opacity(pressed ? 1 : 0.22), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .stroke(color.opacity(pressed ? 1 : 0.4), lineWidth: 1)
            )
            .opacity(pressed ? 1 : 0.55)
        }
        .buttonStyle(.plain)
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
                .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 2))
            }
        }
        .padding(4)
        .background(session.scene.paper, in: RoundedRectangle(cornerRadius: 4))
    }

    private var chipsRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                if session.lit.isEmpty && session.pressed.isEmpty {
                    Text("Chante, joue, ou tape une touche · Sing, play, or tap a key")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(session.scene.muted)
                } else {
                    ForEach((session.lit + session.pressed.map { LitNote(midi: $0, db: 0, freq: 0) }).uniquedMidis) { note in
                        Text(note.label)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(note.name.labelColor)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 5)
                            .background(note.name.color, in: RoundedRectangle(cornerRadius: 4))
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
            pressed: session.pressed,
            scene: session.scene,
            onPressed: { session.setPressed($0) }
        )
        .frame(height: 180)
        .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 4, style: .continuous)
                .stroke(session.scene.muted.opacity(0.35), lineWidth: 1)
        )
    }

    private var legend: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Boîte de crayons macOS / macOS crayon box")
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
                        .background(name.color, in: RoundedRectangle(cornerRadius: 3))
                    }
                    .buttonStyle(.plain)
                }
            }
            Text("Astuce: Blueberry = La / A — Auto-accord trouve le La (~415–466 Hz)")
                .font(.caption2.italic())
                .foregroundStyle(session.scene.muted)
                .frame(maxWidth: .infinity)
        }
    }

    private var clock: String {
        func fmt(_ s: Double) -> String {
            let t = max(0, s)
            let m = Int(t) / 60
            let sec = t - Double(m * 60)
            return String(format: "%d:%04.1f", m, sec)
        }
        return "\(fmt(session.sampleTime)) / \(fmt(session.sampleDuration))"
    }
}

private struct CrayonButtonStyle: ButtonStyle {
    enum Kind {
        case live
        case stop
        case replay
        case replayOn
    }

    var kind: Kind
    var scene: SceneStyle

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .foregroundStyle(foreground)
            .background(background, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .stroke(border, lineWidth: 1)
            )
            .opacity(configuration.isPressed ? 0.85 : 1)
    }

    private var background: Color {
        switch kind {
        case .live: return Color(red: 0.44, green: 0.60, blue: 0.28).opacity(0.85)
        case .stop: return Color(red: 0.60, green: 0.28, blue: 0.29).opacity(scene == .studio ? 0.95 : 0.35)
        case .replay: return Color(red: 0.28, green: 0.28, blue: 0.60).opacity(scene == .studio ? 0.95 : 0.35)
        case .replayOn: return Color(red: 0.28, green: 0.49, blue: 0.60).opacity(0.9)
        }
    }

    private var border: Color { background }
    private var foreground: Color {
        switch scene {
        case .stealth: return Color(red: 0.604, green: 0.604, blue: 0.635)
        case .studio: return Color(red: 0.969, green: 0.945, blue: 0.910)
        }
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
