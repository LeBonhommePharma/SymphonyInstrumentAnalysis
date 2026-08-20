/**
 * English + French UI copy — the first two supported languages.
 * Persist in localStorage; default from navigator.language or ?lang=en|fr.
 */
(function (global) {
  const STORAGE_KEY = "symphony-lang";

  const STRINGS = {
    en: {
      pianoTitleTag: "Crayon piano — Symphony Instrument Analysis",
      pianoEyebrow: "crayon piano",
      pianoSettings: "settings",
      pianoTracksLabel: "tracks",
      pianoClock: "clock",
      pianoConcertA: "concert A",
      laneEyebrow: "stacked lanes",
      laneMeta: "one lane per density cluster",
      chromaEyebrow: "chroma",
      chromaMeta: "12 pitch classes",
      litNow: "lit right now",
      specEyebrow: "spectrum · clustered sources",
      specMeta: "log axis · 27.5 Hz → 4186 Hz",
      boardMeta: "lit = notes in the sound",
      kbMetaPiano: "Z=Do3 · D=Do4 · Q=La4 · 10 fingers",
      pianoFoot: "Analysis only — this page never plays a sound.",

      navLive: "Live listen",
      navPiano: "Piano",
      navHow: "How it works",
      pillSilent: "Silent",
      pillLive: "Live",
      hubEyebrow: "symphony instrument analysis",
      hubFamily: "· part of the Le Bonhomme Pharma family",
      statRangeLabel: "peak-pick range",
      statKeysLabel: "piano keys",
      statNotesLabel: "crayon notes",
      pipeEyebrow: "how it works",
      pipeMeta: "play · listen · look · name",
      step1T: "Play a song",
      step1B: "Anything with sound — speaker, room, or headphones.",
      step2T: "The mic listens",
      step2B: "One tap. Audio only, and the page never plays back.",
      step3T: "Look at the wiggles",
      step3B: "Every frequency it hears, drawn on a log Hz axis.",
      step4T: "Name the sounds",
      step4B: "Peaks become notes and density-clustered tracks.",
      howEyebrow: "explained like you are 5",
      howSandwichTitle: "A song is a sandwich, not a blob",
      howHardTitle: "Naming notes while the song is still playing",
      howPianoTitle: "Find it. Play it. Match it.",
      howBoomName: "Boom",
      howTuneName: "Tune",
      howSparkleName: "Sparkle",
      howTheKey: "the key",
      howTheWiggle: "the wiggle",
      logAxis: "log axis",
      axisOnly: "no signal on this page — the axis only",
      tutEyebrow: "silent live listen",
      tutSilentNote: "Silent — analysis only. Never pauses your music.",
      pianoMeta: "lit = notes in the sound · type Z D Q to play",
      kbEyebrow: "computer keyboard",
      kbMetaTut: "type to play · Z=Do3 · D=Do4 · Q=La4 · both boards live",
      kbHint: "Both keyboards play at once — notes follow the physical key, not the letter printed on it. ↑ ↓ shift the octave; Do1 is two octaves down.",
      octLabel: "octave",
      octRange: "reaches",
      tracksEyebrow: "live tracks",
      labelScore: "score",
      statusIdle: "Audio only. Now Playing reaches this page only as sound through the mic — the web cannot read the media list of your device.",
      iosMicWarn: "On iPhone and iPad, opening the mic makes iOS switch to a recording audio session, so other apps stop playing. That is an iOS rule a web page cannot opt out of. Stop releases the mic so playback can resume.",

      langName: "English",
      htmlLang: "en",
      hubTitle: "Symphony Instrument Analysis — see the Hertz of this device",
      hubBadge: "HTTPS · phone · 5G · silent · EN/FR",
      hubH1: "See what this device is playing",
      hubLead:
        "The page stays quiet. It only draws the live sound of this device — speaker, room, or headphone leak. Soft auto-gain lifts quiet rooms. Tracks come from density clustering. No melody? It still draws the noise. It never fakes a tune.",
      hubCtaTutorial: "Open the 60-second live listen",
      hubCtaPiano: "Open the crayon piano",
      hubCtaHowTo: "How it works (ELI5)",
      hubUsefulTitle: "Useful",
      hubUsefulBody:
        "A song is a sandwich: boom / tune / sparkle. Each instrument gets its own track. Practice one layer instead of drowning in the whole mix.",
      hubHardTitle: "Why live is hard",
      hubHardBody:
        "Notes stack, pianos ring extra high copies, and the picture keeps moving. The grown-up tool records, then looks.",
      hubPianoTitle: "Piano superpower",
      hubPianoBody: "If the loudest wiggle is 440 Hz, that is the A key. Find it. Play it. Match it.",
      hubFoot:
        "Grown-up CLI stays on a Mac. Public pages: English and French first. Source:",
      howTitle: "How this works (explained like you are 5) — Symphony",
      howH1: "Sound is air wiggling",
      howP1:
        "Sound is air wiggling. Slow wiggles are low notes. Fast wiggles are high notes. We count the wiggles in one second. That count is Hertz (Hz).",
      howP2: "A piano A is about 440 Hz. A low bass note can be near 110 Hz.",
      howP3:
        "Open this on the device that is already making sound, including a phone on 5G. The page stays silent. Soft auto-gain lifts quiet rooms and headphone bleed. Tracks are density-clustered on the fly. No melody? It still draws voices and noise. It never fakes a tune.",
      howOpenTutorial: "Open the silent live tutorial",
      howOpenPiano: "Open the crayon piano (US or Canadian French)",
      howBackHub: "Symphony",
      crumbPiano: "Piano",
      howH2Useful: "Useful",
      howSandwichIntro: "Three layers, bottom to top:",
      howBoom: "the bottom. Left hand and bass.",
      howTune: "the middle. The part you can hum.",
      howSparkle: "the top. Extra shine and air.",
      howSandwichOut: "The tool writes that recipe in Hertz. Then you can practice one layer at a time.",
      howH2Hard: "Why doing it live is hard",
      howHardIntro: "It is like reading a page someone is still flipping:",
      howHardLi1: "Many notes stack at once (chords).",
      howHardLi2: "Piano keys ring extra high copies called overtones.",
      howHardLi3: "The computer needs a little bite of sound before it can guess.",
      howHardOut:
        "So the grown-up tool records, then looks. Tiny delay, better answer. The live page shows the messy moving picture so the delay makes sense.",
      howH2Piano: "Piano superpower",
      howPianoP:
        "If the loudest wiggle is 440 Hz, that is the A key. Find it. Play it. Match it. That is ear training: hearing a map, not a blur.",
      howH2Table: "Kid words vs Hertz",
      howThKid: "Kid words",
      howThGrown: "Grown-up words",
      howThHz: "Typical Hz",
      howRowBoomKid: "Boom / rumble",
      howRowBoomGrown: "Bass foundation",
      howRowBodyKid: "Warm body",
      howRowBodyGrown: "Low-mid",
      howRowTuneKid: "Tune you can hum",
      howRowTuneGrown: "Mid melody",
      howRowAirKid: "Sparkle / air",
      howRowAirGrown: "High color",
      howImgAlt: "Four-step how-to: play a song, the mic listens, look at the wiggles, then name the sounds in Hertz.",
      tutTitle: "Live listen — Symphony Instrument Analysis",
      tutBadge: "Silent · audio only · EN/FR",
      tutH1: "See what this device is playing",
      tutLead:
        "This page never plays a song. One tap opens the mic — and if the room is quiet it listens to what this computer is playing, drawing every frequency it hears.",
      btnMic: "Listen",
      btnTab: "This computer",
      btnStop: "Stop",
      tourNext: "Next idea",
      crumbEli5: "ELI5",
      labelNote: "closest note",
      labelHz: "fundamental",
      peaksHeading: "clustered sources",
      meterLabel: "Input",
      meterHint: "Works with quiet rooms and headphone leak — no need to blast the speaker.",
      hudLive: "live",
      hudOff: "off",
      gateTitle: "One tap. Mic first.",
      gateBody:
        "Listen asks for the microphone. If there is no music around, it falls through to live listen of this computer. This page never plays sound back.",
      footerHint:
        "One Listen: microphone first. If the room is quiet, this page asks for the tab or window that is playing. Websites cannot read Apple’s Now Playing list.",
      statusMicOn: "Microphone — music around. Analysis only; nothing is played back.",
      statusSniff: "Microphone on. Checking if there is music around…",
      statusMicQuiet: "Nothing around the mic. Play it out loud — a website cannot read Now Playing.",
      statusNeedTab: "Nothing around the mic. Share the tab that is playing.",
      statusTabOn: "Live listen — this computer (tab audio, video discarded). Page stays silent.",
      statusStopped: "Stopped. Play something on the device, then listen again.",
      statusNeedGesture: "Tap Listen once more if the browser blocked audio.",
      errMicDenied: "Mic permission was denied. Allow Microphone for this site, then tap Listen.",
      errTabDenied: "Tab audio was not shared. Tap “This computer is playing” if the song is in a browser tab.",
      errNoMic: "This device has no microphone the browser can use.",
      errSecure:
        "Browsers only allow the mic on HTTPS (or localhost). Open the public thebonhomme.com link on this phone, not a LAN address.",
      errNoTabShare: "This browser cannot share tab audio. On a phone, play it out loud so the mic can hear it.",
      errNoAudioTrack: "No audio track. Share a tab or window with sound, and turn audio sharing on.",
      errNoAudioCtx: "This browser cannot listen. Try Safari or Chrome on this phone.",
      tracksHeading: "Live tracks · {count}",
      nInstruments: "{n} instruments",
      nInstrument1: "1 instrument",
      nInstrument0: "0 instruments",
      laneEmpty: "No instrument yet",
      familyBass: "Bass",
      familyBody: "Body",
      familyTune: "Tune",
      familyAir: "Air",
      familyNoise: "Noise",
      rulerNow: "now",
      liveElapsed: "{n}s live",
      hzWaiting: "waiting",
      hzNoPitch: "no clear pitch",
      hzWaitingDevice: "waiting for this device",
      peaksWaiting: "Waiting for live sound…",
      quietIdle: "Tap Listen. Microphone first — if nothing is around, live listen moves to this computer.",
      quietPitch:
        "Hearing this device right now. Tracks follow density clusters in the spectrum.",
      quietNoise: "No clear melody. Still drawing the live sound (voices, noise, room). We will not fake a tune.",
      quietAfter:
        "Quiet now — soft gain is still listening. Headphone bleed and room tone still count. We cannot read Apple’s Now Playing list from the web.",
      peaksNoise: "Energy without a hummable pitch — that is still this device, right now.",
      hardDefault: "Lane count is density-clustered on the fly. Quiet is still drawn — we never invent a tune.",
      hardMany:
        "Density found {n} independent sources after folding harmonics together. A psytrance session can have 40-80 DAW tracks; this picture counts pitched clusters, not mixer channels.",
      hardOvertones: "Overtones are ringing with the fundamental — clustering keeps them from inventing extra instruments when they lock.",
      hardClear: "One clear cluster — easy case. Songs rarely stay this tidy.",
      hardNoise: "No clear pitch cluster. The room/noise lane keeps rolling anyway.",
      demoQuiet: "Layout preview only — not live audio. Real use: tap Listen on the device that is playing.",
      demoStatus: "Preview of density-clustered tracks. Time is the waveform. No slider. No song is playing.",
      demoHard: "Example: several density clusters at once. Lane count is not a fixed parameter.",
      tour0Title: "We will not play a song over yours",
      tour0Body:
        "Whatever this device is already making — Now Playing through the speaker, a piano, voices, noise — gets drawn. We never put a demo song under it.",
      tour1Title: "One track per instrument, like Logic",
      tour1Body:
        "If we hear 6 instruments, you get 6 tracks. Bass sits at the bottom. The white line on the right is now. There is no time slider.",
      tour2Title: "No tune? We still draw the live sound",
      tour2Body:
        "Random noise and voices are still this device, right now. We do not invent a melody. If Now Playing is on, turn the speaker up so the mic can hear it.",
      tour3Title: "A song is a sandwich. That is the useful part.",
      tour3Body:
        "Boom on the bottom is left-hand / bass. The middle is the tune you can hum. The top is sparkle. Practice one layer at a time.",
      tour4Title: "Piano superpower",
      tour4Body:
        "If a clear pitch appears, 440 Hz is the A key. Find it. Play it. Match it. Live guessing stays hard when many pitches stack.",
      themeGroup: "Look",
      themeDay: "Day",
      themeLight: "Light",
      themeDark: "Dark",
      themeNight: "Night",
      themeStealth: "Stealth",
      themeAuto: "Auto",
      specAxisHz: "Hz",
      specAxisDb: "dBFS",
      pianoFull: "full piano · A0–C8",
    },
    fr: {
      pianoTitleTag: "Piano-crayon — Symphony Instrument Analysis",
      pianoEyebrow: "crayon piano",
      pianoSettings: "réglages",
      pianoTracksLabel: "pistes",
      pianoClock: "horloge",
      pianoConcertA: "la du concert",
      laneEyebrow: "pistes empilées",
      laneMeta: "une piste par groupe de densité",
      chromaEyebrow: "chroma",
      chromaMeta: "12 classes de hauteur",
      litNow: "allumé maintenant",
      specEyebrow: "spectre · sources regroupées",
      specMeta: "axe log · 27.5 Hz → 4186 Hz",
      boardMeta: "allumé = notes dans le son",
      kbMetaPiano: "Z=Do3 · D=Do4 · Q=La4 · 10 doigts",
      pianoFoot: "Analyse seulement — cette page ne joue jamais de son.",

      navLive: "Écoute live",
      navPiano: "Piano",
      navHow: "Comment ça marche",
      pillSilent: "Silencieux",
      pillLive: "Live",
      hubEyebrow: "symphony instrument analysis",
      hubFamily: "· fait partie de la famille Le Bonhomme Pharma",
      statRangeLabel: "plage de détection",
      statKeysLabel: "touches de piano",
      statNotesLabel: "notes crayon",
      pipeEyebrow: "comment ça marche",
      pipeMeta: "jouer · écouter · regarder · nommer",
      step1T: "Fais jouer une chanson",
      step1B: "N’importe quel son — haut-parleur, pièce ou écouteurs.",
      step2T: "Le micro écoute",
      step2B: "Une touche. Audio seulement, et la page ne rejoue jamais rien.",
      step3T: "Regarde les vagues",
      step3B: "Chaque fréquence entendue, tracée sur un axe log en Hz.",
      step4T: "Nomme les sons",
      step4B: "Les pics deviennent des notes et des pistes regroupées par densité.",
      howEyebrow: "expliqué comme si tu avais 5 ans",
      howSandwichTitle: "Une chanson est un sandwich, pas une bouillie",
      howHardTitle: "Nommer les notes pendant que la chanson joue encore",
      howPianoTitle: "Trouve-la. Joue-la. Accorde-toi.",
      howBoomName: "Boum",
      howTuneName: "Mélodie",
      howSparkleName: "Brillance",
      howTheKey: "la touche",
      howTheWiggle: "la vibration",
      logAxis: "axe log",
      axisOnly: "aucun signal sur cette page — l’axe seulement",
      tutEyebrow: "écoute live silencieuse",
      tutSilentNote: "Silencieux — analyse seulement. N’interrompt jamais ta musique.",
      pianoMeta: "allumé = notes dans le son · tape Z D Q pour jouer",
      kbEyebrow: "clavier d’ordinateur",
      kbMetaTut: "tape pour jouer · Z=Do3 · D=Do4 · Q=La4 · les deux claviers",
      kbHint: "Les deux claviers jouent en même temps — la note suit la touche physique, pas la lettre imprimée dessus. ↑ ↓ décalent l’octave; Do1 est deux octaves plus bas.",
      octLabel: "octave",
      octRange: "portée",
      tracksEyebrow: "pistes live",
      labelScore: "score",
      statusIdle: "Audio seulement. « En cours de lecture » n’arrive ici que comme son capté par le micro — le web ne peut pas lire la liste multimédia de ton appareil.",
      iosMicWarn: "Sur iPhone et iPad, ouvrir le micro fait passer iOS en session audio d’enregistrement, alors les autres applications arrêtent de jouer. C’est une règle d’iOS qu’une page web ne peut pas contourner. Arrêter libère le micro pour que la lecture reprenne.",

      langName: "Français",
      htmlLang: "fr",
      hubTitle: "Symphony — analyse d’instruments : voir les hertz de cet appareil",
      hubBadge: "HTTPS · téléphone · 5G · silencieux · EN/FR",
      hubH1: "Voir ce que cet appareil est en train de jouer",
      hubLead:
        "La page reste silencieuse. Elle ne fait que dessiner le son live de cet appareil — haut-parleur, pièce ou fuite des écouteurs. Un gain doux relève les pièces calmes. Les pistes viennent du regroupement par densité. Pas de mélodie ? Elle dessine quand même le bruit. Elle n’invente jamais un air.",
      hubCtaTutorial: "Ouvrir l’écoute en direct (60 secondes)",
      hubCtaPiano: "Ouvrir le piano-crayon",
      hubCtaHowTo: "Comment ça marche (très simple)",
      hubUsefulTitle: "Utile",
      hubUsefulBody:
        "Une chanson, c’est un sandwich : grave / air / brillance. Chaque instrument a sa piste. Travaille une couche au lieu de tout mélanger.",
      hubHardTitle: "Pourquoi le direct est difficile",
      hubHardBody:
        "Les notes se superposent, le piano fait des copies aiguës, et l’image n’arrête pas de bouger. L’outil adulte enregistre, puis regarde.",
      hubPianoTitle: "Le superpouvoir du piano",
      hubPianoBody: "Si le plus gros tremblement fait 440 Hz, c’est la touche la. Trouve-la. Joue-la. Imite-la.",
      hubFoot:
        "L’outil en ligne de commande reste sur Mac. Pages publiques : anglais et français d’abord. Source :",
      howTitle: "Comment ça marche (expliqué simplement) — Symphony",
      howH1: "Le son, c’est de l’air qui vibre",
      howP1:
        "Le son, c’est de l’air qui vibre. Les vibrations lentes font les notes graves. Les vibrations rapides font les notes aiguës. On compte les vibrations en une seconde. Ce compte, c’est le hertz (Hz).",
      howP2: "Un la de piano fait environ 440 Hz. Une basse grave peut être près de 110 Hz.",
      howP3:
        "Ouvre ceci sur l’appareil qui fait déjà du son, y compris un téléphone en 5G. La page reste silencieuse. Un gain automatique relève les pièces calmes et la fuite des écouteurs. Les pistes sont regroupées par densité en direct. Pas d’air ? Elle dessine quand même les voix et le bruit. Elle n’invente jamais de mélodie.",
      howOpenTutorial: "Ouvrir le tutoriel silencieux en direct",
      howOpenPiano: "Ouvrir le piano-crayon (É.-U. ou canadien français)",
      howBackHub: "Symphony",
      crumbPiano: "Piano",
      howH2Useful: "Utile",
      howSandwichIntro: "Trois couches, de bas en haut :",
      howBoom: "le bas. Main gauche et basse.",
      howTune: "le milieu. La partie qu’on peut fredonner.",
      howSparkle: "le haut. Le brillant et l’air.",
      howSandwichOut: "L’outil écrit cette recette en hertz. Ensuite tu peux travailler une couche à la fois.",
      howH2Hard: "Pourquoi le faire en direct est difficile",
      howHardIntro: "C’est comme lire une page que quelqu’un tourne encore :",
      howHardLi1: "Plusieurs notes s’empilent en même temps (les accords).",
      howHardLi2: "Les touches de piano font sonner des copies plus aiguës : les harmoniques.",
      howHardLi3: "L’ordinateur a besoin d’une petite bouchée de son avant de deviner.",
      howHardOut:
        "Alors l’outil adulte enregistre, puis regarde. Petit délai, meilleure réponse. La page en direct montre l’image qui bouge, pour que le délai ait un sens.",
      howH2Piano: "Le superpouvoir du piano",
      howPianoP:
        "Si le plus gros tremblement fait 440 Hz, c’est la touche la. Trouve-la. Joue-la. Imite-la. C’est l’oreille : une carte, pas un flou.",
      howH2Table: "Mots d’enfant et hertz",
      howThKid: "Mots d’enfant",
      howThGrown: "Mots d’adulte",
      howThHz: "Hz typiques",
      howRowBoomKid: "Boom / grondement",
      howRowBoomGrown: "Fond de basse",
      howRowBodyKid: "Corps chaud",
      howRowBodyGrown: "Grave-médium",
      howRowTuneKid: "Air à fredonner",
      howRowTuneGrown: "Mélodie médium",
      howRowAirKid: "Brillance / air",
      howRowAirGrown: "Couleur aiguë",
      howImgAlt: "Mode d’emploi en quatre étapes : jouer un morceau, le micro écoute, regarder les tremblements, nommer les sons en hertz.",
      tutTitle: "Écoute en direct — Symphony analyse d’instruments",
      tutBadge: "Silencieux · audio seulement · EN/FR",
      tutH1: "Voir ce que cet appareil est en train de jouer",
      tutLead:
        "Cette page ne joue jamais de chanson. Une touche ouvre le micro — et si la pièce est calme, elle écoute ce que joue cet ordinateur et dessine chaque fréquence entendue.",
      btnMic: "Écouter",
      btnTab: "Cet ordinateur",
      btnStop: "Arrêter",
      tourNext: "Idée suivante",
      crumbEli5: "Très simple",
      labelNote: "note la plus proche",
      labelHz: "fondamentale",
      peaksHeading: "sources regroupées",
      meterLabel: "Entrée",
      meterHint: "Marche en pièce calme et avec la fuite des écouteurs — pas besoin de pousser le volume.",
      hudLive: "direct",
      hudOff: "arrêt",
      gateTitle: "Un appui. Le micro d’abord.",
      gateBody:
        "Écouter demande le micro. S’il n’y a pas de musique autour, ça passe à l’écoute en direct de cet ordinateur. Cette page ne rejoue jamais le son.",
      footerHint:
        "Un Écouter : micro d’abord. Si la pièce est calme, la page demande l’onglet ou la fenêtre qui joue. Un site ne peut pas lire la liste Apple En cours de lecture.",
      statusMicOn: "Micro — il y a de la musique autour. Analyse seulement ; rien n’est rejoué.",
      statusSniff: "Micro allumé. On vérifie s’il y a de la musique autour…",
      statusMicQuiet: "Rien autour du micro. Joue à voix haute — un site ne peut pas lire En cours de lecture.",
      statusNeedTab: "Rien autour du micro. Partage l’onglet qui joue.",
      statusTabOn: "Écoute en direct — cet ordinateur (audio d’onglet, vidéo écartée). La page reste silencieuse.",
      statusStopped: "Arrêté. Fais jouer quelque chose sur l’appareil, puis écoute à nouveau.",
      statusNeedGesture: "Appuie encore sur Écouter si le navigateur a bloqué l’audio.",
      errMicDenied: "Le micro est refusé. Autorise le micro pour ce site, puis appuie sur Écouter.",
      errTabDenied: "L’audio d’onglet n’a pas été partagé. Appuie sur « Cet ordinateur joue » si la chanson est dans un onglet.",
      errNoMic: "Cet appareil n’a pas de micro que le navigateur puisse utiliser.",
      errSecure:
        "Les navigateurs n’autorisent le micro qu’en HTTPS (ou en localhost). Ouvre le lien public thebonhomme.com sur ce téléphone, pas une adresse du réseau local.",
      errNoTabShare: "Ce navigateur ne peut pas partager l’audio d’un onglet. Sur un téléphone, joue à voix haute pour que le micro l’entende.",
      errNoAudioTrack: "Pas de piste audio. Partage un onglet ou une fenêtre avec du son, et active le partage audio.",
      errNoAudioCtx: "Ce navigateur ne peut pas écouter. Essaie Safari ou Chrome sur ce téléphone.",
      tracksHeading: "Pistes en direct · {count}",
      nInstruments: "{n} instruments",
      nInstrument1: "1 instrument",
      nInstrument0: "0 instrument",
      laneEmpty: "Pas encore d’instrument",
      familyBass: "Basse",
      familyBody: "Corps",
      familyTune: "Mélodie",
      familyAir: "Aigu",
      familyNoise: "Bruit",
      rulerNow: "maintenant",
      liveElapsed: "{n}s en direct",
      hzWaiting: "en attente",
      hzNoPitch: "pas de hauteur claire",
      hzWaitingDevice: "en attente de cet appareil",
      peaksWaiting: "En attente du son en direct…",
      quietIdle: "Appuie sur Écouter. Micro d’abord — s’il n’y a rien autour, l’écoute passe à cet ordinateur.",
      quietPitch:
        "On entend cet appareil maintenant (son en direct, y compris En cours de lecture s’il sort du haut-parleur).",
      quietNoise: "Pas d’air clair. On dessine quand même le son en direct (voix, bruit, pièce). On n’inventera pas de mélodie.",
      quietAfter:
        "C’est calme. Si En cours de lecture est allumé, monte le haut-parleur — une page web n’a pas accès à la liste Apple En cours de lecture.",
      peaksNoise: "De l’énergie sans hauteur fredonnable — c’est quand même cet appareil, maintenant.",
      hardDefault: "Le nombre de pistes vient d’un clustering par densité. Le calme est quand même dessiné — on n’invente pas d’air.",
      hardMany:
        "Densité : {n} sources indépendantes, harmoniques repliées. Un projet psytrance peut avoir 40-80 pistes dans le DAW ; ici on compte les grappes de hauteur, pas les canaux de mixage.",
      hardOvertones: "Le direct est dur : cette note fait des copies aiguës (harmoniques), comme un piano.",
      hardClear: "Une hauteur claire, c’est le cas facile. Les chansons sont rarement si rangées.",
      hardNoise: "Nommer en direct est dur s’il n’y a pas d’air. Les pistes défilent quand même.",
      demoQuiet: "Aperçu de mise en page seulement — pas d’audio en direct. Vrai usage : écouter avec le micro de l’appareil qui joue.",
      demoStatus: "Aperçu de pistes regroupées par densité. Le temps, c’est la forme d’onde. Pas de curseur. Aucune chanson ne joue.",
      demoHard: "Exemple : plusieurs grappes de densité. Le nombre de pistes n’est pas un paramètre fixe.",
      tour0Title: "On ne jouera pas une chanson par-dessus la tienne",
      tour0Body:
        "Tout ce que cet appareil fait déjà — En cours de lecture dans le haut-parleur, un piano, des voix, du bruit — est dessiné. On ne met jamais une chanson d’exemple dessous.",
      tour1Title: "Une piste par instrument, comme dans Logic",
      tour1Body:
        "Si on entend 6 instruments, tu as 6 pistes. La basse est en bas. Le trait blanc à droite, c’est maintenant. Il n’y a pas de curseur de temps.",
      tour2Title: "Pas d’air ? On dessine quand même le son en direct",
      tour2Body:
        "Le bruit et les voix, c’est encore cet appareil, maintenant. On n’invente pas de mélodie. Si En cours de lecture est allumé, monte le haut-parleur pour que le micro l’entende.",
      tour3Title: "Une chanson, c’est un sandwich. C’est ça, l’utile.",
      tour3Body:
        "Le grave en bas, c’est la main gauche / la basse. Le milieu, c’est l’air que tu fredonnes. Le haut, c’est la brillance. Travaille une couche à la fois.",
      tour4Title: "Le superpouvoir du piano",
      tour4Body:
        "Si une hauteur claire apparaît, 440 Hz c’est la touche la. Trouve-la. Joue-la. Imite-la. Deviner en direct reste dur quand beaucoup de hauteurs s’empilent.",
      themeGroup: "Ambiance",
      themeDay: "Jour",
      themeLight: "Clair",
      themeDark: "Sombre",
      themeNight: "Soir",
      themeStealth: "Scène",
      themeAuto: "Auto",
      specAxisHz: "Hz",
      specAxisDb: "dBFS",
      pianoFull: "piano complet · La0–Do8",
    },
  };

  function detectLang() {
    try {
      const q = new URLSearchParams(global.location.search).get("lang");
      if (q === "en" || q === "fr") return q;
    } catch (e) {
      /* ignore */
    }
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "en" || saved === "fr") return saved;
    } catch (e) {
      /* ignore */
    }
    const nav = String((global.navigator && navigator.language) || "en").toLowerCase();
    return nav.startsWith("fr") ? "fr" : "en";
  }

  let current = detectLang();

  function interpolate(template, vars) {
    if (!vars) return template;
    return String(template).replace(/\{(\w+)\}/g, function (_, name) {
      return Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : "{" + name + "}";
    });
  }

  function t(key, vars) {
    const pack = STRINGS[current] || STRINGS.en;
    let value;
    if (Object.prototype.hasOwnProperty.call(pack, key)) value = pack[key];
    else if (Object.prototype.hasOwnProperty.call(STRINGS.en, key)) value = STRINGS.en[key];
    else value = key;
    return interpolate(value, vars);
  }

  function applyDom() {
    document.documentElement.lang = t("htmlLang");
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      const key = el.getAttribute("data-i18n");
      if (key) el.textContent = t(key);
    });
    document.querySelectorAll("[data-i18n-html]").forEach(function (el) {
      const key = el.getAttribute("data-i18n-html");
      if (key) el.textContent = t(key);
    });
    document.querySelectorAll("[data-i18n-alt]").forEach(function (el) {
      const key = el.getAttribute("data-i18n-alt");
      if (key) el.setAttribute("alt", t(key));
    });
    document.querySelectorAll("[data-i18n-title]").forEach(function (el) {
      const key = el.getAttribute("data-i18n-title");
      if (key) {
        document.title = t(key);
        el.textContent = t(key);
      }
    });
    document.querySelectorAll("[data-lang-switch]").forEach(function (el) {
      el.setAttribute("aria-pressed", el.getAttribute("data-lang-switch") === current ? "true" : "false");
    });
  }

  function setLang(lang) {
    current = lang === "fr" ? "fr" : "en";
    try {
      localStorage.setItem(STORAGE_KEY, current);
    } catch (e) {
      /* ignore */
    }
    applyDom();
    if (typeof global.onSymphonyLangChange === "function") {
      global.onSymphonyLangChange(current);
    }
  }

  function wireLangSwitch() {
    document.querySelectorAll("[data-lang-switch]").forEach(function (btn) {
      if (btn.getAttribute("data-i18n-wired") === "1") return;
      btn.setAttribute("data-i18n-wired", "1");
      btn.addEventListener("click", function () {
        setLang(btn.getAttribute("data-lang-switch"));
      });
    });
  }

  function boot() {
    wireLangSwitch();
    applyDom();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  global.I18N = {
    t: t,
    get lang() {
      return current;
    },
    setLang: setLang,
    applyDom: applyDom,
    wireLangSwitch: wireLangSwitch,
    detectLang: detectLang,
  };
})(window);
