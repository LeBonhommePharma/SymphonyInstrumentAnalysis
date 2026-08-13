/**
 * English + French UI copy — the first two supported languages.
 * Persist in localStorage; default from navigator.language or ?lang=en|fr.
 */
(function (global) {
  const STORAGE_KEY = "symphony-lang";

  const STRINGS = {
    en: {
      langName: "English",
      htmlLang: "en",
      hubTitle: "Symphony Instrument Analysis — see the Hertz of this device",
      hubBadge: "HTTPS · phone · 5G · silent · EN/FR",
      hubH1: "See what this device is playing",
      hubLead:
        "The page stays quiet. It only draws the live sound of this device (speaker / Now Playing through the speaker / room). One Logic-style track per instrument we can hear (up to 6). No melody? We still draw the noise. We never fake a tune.",
      hubCtaTutorial: "Open the 60-second live listen",
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
      howH1: "How this works (explained like you are 5)",
      howP1:
        "Sound is air wiggling. Slow wiggles are low notes. Fast wiggles are high notes. We count the wiggles in one second. That count is Hertz (Hz).",
      howP2: "A piano A is about 440 Hz. A low bass note can be near 110 Hz.",
      howP3:
        "Open this on the device that is already making sound, including a phone on 5G. The page stays silent. It draws the live sound of this device (speaker, Now Playing through the speaker, room). Each instrument we can tell apart gets its own waveform track (up to 6). No melody? It still draws voices and noise. It never fakes a tune.",
      howOpenTutorial: "Open the silent live tutorial",
      howBackHub: "Symphony",
      howH2Useful: "Useful",
      howSandwichIntro: "A song is a sandwich, not a blob:",
      howBoom: "Boom on the bottom = left hand / bass",
      howTune: "Tune in the middle = the part you can hum",
      howSparkle: "Sparkle on top = extra shine",
      howSandwichOut: "The tool writes that recipe in Hertz. Then you can practice one layer at a time.",
      howH2Hard: "Why doing it live is hard",
      howHardIntro: "Naming notes while the song is still happening is like reading a page someone is still flipping:",
      howHardLi1: "Many notes stack (chords)",
      howHardLi2: "Piano keys ring extra high copies called overtones",
      howHardLi3: "The computer needs a little bite of sound before it can guess",
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
      tutTitle: "60-second live listen — Symphony Instrument Analysis",
      tutBadge: "Live listen · we stay silent · EN / FR · works on 5G",
      tutH1: "See what this device is playing",
      tutLead:
        "This page never plays a song. It draws the live sound of this device: speaker, piano, room, or Now Playing if that song is coming out of the speaker. One track per instrument we can hear (up to 6). If there is no tune — only voices or noise — we still draw that live signal. We do not invent a melody.",
      btnMic: "Listen with the mic",
      btnTab: "Listen to tab/window audio",
      btnStop: "Stop",
      tourNext: "Next idea",
      crumbEli5: "ELI5",
      labelNote: "Closest piano name",
      labelHz: "Wiggles per second",
      peaksHeading: "Competing pitches",
      gateTitle: "One minute. Your sound, not ours.",
      gateBody:
        "Press listen. We will not put music underneath you. If Music / Now Playing is on this phone, turn the speaker on — that live audio is the input. No melody? We still draw the noise and voices. We never fake a tune. Each instrument we can separate gets its own track (max 6).",
      footerHint:
        "iPhone / iPad / Mac: Now Playing only reaches this page if it is coming out of this device’s speaker (or a shared tab on a computer). Apple Watch Now Playing is the same song — open this page on the iPhone that is playing it. Grown-up tool: python3 scripts/analyze_instruments.py",
      statusMicOn: "Mic on this device. Now Playing / speakers / room are the input. Nothing is played back.",
      statusTabOn: "Shared tab/window audio from this device. This page stays silent.",
      statusStopped: "Stopped. Play something on the device, then listen again.",
      statusNeedGesture: "Tap Listen once more if the browser blocked audio.",
      errMicDenied: "Mic permission was denied. On a phone, allow Microphone for this site, then tap listen again.",
      errNoMic: "This device has no microphone the browser can use.",
      errSecure:
        "Browsers only allow the mic on HTTPS (or localhost). Open the public thebonhomme.com link on this phone, not a LAN address.",
      errNoTabShare: "This browser cannot share tab audio. On a phone, use “Listen with the mic” instead.",
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
      quietIdle: "Nothing loud yet. Play Now Playing out loud on this device, or a piano, or a video.",
      quietPitch:
        "Hearing this device right now (live sound, including Now Playing if it is coming out of the speaker).",
      quietNoise: "No clear melody. Still drawing the live sound (voices, noise, room). We will not fake a tune.",
      quietAfter:
        "Quiet now. If Now Playing is on, turn this device’s speaker up — we cannot tap Apple’s Now Playing bus from a web page.",
      peaksNoise: "Energy without a hummable pitch — that is still this device, right now.",
      hardDefault: "Live naming is hard because the picture keeps moving. Watch how many pitches show up at once.",
      hardMany: "Live is hard: {n} strong pitches at once. The picture is still moving.",
      hardOvertones: "Live is hard: this note is ringing extra high copies (overtones), like a piano does.",
      hardClear: "One clear pitch is the easy case. Songs are rarely this tidy.",
      hardNoise: "Live naming is hard when there is no tune. The tracks keep rolling anyway.",
      demoQuiet: "Example layout only — not live audio. Real use: Listen with the mic on the device that is playing.",
      demoStatus: "Preview of six instrument tracks. Time is the waveform. No slider. No song is playing.",
      demoHard: "Example: six instruments at once. Live naming is hard because the picture keeps moving.",
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
    },
    fr: {
      langName: "Français",
      htmlLang: "fr",
      hubTitle: "Symphony — analyse d’instruments : voir les hertz de cet appareil",
      hubBadge: "HTTPS · téléphone · 5G · silencieux · EN/FR",
      hubH1: "Voir ce que cet appareil est en train de jouer",
      hubLead:
        "La page reste silencieuse. Elle ne dessine que le son en direct de cet appareil (haut-parleur / En cours de lecture s’il sort du haut-parleur / pièce). Une piste style Logic par instrument entendu (jusqu’à 6). Pas d’air ? On dessine quand même le bruit. On n’invente jamais de mélodie.",
      hubCtaTutorial: "Ouvrir l’écoute en direct (60 secondes)",
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
      howH1: "Comment ça marche (expliqué simplement)",
      howP1:
        "Le son, c’est de l’air qui tremble. Les tremblements lents sont des notes graves. Les rapides sont des notes aiguës. On compte les tremblements en une seconde. Ce nombre, c’est des hertz (Hz).",
      howP2: "Un la de piano, c’est environ 440 Hz. Une note de basse peut être près de 110 Hz.",
      howP3:
        "Ouvre ceci sur l’appareil qui fait déjà du son, y compris un téléphone en 5G. La page reste silencieuse. Elle dessine le son en direct de cet appareil (haut-parleur, En cours de lecture s’il sort du haut-parleur, pièce). Chaque instrument qu’on arrive à séparer a sa propre piste (jusqu’à 6). Pas d’air ? Elle dessine quand même les voix et le bruit. Elle n’invente jamais de mélodie.",
      howOpenTutorial: "Ouvrir le tutoriel silencieux en direct",
      howBackHub: "Symphony",
      howH2Useful: "Utile",
      howSandwichIntro: "Une chanson, c’est un sandwich, pas une bouillie :",
      howBoom: "Grave en bas = main gauche / basse",
      howTune: "Air au milieu = la partie que tu peux fredonner",
      howSparkle: "Brillance en haut = le petit éclat",
      howSandwichOut: "L’outil écrit cette recette en hertz. Ensuite tu peux travailler une couche à la fois.",
      howH2Hard: "Pourquoi le faire en direct est difficile",
      howHardIntro: "Nommer les notes pendant que la chanson continue, c’est comme lire une page qu’on tourne encore :",
      howHardLi1: "Plusieurs notes en même temps (accords)",
      howHardLi2: "Les touches de piano font des copies aiguës, les harmoniques",
      howHardLi3: "L’ordinateur a besoin d’un petit morceau de son avant de deviner",
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
      tutTitle: "Écoute en direct 60 secondes — Symphony analyse d’instruments",
      tutBadge: "Écoute en direct · on reste silencieux · EN / FR · marche en 5G",
      tutH1: "Voir ce que cet appareil est en train de jouer",
      tutLead:
        "Cette page ne joue jamais de chanson. Elle dessine le son en direct de cet appareil : haut-parleur, piano, pièce, ou En cours de lecture si ça sort du haut-parleur. Une piste par instrument entendu (jusqu’à 6). S’il n’y a pas d’air — seulement des voix ou du bruit — on dessine quand même ce signal. On n’invente pas de mélodie.",
      btnMic: "Écouter avec le micro",
      btnTab: "Écouter l’audio d’un onglet / d’une fenêtre",
      btnStop: "Arrêter",
      tourNext: "Idée suivante",
      crumbEli5: "Très simple",
      labelNote: "Nom de touche le plus proche",
      labelHz: "Tremblements par seconde",
      peaksHeading: "Hauteurs en concurrence",
      gateTitle: "Une minute. Ton son, pas le nôtre.",
      gateBody:
        "Appuie sur écouter. On ne mettra pas de musique sous la tienne. Si Musique / En cours de lecture joue sur ce téléphone, allume le haut-parleur — c’est ça, l’entrée. Pas d’air ? On dessine quand même le bruit et les voix. On n’invente jamais de mélodie. Chaque instrument qu’on sépare a sa piste (max. 6).",
      footerHint:
        "iPhone / iPad / Mac : En cours de lecture n’arrive ici que s’il sort du haut-parleur de cet appareil (ou d’un onglet partagé sur ordinateur). Sur Apple Watch, c’est la même chanson — ouvre cette page sur l’iPhone qui la joue. Outil adulte : python3 scripts/analyze_instruments.py",
      statusMicOn: "Micro de cet appareil. En cours de lecture / haut-parleurs / pièce = l’entrée. Rien n’est rejoué.",
      statusTabOn: "Audio d’onglet / de fenêtre partagé depuis cet appareil. Cette page reste silencieuse.",
      statusStopped: "Arrêté. Fais jouer quelque chose sur l’appareil, puis écoute à nouveau.",
      statusNeedGesture: "Appuie encore sur Écouter si le navigateur a bloqué l’audio.",
      errMicDenied: "Le micro est refusé. Sur un téléphone, autorise le micro pour ce site, puis appuie encore.",
      errNoMic: "Cet appareil n’a pas de micro que le navigateur puisse utiliser.",
      errSecure:
        "Les navigateurs n’autorisent le micro qu’en HTTPS (ou en localhost). Ouvre le lien public thebonhomme.com sur ce téléphone, pas une adresse du réseau local.",
      errNoTabShare: "Ce navigateur ne peut pas partager l’audio d’un onglet. Sur un téléphone, utilise « Écouter avec le micro ».",
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
      quietIdle: "Rien de fort pour l’instant. Fais sortir En cours de lecture du haut-parleur, ou un piano, ou une vidéo.",
      quietPitch:
        "On entend cet appareil maintenant (son en direct, y compris En cours de lecture s’il sort du haut-parleur).",
      quietNoise: "Pas d’air clair. On dessine quand même le son en direct (voix, bruit, pièce). On n’inventera pas de mélodie.",
      quietAfter:
        "C’est calme. Si En cours de lecture est allumé, monte le haut-parleur — une page web n’a pas accès à la liste Apple En cours de lecture.",
      peaksNoise: "De l’énergie sans hauteur fredonnable — c’est quand même cet appareil, maintenant.",
      hardDefault: "Nommer en direct est difficile parce que l’image n’arrête pas de bouger. Regarde combien de hauteurs arrivent en même temps.",
      hardMany: "Le direct est dur : {n} hauteurs fortes en même temps. L’image bouge encore.",
      hardOvertones: "Le direct est dur : cette note fait des copies aiguës (harmoniques), comme un piano.",
      hardClear: "Une hauteur claire, c’est le cas facile. Les chansons sont rarement si rangées.",
      hardNoise: "Nommer en direct est dur s’il n’y a pas d’air. Les pistes défilent quand même.",
      demoQuiet: "Aperçu de mise en page seulement — pas d’audio en direct. Vrai usage : écouter avec le micro de l’appareil qui joue.",
      demoStatus: "Aperçu de six pistes d’instruments. Le temps, c’est la forme d’onde. Pas de curseur. Aucune chanson ne joue.",
      demoHard: "Exemple : six instruments à la fois. Nommer en direct est difficile parce que l’image bouge.",
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
