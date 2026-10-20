// UI beta: an alternative table layout ("football pitch": me on the left, the
// opponent on the right), toggled from the home options or the in-game menu.
// It is a relayout of the existing table, not a second client: every panel,
// pile, card and handler of app.js stays the one doing the work. This file
// only (1) moves the existing panels into two side columns, (2) places the
// battlefield cards by zone instead of by their x/y, (3) turns a drop on the
// field into a position inside the right zone, and (4) draws the field
// chrome (zones, totals, priority wheel, stalemate strip, merged chat/log).
(() => {
  "use strict";

  const ENABLED_KEY = "ko_ui_beta";
  const THEME_KEY = "ko_ui_beta_theme";
  const THEMES = ["current", "sand", "dark"];
  const CARD_W = 150;
  const CARD_H = 210;
  const RATIO = CARD_H / CARD_W;
  const RING = ["phlegmatic", "vitreous", "melancholic", "capricious", "choleric"];
  const DOMINATES = {
    phlegmatic: ["vitreous", "capricious"],
    vitreous: ["melancholic", "choleric"],
    melancholic: ["capricious", "phlegmatic"],
    capricious: ["choleric", "vitreous"],
    choleric: ["phlegmatic", "melancholic"],
  };

  Object.assign(ui.fr, {
    ubTurn: "Tour",
    ubRotate: "Tournez votre appareil en mode paysage pour jouer.",
    ubPassed: "a passé",
    ubTargetHint: "Cible un joueur : son côté du terrain, son total, son nom ou son icône.",
    ubToolDraw: "Dessin",
    ubToolCreate: "Créer (jeton, essence, dé)",
    ubChoosePlayer: "Choisis un joueur",
    ubClickPlayer: "Clique sur le côté du terrain, le total, le nom ou l’icône du joueur visé.",
    ubClickCard: "Clique sur une des cartes en surbrillance sur le terrain.",
    ubDragDestination: "Glisse la carte dans ta colonne Interzone, ou dans ta colonne (sous ton deck).",
    ubDragToDeck: "Glisse une carte en surbrillance sur ton deck (ou clique dessus).",
    ubShowChoicePanel: "Voir les options",
    ubHideChoicePanel: "Choisir sur le terrain",
    ubOption: "Nouvelle table",
    ubOptionHint: "Table par défaut : moi à gauche, l’adversaire à droite. Décocher pour revenir à l’ancienne table (aussi depuis le menu de la partie).",
    ubMenuToggle: "Nouvelle table",
    ubTheme: "Thème",
    ubThemeCurrent: "Actuel",
    ubThemeSand: "Crème / sable",
    ubThemeDark: "Foncé",
    ubInterzone: "Interzone",
    ubWills: "Volontés",
    ubConfrontation: "Zone de Confrontation",
    ubStalemate: "Impasse",
    ubStalemateTitle: "Zone d’Impasse",
    ubStalemateHint: "Clique en dehors pour refermer.",
    ubStalemateOf: "À {player}",
    ubStaleAtStake: "{points} points en jeu",
    ubPts: "pts",
    ubNoCard: "Aucune carte",
    ubEnlarge: "Agrandir",
    ubStack: "La Pile",
    ubStackEmpty: "La Pile est vide.",
    ubStackOpen: "Agrandir la Pile",
    ubOn: "activé",
    ubOff: "désactivé",
    ubEnable: "Activer",
    ubDisable: "Désactiver",
    ubAutoSkipOnAsk: "Activer le passage automatique des phases où vous n'avez rien à faire ?",
    ubAutoSkipOffAsk: "Désactiver le passage automatique des phases ? Vous passerez chaque phase vous-même.",
    ubManualStackEmpty: "Glisse une carte ici pour la jouer dans la Pile, puis sors-la pour la résoudre.",
    ubPlayToStack: "Jouer dans la Pile",
    ubPutInStack: "Mettre dans la Pile",
    ubTakeFromStack: "Sortir de la Pile",
    ubSendToStalemate: "Envoyer en Zone d’Impasse",
    ubStalemateDrop: "Zone d’Impasse",
    ubTabAll: "Tout",
    ubTabChat: "Chat",
    ubObserverTag: "Observateurs",
    ubObserverPlaceholder: "Message aux observateurs…",
    ubTabLog: "Actions",
    ubNothingYet: "Rien pour l’instant.",
    ubFold: "Replier",
    ubUnfold: "Déplier",
    ubPilesOf: "Decks de",
    ubScoreAdjust: "Ajuster les points",
    ubReceptacleShort: "Réceptacle",
    ubLastOppAction: "Dernière action de {player} :",
    ubInterzoneShort: "Inter.",
    ubWillsShort: "Vol.",
    ubAutoSkipShort: "Passer auto",
    ubAppShort: "Kartomantik",
    ubChatShort: "Msg",
    ubTabLogShort: "Act.",
    ubShowOppPiles: "Afficher les piles adverses",
    ubHideOppPiles: "Replier les piles adverses",
    ubDropHint: "Lâche une carte de ta main n’importe où sur le terrain",
    ubWaitingOpponent: "En attente de l’adversaire",
    ubFreeSlot: "libre",
    ubReceptacle: "Réceptacle",
    ubBonus: "Bonus",
    ubTotal: "Total",
    ubPriority: "Priorité",
    ubHandCards: "cartes en main",
    ubPhaseWaiting: "Attente…",
    ubFirstManifestation: "Première Manifestation",
  });
  Object.assign(ui.en, {
    ubTurn: "Turn",
    ubRotate: "Turn your device to landscape to play.",
    ubPassed: "passed",
    ubTargetHint: "Target a player: their side of the field, their total, their name or their icon.",
    ubToolDraw: "Drawing",
    ubToolCreate: "Create (token, essence, die)",
    ubChoosePlayer: "Choose a player",
    ubClickPlayer: "Click the targeted player's side of the field (or their name).",
    ubClickCard: "Click one of the highlighted cards on the field.",
    ubDragDestination: "Drag the card into your Interzone column, or into your side column (under your deck).",
    ubDragToDeck: "Drag a highlighted card onto your deck (or click it).",
    ubShowChoicePanel: "See the options",
    ubHideChoicePanel: "Choose on the field",
    ubOption: "New table",
    ubOptionHint: "Default table: me on the left, the opponent on the right. Untick to go back to the classic table (also from the game menu).",
    ubMenuToggle: "New table",
    ubTheme: "Theme",
    ubThemeCurrent: "Current",
    ubThemeSand: "Cream / sand",
    ubThemeDark: "Dark",
    ubInterzone: "Interzone",
    ubWills: "Wills",
    ubConfrontation: "Confrontation Zone",
    ubStalemate: "Stalemate",
    ubStalemateTitle: "Stalemate Zone",
    ubStalemateHint: "Click outside to close.",
    ubStalemateOf: "{player}’s",
    ubStaleAtStake: "{points} points at stake",
    ubPts: "pts",
    ubNoCard: "No card",
    ubEnlarge: "Enlarge",
    ubStack: "Stack",
    ubStackEmpty: "The Stack is empty.",
    ubStackOpen: "Enlarge the Stack",
    ubOn: "on",
    ubOff: "off",
    ubEnable: "Turn on",
    ubDisable: "Turn off",
    ubAutoSkipOnAsk: "Automatically skip the phases where you have nothing to do?",
    ubAutoSkipOffAsk: "Stop skipping phases automatically? You will pass each phase yourself.",
    ubManualStackEmpty: "Drop a card here to play it on the Stack, then drag it out to resolve it.",
    ubPlayToStack: "Play on the Stack",
    ubPutInStack: "Put on the Stack",
    ubTakeFromStack: "Take off the Stack",
    ubSendToStalemate: "Send to the Stalemate Zone",
    ubStalemateDrop: "Stalemate Zone",
    ubTabAll: "All",
    ubTabChat: "Chat",
    ubObserverTag: "Observers",
    ubObserverPlaceholder: "Message to the observers…",
    ubTabLog: "Actions",
    ubNothingYet: "Nothing yet.",
    ubFold: "Fold",
    ubUnfold: "Unfold",
    ubPilesOf: "Piles of",
    ubScoreAdjust: "Adjust the points",
    ubReceptacleShort: "Vessel",
    ubLastOppAction: "Last action by {player}:",
    ubInterzoneShort: "Inter.",
    ubWillsShort: "Wills",
    ubAutoSkipShort: "Auto-skip",
    ubAppShort: "Kartomantik",
    ubChatShort: "Msg",
    ubTabLogShort: "Act.",
    ubShowOppPiles: "Show the opponent’s piles",
    ubHideOppPiles: "Fold the opponent’s piles",
    ubDropHint: "Drop a card from your hand anywhere on the field",
    ubWaitingOpponent: "Waiting for the opponent",
    ubFreeSlot: "free",
    ubReceptacle: "Vessel",
    ubBonus: "Bonus",
    ubTotal: "Total",
    ubPriority: "Priority",
    ubHandCards: "cards in hand",
    ubPhaseWaiting: "Waiting…",
    ubFirstManifestation: "First Manifestation",
  });
  Object.assign(ui.it, {
    ubTurn: "Turno",
    ubRotate: "Ruota il dispositivo in orizzontale per giocare.",
    ubPassed: "ha passato",
    ubTargetHint: "Scegli un giocatore: il suo lato del campo, il suo totale, il nome o la sua icona.",
    ubToolDraw: "Disegno",
    ubToolCreate: "Crea (segnalino, essenza, dado)",
    ubChoosePlayer: "Scegli un giocatore",
    ubClickPlayer: "Clicca sul lato del campo (o sul nome) del giocatore bersaglio.",
    ubClickCard: "Clicca su una delle carte evidenziate sul campo.",
    ubDragDestination: "Trascina la carta nella colonna Interzona, o nella tua colonna (sotto il mazzo).",
    ubDragToDeck: "Trascina una carta evidenziata sul tuo mazzo (o cliccala).",
    ubShowChoicePanel: "Vedi le opzioni",
    ubHideChoicePanel: "Scegli sul campo",
    ubOption: "Nuovo tavolo",
    ubOptionHint: "Tavolo predefinito: io a sinistra, l’avversario a destra. Togli la spunta per tornare al tavolo classico (anche dal menu della partita).",
    ubMenuToggle: "Nuovo tavolo",
    ubTheme: "Tema",
    ubThemeCurrent: "Attuale",
    ubThemeSand: "Crema / sabbia",
    ubThemeDark: "Scuro",
    ubInterzone: "Interzona",
    ubWills: "Volontà",
    ubConfrontation: "Zona di Confronto",
    ubStalemate: "Stallo",
    ubStalemateTitle: "Zona di Stallo",
    ubStalemateHint: "Clicca fuori per chiudere.",
    ubStalemateOf: "Di {player}",
    ubStaleAtStake: "{points} punti in palio",
    ubPts: "pt",
    ubNoCard: "Nessuna carta",
    ubEnlarge: "Ingrandisci",
    ubStack: "Stack",
    ubStackEmpty: "Lo Stack è vuoto.",
    ubStackOpen: "Ingrandisci lo Stack",
    ubOn: "attivo",
    ubOff: "disattivo",
    ubEnable: "Attiva",
    ubDisable: "Disattiva",
    ubAutoSkipOnAsk: "Saltare automaticamente le fasi in cui non hai nulla da fare?",
    ubAutoSkipOffAsk: "Smettere di saltare le fasi automaticamente? Passerai ogni fase da solo.",
    ubManualStackEmpty: "Trascina qui una carta per giocarla nello Stack, poi trascinala fuori per risolverla.",
    ubPlayToStack: "Gioca nello Stack",
    ubPutInStack: "Metti nello Stack",
    ubTakeFromStack: "Togli dallo Stack",
    ubSendToStalemate: "Manda nella Zona di Stallo",
    ubStalemateDrop: "Zona di Stallo",
    ubTabAll: "Tutto",
    ubTabChat: "Chat",
    ubObserverTag: "Osservatori",
    ubObserverPlaceholder: "Messaggio agli osservatori…",
    ubTabLog: "Azioni",
    ubNothingYet: "Niente per ora.",
    ubFold: "Chiudi",
    ubUnfold: "Apri",
    ubPilesOf: "Pile di",
    ubScoreAdjust: "Regola i punti",
    ubReceptacleShort: "Bacino",
    ubLastOppAction: "Ultima azione di {player}:",
    ubInterzoneShort: "Inter.",
    ubWillsShort: "Vol.",
    ubAutoSkipShort: "Salta auto",
    ubAppShort: "Kartomantik",
    ubChatShort: "Msg",
    ubTabLogShort: "Az.",
    ubShowOppPiles: "Mostra le pile avversarie",
    ubHideOppPiles: "Chiudi le pile avversarie",
    ubDropHint: "Rilascia una carta della mano ovunque sul campo",
    ubWaitingOpponent: "In attesa dell’avversario",
    ubFreeSlot: "libero",
    ubReceptacle: "Bacino Empatico",
    ubBonus: "Bonus",
    ubTotal: "Totale",
    ubPriority: "Priorità",
    ubHandCards: "carte in mano",
    ubPhaseWaiting: "Attesa…",
    ubFirstManifestation: "Prima Manifestazione",
  });

  const ICONS = {
    first: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.6 5.6 6 .7-4.5 4.1 1.3 6L12 16.4l-5.4 3 1.3-6-4.5-4.1 6-.7Z"/></svg>',
    chevron: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>',
    rotate: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="2.5" width="10" height="17" rx="2"/><path d="M11 16.5h2M20.5 14a8.5 8.5 0 0 1-6 7.5m0 0 2.2-.4m-2.2.4.6-2.2"/></svg>',
    send: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12 20 4l-6 16-3-7-7-1Z"/></svg>',
    log: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14M5 10h14M5 15h9M5 20h6"/></svg>',
    pen: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 20 1-4L16 5l3 3L8 19l-4 1ZM14 7l3 3"/></svg>',
    erase: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="2" stroke-dasharray="3 3"/></svg>',
    undo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/></svg>',
    redo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 14 5-5-5-5"/><path d="M20 9H10a6 6 0 0 0 0 12h3"/></svg>',
    trash: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
    plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
    token: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="3" width="11" height="15" rx="2"/><path d="M18 14v6M15 17h6"/></svg>',
    essence: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3c3 4 6 7 6 11a6 6 0 0 1-12 0c0-4 3-7 6-11Z"/></svg>',
    dice: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"/><circle cx="9" cy="9" r=".8"/><circle cx="15" cy="15" r=".8"/><circle cx="15" cy="9" r=".8"/><circle cx="9" cy="15" r=".8"/></svg>',
    palette: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 0 0 0 18c1.4 0 2-1 2-2 0-1.6-1.6-2 0-3h2a5 5 0 0 0 5-5c0-4.4-4-8-9-8Z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10.5" cy="7" r="1"/><circle cx="15" cy="7.5" r="1"/></svg>',
    skip: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 6 7 6-7 6ZM13 6l7 6-7 6Z"/></svg>',
    chat: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4Z"/></svg>',
    all: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v8H9l-5 4ZM8 17h8l4 3v-7"/></svg>',
    interzone: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="2.5" width="10" height="5.5" rx="1"/><rect x="7" y="9.25" width="10" height="5.5" rx="1"/><rect x="7" y="16" width="10" height="5.5" rx="1"/></svg>',
    wills: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/></svg>',
    deck: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="3" width="12" height="16" rx="2"/><path d="M8 21h10a2 2 0 0 0 2-2V7"/></svg>',
    limbo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 18a5 5 0 1 1 1.4-9.8A6 6 0 0 1 19.5 11 3.5 3.5 0 0 1 18 18Z"/></svg>',
    exile: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="m6.5 6.5 11 11"/></svg>',
    vessel: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3h8M9 3v4l-4 6a6 6 0 0 0 5 8h4a6 6 0 0 0 5-8l-4-6V3"/></svg>',
    eye: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.6"/></svg>',
  };

  const local = {
    chatTab: "all",
    chatFolded: false,
    unread: 0,
    seenChat: null,
    staleOpen: false,
    oppPilesOpen: null,
    geometry: null,
    placement: null,
    homes: new Map(),
    built: false,
    peekTimer: null,
    peekEl: null,
    resizeFrame: 0,
    system: [],
    iconSwaps: [],
    choice: null,
    choiceKey: "",
    choicePanelShown: "",
    choiceDrag: null,
    pingTimer: null,
    prevHandH: null,
    handSeen: null,
    handHidden: new Map(),
    handRevealTimer: null,
    immersiveTried: false,
    destinationShownAt: 0,
    inGame: false,
    longPress: null,
    swallowMenuUntil: 0,
  };

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const qs = (selector, root = document) => root.querySelector(selector);

  // the new table is the default UI (players, tournament players and spectators):
  // only an explicit choice made since it became the default switches it off
  const DEFAULT_KEY = "ko_ui_default_v2";
  function enabled() {
    try {
      if (localStorage.getItem(DEFAULT_KEY) !== "1") {
        // an opt-out from the beta era does not survive the switch
        localStorage.removeItem(ENABLED_KEY);
        localStorage.setItem(DEFAULT_KEY, "1");
      }
      return localStorage.getItem(ENABLED_KEY) !== "0";
    } catch (error) { return true; }
  }
  function setEnabled(on) {
    try { localStorage.setItem(ENABLED_KEY, on ? "1" : "0"); } catch (error) { /* private mode: session only */ }
  }
  function theme() {
    let value = "current";
    try { value = localStorage.getItem(THEME_KEY) || "current"; } catch (error) { /* default */ }
    return THEMES.includes(value) ? value : "current";
  }
  function active() {
    return Boolean(document.getElementById("gameScreen")?.classList.contains("ui-beta"));
  }
  function rulesOn() {
    return Boolean(latestState?.rulesEngine?.enabled);
  }

  // ------------------------------------------------------------ label fitting

  // A label that does not fit first shows its short form, then its icon (the
  // full text stays as tooltip). Names (players, cards) shrink their font
  // instead and are only cut once at the minimum size.
  const FIT_LABELS = {
    interzone: () => ({ full: t("ubInterzone"), short: t("ubInterzoneShort"), icon: ICONS.interzone }),
    wills: () => ({ full: t("ubWills"), short: t("ubWillsShort"), icon: ICONS.wills }),
    autoskip: () => ({ full: t("rulesAutoSkipLabel"), short: t("ubAutoSkipShort"), icon: ICONS.skip }),
    brand: () => ({ full: t("appName"), short: t("ubAppShort"), icon: "" }),
    tabAll: () => ({ full: t("ubTabAll"), short: t("ubTabAll"), icon: ICONS.all }),
    tabChat: () => ({ full: t("ubTabChat"), short: t("ubTabChat"), icon: ICONS.chat }),
    tabLog: () => ({ full: t("ubTabLog"), short: t("ubTabLogShort"), icon: ICONS.log }),
    "pile-deck": () => ({ full: t("deck"), short: t("deck"), icon: ICONS.deck }),
    "pile-graveyard": () => ({ full: t("graveyard"), short: t("graveyard"), icon: ICONS.limbo }),
    "pile-exile": () => ({ full: t("exile"), short: t("exile"), icon: ICONS.exile }),
    "pile-receptacle": () => ({ full: t("receptacle"), short: t("ubReceptacleShort"), icon: ICONS.vessel }),
  };
  const overflows = (node) => node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1;

  function fitLabel(node) {
    const spec = FIT_LABELS[node.dataset.fit]?.();
    if (!spec) return;
    node.classList.remove("ub-fit-icon");
    node.removeAttribute("title");
    node.textContent = spec.full;
    if (!overflows(node)) return;
    node.title = spec.full;
    if (spec.short !== spec.full) {
      node.textContent = spec.short;
      if (!overflows(node)) return;
    }
    node.innerHTML = spec.icon;
    node.classList.add("ub-fit-icon");
    node.setAttribute("aria-label", spec.full);
  }

  // shrink a name until it fits (or reaches `min` px), the text stays whole
  function fitName(node, min = 10) {
    node.style.fontSize = "";
    if (!overflows(node)) return;
    let size = parseFloat(getComputedStyle(node).fontSize) || 14;
    while (overflows(node) && size > min) {
      size = Math.max(min, size - 1);
      node.style.fontSize = `${size}px`;
    }
  }

  function fitCardNames(root = document) {
    root.querySelectorAll(".rules-choice-card > span, .sideboard-card strong").forEach((node) => {
      if (node.offsetParent) fitName(node, 9);
    });
  }

  function fitOppBar() {
    const bar = document.getElementById("ubOppBar");
    const name = bar?.querySelector(".v");
    if (!name) return;
    bar.classList.remove("ub-fit-short", "ub-fit-icons", "ub-fit-tight", "ub-fit-noname");
    name.style.fontSize = "";
    if (!overflows(name)) return;
    bar.classList.add("ub-fit-short");
    if (!overflows(name)) return;
    bar.classList.add("ub-fit-icons");
    if (!overflows(name)) return;
    bar.classList.add("ub-fit-tight");
    fitName(name, 9);
    // the opponent is named in the box just above: an unreadable stub goes
    if (overflows(name)) bar.classList.add("ub-fit-noname");
  }

  function fitWho() {
    for (const node of document.querySelectorAll("#ubWhoMe, #ubWhoOpp")) {
      const name = node.querySelector(".ub-name");
      const activity = node.querySelector(".ub-activity");
      if (!name) continue;
      if (activity) activity.hidden = false;
      node.classList.remove("ub-fit-tight");
      name.style.fontSize = "";
      if (!overflows(name)) continue;
      if (activity) activity.hidden = true;
      if (!overflows(name)) continue;
      node.classList.add("ub-fit-tight");
      fitName(name, 10);
    }
  }

  function fitChatPlaceholder() {
    const input = document.getElementById("ubChatInput");
    if (!input) return;
    const full = input.dataset.fullPlaceholder || input.placeholder;
    input.dataset.fullPlaceholder = full;
    const style = getComputedStyle(input);
    const room = input.clientWidth - parseFloat(style.paddingLeft || 0) - parseFloat(style.paddingRight || 0);
    const ctx = (local.measure ||= document.createElement("canvas").getContext("2d"));
    ctx.font = `${style.fontSize} ${style.fontFamily}`;
    const fits = (text) => ctx.measureText(text).width <= room;
    input.placeholder = fits(full) ? full : fits(t("ubChatShort")) ? t("ubChatShort") : "✎";
    input.title = full;
  }

  function fitLabels() {
    for (const [id, key] of [["brandText", "brand"], ["rulesAutoSkipLabel", "autoskip"]]) {
      const node = document.getElementById(id);
      if (node) node.dataset.fit = key;
    }
    document.querySelectorAll("#gameScreen .ub-piles .field-pile[data-zone] .pile-label").forEach((node) => {
      node.dataset.fit = `pile-${node.closest("[data-zone]").dataset.zone}`;
    });
    document.querySelectorAll("#gameScreen [data-fit]").forEach(fitLabel);
    fitWho();
    fitOppBar();
    fitChatPlaceholder();
    fitCardNames();
    const priority = document.getElementById("rulesPriority");
    if (priority) {
      priority.style.fontSize = "";
      if (document.getElementById("gameScreen").classList.contains("ub-phone")) fitName(priority, 8);
    }
  }

  // back on the classic table: full texts, no inline sizes
  function unfitLabels() {
    document.querySelectorAll("#gameScreen [data-fit]").forEach((node) => {
      const spec = FIT_LABELS[node.dataset.fit]?.();
      node.classList.remove("ub-fit-icon");
      node.removeAttribute("title");
      if (spec) node.textContent = spec.full;
      delete node.dataset.fit;
    });
    document.querySelectorAll("#gameScreen .ub-name, #ubOppBar .v").forEach((node) => { node.style.fontSize = ""; });
  }

  // ------------------------------------------------------------ last opponent action

  // Once its spotlight is gone, the opponent's last declared action stays
  // pointed at: its card on the field keeps an outline (a pulse when new) and
  // the empty Stack names it, with its targets.
  function lastOpponentAction() {
    if (!rulesOn() || isObserver) return null;
    const known = local.lastOpp;
    const newest = Math.max(0, ...(latestState.recentLog || []).map((entry) => Number(entry.sequence) || 0));
    if (known && newest < Number(known.sequence)) local.lastOpp = null; // a new session
    for (const entry of latestState.recentLog || []) {
      if (entry.type !== "rules_action_declared" || !entry.actorId || entry.actorId === myPlayerId || !entry.details?.source?.cardId) continue;
      if (!local.lastOpp || Number(entry.sequence) > Number(local.lastOpp.sequence)) local.lastOpp = entry;
    }
    return local.lastOpp;
  }

  function markLastOpponentAction() {
    const entry = lastOpponentAction();
    document.querySelectorAll("#battlefield .ub-last-opp").forEach((node) => node.classList.remove("ub-last-opp", "ub-last-opp-fresh"));
    if (!entry) return;
    const source = entry.details.source;
    const items = latestState.battlefield || [];
    const item = items.find((candidate) => candidate.id === source.itemId)
      || items.filter((candidate) => candidate.cardId === source.cardId && (candidate.controllerId || candidate.ownerId) === entry.actorId).pop();
    const node = item ? document.querySelector(`#battlefield .bf-card[data-item-id="${CSS.escape(item.id)}"]`) : null;
    if (!node) return;
    node.classList.add("ub-last-opp");
    node.style.setProperty("--last-opp", playerColor(entry.actorId));
    if (local.lastOppPulsed !== entry.sequence) {
      local.lastOppPulsed = entry.sequence;
      node.classList.add("ub-last-opp-fresh");
    }
  }

  function lastOpponentActionHtml() {
    const entry = lastOpponentAction();
    if (!entry) return "";
    const targets = (entry.details.targets || []).map((target) => rulesActionTargetRef(target)).join(", ");
    return `<span class="ub-last-opp-line" style="--last-opp:${esc(playerColor(entry.actorId))}">${esc(rulesText("ubLastOppAction", { player: rulesPlayerName(entry.actorId) }))} `
      + `${rulesActionCardRef(entry.details.source.cardId)}${targets ? ` <span class="ub-last-opp-arrow" aria-hidden="true">→</span> ${targets}` : ""}</span>`;
  }

  // ------------------------------------------------------------ departures

  // A card that leaves the field without an effect staging it (a manual move,
  // a rule the effects do not animate) flies to the pile it went to.
  const DEPARTURE_ZONES = ["graveyard", "exile", "receptacle", "hand", "deck"];

  function boardSnapshot() {
    const items = new Map((latestState?.battlefield || []).map((item) => [item.id, item]));
    const nodes = new Map();
    document.querySelectorAll("#battlefield .bf-card[data-item-id]").forEach((node) => {
      const rect = node.getBoundingClientRect();
      if (rect.width) nodes.set(node.dataset.itemId, { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
    });
    return { items: local.boardItems || items, nodes, counts: local.boardCounts || pileCounts() };
  }

  function pileCounts() {
    const counts = {};
    Object.values(latestState?.players || {}).forEach((player) => {
      counts[player.id] = Object.fromEntries(DEPARTURE_ZONES.map((zone) => [zone, pileCount(player, zone)]));
    });
    return counts;
  }

  function departureZone(item, before) {
    const players = Object.values(latestState?.players || {});
    for (const player of players) {
      for (const zone of DEPARTURE_ZONES) {
        if ((player.zones?.[zone]?.cards || []).includes(item.cardId)) return { playerId: player.id, zone, visible: true };
      }
    }
    // a hidden zone: the one of the owner that grew
    const owner = latestState?.players?.[item.ownerId];
    const zone = owner && DEPARTURE_ZONES.find((name) => pileCount(owner, name) > (before.counts[owner.id]?.[name] ?? Infinity));
    return zone ? { playerId: owner.id, zone, visible: false } : null;
  }

  function flyDepartures(before) {
    const now = new Map((latestState?.battlefield || []).map((item) => [item.id, item]));
    local.boardItems = now;
    local.boardCounts = pileCounts();
    if (typeof playRulesVfxFlight !== "function" || rulesVfxReducedMotion()) return;
    const claims = local.vfxClaims && Date.now() - local.vfxClaims.at < 4000 ? local.vfxClaims.ids : new Set();
    const dropped = local.droppedItem && Date.now() - local.droppedItem.at < 1500 ? local.droppedItem.id : null;
    let flights = 0;
    for (const [itemId, item] of before.items) {
      if (now.has(itemId) || flights >= 8) continue;
      const origin = before.nodes.get(itemId);
      if (!origin || !item.cardId || item.isTokenCard || itemId === dropped || claims.has(itemId) || claims.has(item.cardId)) continue;
      const destination = departureZone(item, before);
      if (!destination) continue;
      const target = rulesVfxPileCenter(destination.playerId, destination.zone) || rulesVfxPlayerOrigin(destination.playerId);
      const shown = item.faceUp && destination.visible;
      playRulesVfxFlight(shown ? "effect-card" : "draw-card", origin, target, { cardId: shown ? item.cardId : null, index: flights });
      flights += 1;
    }
  }

  // ------------------------------------------------------------ Vessel points (manual play)

  // The -10..+10 buttons of a Vessel open from a "±" button on its tile (a finger
  // cannot hover), float over the page, and stay open while points are added.
  const scoreOwner = (adjust) => adjust.querySelector("[data-score-delta]")?.dataset.scoreDelta.split(":")[0];
  function decorateScoreAdjust() {
    document.querySelectorAll(".ub-piles .field-pile").forEach((pile) => {
      const adjust = pile.querySelector(":scope > .pile-score-adjust");
      if (!adjust) return;
      const owner = scoreOwner(adjust);
      let toggle = pile.querySelector(":scope > .ub-score-toggle");
      if (!toggle) {
        toggle = el("button", "ub-score-toggle", "±");
        toggle.type = "button";
        toggle.addEventListener("click", (event) => {
          event.stopPropagation();
          local.scoreOpen = local.scoreOpen === owner ? null : owner;
          syncScoreAdjust();
        });
        pile.appendChild(toggle);
      }
      toggle.title = t("ubScoreAdjust");
      toggle.setAttribute("aria-label", t("ubScoreAdjust"));
    });
    syncScoreAdjust();
  }
  function syncScoreAdjust() {
    document.querySelectorAll(".ub-piles .field-pile > .pile-score-adjust").forEach((adjust) => {
      const open = Boolean(local.scoreOpen) && local.scoreOpen === scoreOwner(adjust);
      const toggle = adjust.parentElement.querySelector(":scope > .ub-score-toggle");
      adjust.classList.toggle("ub-open", open);
      toggle?.setAttribute("aria-expanded", String(open));
      if (open) floatOver(adjust, toggle || adjust.parentElement, { above: false });
      else unfloat(adjust);
    });
  }

  // ------------------------------------------------------------ players

  // the left half belongs to me; an observer gets the first seat on the left
  function sidePlayers() {
    const players = Object.values(latestState?.players || {});
    let me = !isObserver && myPlayerId ? players.find((player) => player.id === myPlayerId) : null;
    if (!me) me = players.find((player) => (player.seat || 0) === mySeat()) || players[0] || null;
    const opp = players.find((player) => player !== me) || null;
    return { me, opp };
  }
  function sideOfSeat(seat) {
    return (seat || 0) === mySeat() ? "me" : "opp";
  }
  function seatOfPlayer(playerId) {
    return latestState?.players?.[playerId]?.seat || 0;
  }

  // ------------------------------------------------------------ zones

  // Same slots and rectangles as the server's rules_auto_layout, so a beta drop
  // always lands where the engine (or a manual player) expects that zone to be.
  function classicSlot(zone, seat, index) {
    const top = seat === 1;
    if (zone === "interzone") return { x: 445 + (index % 3) * 305 + Math.floor(index / 3) * 20, y: (top ? 285 : 1064) + Math.floor(index / 3) * 14 };
    if (zone === "confrontation") {
      const lift = Math.floor(index / 4) * 30;
      return { x: 445 + (index % 4) * 215 + Math.floor(index / 4) * 40, y: (top ? 525 : 800) + (top ? lift : -lift) };
    }
    if (zone === "stalemate") return { x: 1429 + Math.floor(index / 2) * 40, y: 560 + (index % 2) * 230 };
    return { x: 445 + (index % 5) * 170, y: (top ? 45 : 1300) + Math.floor(index / 5) * 14 };
  }
  function classicRect(zone, seat) {
    const top = seat === 1;
    if (zone === "interzone") return top ? [415, 271, 1322, 498] : [415, 1050, 1322, 1278];
    if (zone === "confrontation") return top ? [415, 510, 1322, 773] : [415, 773, 1322, 1037];
    if (zone === "stalemate") return [1354, 543, 1703, 1008];
    return top ? [415, 35, 1322, 270] : [415, 1290, 1322, 1515];
  }
  // manual mode has no fieldZone: the zone is read back from where the card sits
  function inferZone(x, y) {
    const cx = Number(x || 0) + CARD_W / 2;
    const cy = Number(y || 0) + CARD_H / 2;
    const inside = (rect) => cx >= rect[0] && cx <= rect[2] && cy >= rect[1] && cy <= rect[3];
    if (inside(classicRect("stalemate", 0))) return { zone: "stalemate", seat: cy < 775 ? 1 : 0 };
    for (const zone of ["confrontation", "interzone", "field"]) {
      for (const seat of [0, 1]) if (inside(classicRect(zone, seat))) return { zone, seat };
    }
    const seat = cy < 775 ? 1 : 0;
    return { zone: cx >= 415 && cx <= 1322 ? "confrontation" : "field", seat };
  }
  function slotOrder(zone, seat, x, y) {
    let best = 0;
    let bestDistance = Infinity;
    for (let index = 0; index < 24; index += 1) {
      const slot = classicSlot(zone, seat, index);
      const distance = (slot.x - x) ** 2 + (slot.y - y) ** 2;
      if (distance < bestDistance - 0.5) { best = index; bestDistance = distance; }
    }
    return best;
  }

  function firstManifestationIds() {
    return new Set(Object.values(latestState?.rulesEngine?.firstManifestationItemIds || {}));
  }

  // zone: confrontation | interzone | will (Volontés) | stalemate
  function classify(item, firstIds) {
    let zone = item.fieldZone || (firstIds.has(item.id) ? "confrontation" : null);
    let seat;
    if (zone) {
      seat = seatOfPlayer(battlefieldItemControllerId(item));
    } else {
      const inferred = inferZone(item.x, item.y);
      zone = inferred.zone;
      seat = rulesOn() ? seatOfPlayer(battlefieldItemControllerId(item)) : inferred.seat;
    }
    if (zone === "stalemate") seat = seatOfPlayer(item.ownerId);
    const classicZone = zone === "field" ? "field" : zone;
    return {
      zone: zone === "field" ? "will" : zone,
      seat,
      side: sideOfSeat(seat),
      order: slotOrder(classicZone, seat, Number(item.x || 0), Number(item.y || 0)),
    };
  }

  function groupItems() {
    const firstIds = firstManifestationIds();
    const groups = {
      me: { confrontation: [], interzone: [], will: [] },
      opp: { confrontation: [], interzone: [], will: [] },
      stalemate: [],
      stacked: [],
      manualStack: [],
    };
    const info = new Map();
    (latestState?.battlefield || []).forEach((item, index) => {
      // manual play: a card in the Stack is shown in the Stack panel, not on the field
      if (item.manualStack && !rulesOn()) {
        groups.manualStack.push(item);
        return;
      }
      const entry = { item, index, first: firstIds.has(item.id), ...classify(item, firstIds) };
      info.set(item.id, entry);
      if (item.stackedOn && (latestState.battlefield || []).some((other) => other.id === item.stackedOn)) {
        groups.stacked.push(entry);
        return;
      }
      if (entry.zone === "stalemate") groups.stalemate.push(entry);
      else groups[entry.side][entry.zone].push(entry);
    });
    const byOrder = (a, b) => (b.first - a.first) || (a.order - b.order) || (a.index - b.index);
    for (const side of ["me", "opp"]) for (const zone of ["confrontation", "interzone", "will"]) groups[side][zone].sort(byOrder);
    groups.stalemate.sort(byOrder);
    return { groups, info };
  }

  // ------------------------------------------------------------ geometry

  function fit(width, height, count, { maxW = 240, gap = 10, maxCols = 99 } = {}) {
    let best = { cols: 1, w: 24 };
    const n = Math.max(count, 1);
    for (let cols = 1; cols <= Math.min(n, maxCols); cols += 1) {
      const rows = Math.ceil(n / cols);
      const w = Math.min((width - gap * (cols - 1)) / cols, ((height - gap * (rows - 1)) / rows) / RATIO, maxW);
      if (w > best.w) best = { cols, w };
    }
    best.w = Math.max(24, Math.floor(best.w));
    return best;
  }

  function interzoneCapacity(playerId) {
    if (!rulesOn()) return 3;
    if (playerId === myPlayerId && typeof rulesInterzoneCapacityClient === "function") return rulesInterzoneCapacityClient();
    const bonus = (latestState?.battlefield || []).reduce((total, item) => {
      if (battlefieldItemControllerId(item) !== playerId || !item.faceUp || item.effectsDisabled || item.fieldZone === "stalemate") return total;
      return total + (passiveEffectsByCard.get(item.cardId) || [])
        .filter((effect) => effect.kind === "extend_interzone")
        .reduce((sum, effect) => sum + Number(effect.value || 0), 0);
    }, 0);
    return 3 + Math.max(0, bonus);
  }

  function computeGeometry(groups) {
    const wrap = document.getElementById("battlefieldWrap");
    const rect = wrap.getBoundingClientRect();
    const W = rect.width || window.innerWidth;
    const H = rect.height || window.innerHeight;
    const compact = W < 1100 || H < 640;
    // a phone held sideways: very little height, everything gets tighter
    const phone = H < 520;
    const colW = Math.round(phone ? clamp(W * 0.16, 118, 170) : clamp(W * 0.17, compact ? 150 : 220, 330));
    const fieldL = colW;
    const fieldR = W - colW;
    const fieldW = fieldR - fieldL;
    const cx = (fieldL + fieldR) / 2;
    const zcCount = Math.max(groups.me.confrontation.length, groups.opp.confrontation.length);
    const kBase = zcCount <= 2 ? 1.7 : zcCount <= 4 ? 1.6 : 1.5;
    const k = compact ? 1 + (kBase - 1) * 0.5 : kBase;
    const intW = clamp(W * 0.074, 78, 150);
    // phone: the Confrontation Zone gets the width, the Interzones and the centre stay slim
    const izW = Math.round(Math.min(intW * k, fieldW * (phone ? 0.19 : 0.2)));
    const gutW = Math.round(phone ? clamp(W * 0.05, 34, 56) : clamp(W * 0.062, 56, 116));
    const handH = typeof handCardHeight === "number" ? handCardHeight : 170;
    const handCollapsed = document.getElementById("handArea")?.classList.contains("hand-collapsed");
    // touch phones: the hand sits above the screen's bottom edge, where an upward
    // drag of a card would otherwise be taken for the system "home" swipe
    const handLift = phone && window.matchMedia?.("(pointer: coarse)").matches ? 22 : 0;
    const handPeek = (handCollapsed ? 48 : Math.round(handH * 0.62 + 18)) + handLift;
    const oppHandH = Math.round(phone ? clamp(H * 0.09, 30, 40) : clamp(H * 0.085, 46, 86));
    const totalsH = phone ? 34 : compact ? 44 : 54;
    const stale = groups.stalemate.length > 0;
    const staleH = stale ? (phone ? 52 : 84) : 0;
    const bandTop = 0;
    const bandH = oppHandH + totalsH + staleH + 10;
    const zcTop = bandTop + bandH;
    const zcBottom = Math.max(zcTop + 120, H - handPeek);
    return {
      W, H, compact, phone, colW, fieldL, fieldR, cx, izW, gutW, handPeek, handLift, oppHandH, totalsH, staleH, bandH,
      zcTop, zcBottom, wrapLeft: rect.left, wrapTop: rect.top,
      izMe: { l: fieldL, r: fieldL + izW },
      izOpp: { l: fieldR - izW, r: fieldR },
      zcMe: { l: fieldL + izW + 10, r: cx - gutW / 2, t: zcTop, b: zcBottom },
      zcOpp: { l: cx + gutW / 2, r: fieldR - izW - 10, t: zcTop, b: zcBottom },
    };
  }

  // the classic board keeps its logical size; in beta it is just fitted into
  // the field, so tokens and drawings (still stored in board coordinates)
  // stay visible and draggable. Zoom and pan are off.
  function fitBoard(G) {
    const width = Math.max(200, G.fieldR - G.fieldL);
    zoomLevel = Math.min(width / BOARD_WIDTH, G.H / BOARD_HEIGHT);
    panX = G.fieldL + (width - BOARD_WIDTH * zoomLevel) / 2;
    panY = (G.H - BOARD_HEIGHT * zoomLevel) / 2;
    applyTransform();
  }

  // a screen rectangle (relative to the wrap) -> battlefield-local box for a
  // 150x210 element scaled around its centre
  function boxFor(x, y, w) {
    const k = w / CARD_W / zoomLevel;
    const lx = (x - panX) / zoomLevel;
    const ly = (y - panY) / zoomLevel;
    return {
      x: lx - (CARD_W / 2) * (1 - k),
      y: ly - (CARD_H / 2) * (1 - k),
      k,
      screen: { x, y, w, h: w * RATIO },
    };
  }

  function layoutInterzoneColumn(G, side, groups, players) {
    const column = side === "me" ? G.izMe : G.izOpp;
    const player = side === "me" ? players.me : players.opp;
    const inner = column.r - column.l - 16;
    const labelH = 18;
    const top = 10;
    // stop above the hand when its fan reaches this column, like the Confrontation
    // Zone does: the tray box ignores the hover transforms, so it does not jump
    const tray = document.querySelector("#handArea .hand-tray");
    const trayRect = tray && tray.childElementCount ? tray.getBoundingClientRect() : null;
    const underHand = trayRect && trayRect.width > 0
      && trayRect.right - G.wrapLeft > column.l && trayRect.left - G.wrapLeft < column.r;
    const bottom = underHand ? G.H - G.handPeek - 6 : G.H - 12;
    const available = bottom - top - labelH * 2 - 18;
    const wills = groups[side].will.length;
    const used = groups[side].interzone.length;
    const fullCapacity = Math.max(player ? interzoneCapacity(player.id) : 3, used);
    // phone: the Interzone is sized for the cards it holds (one slot when empty),
    // not for every free slot, so the Wills keep the height (the label still
    // reads used/capacity)
    const capacity = G.phone ? Math.max(1, used) : fullCapacity;
    const columnFit = (width, height, count, opts) => (G.phone && count > 1 && stackedFit(width, height, count, opts)) || fit(width, height, count, opts);
    // share the height so both zones keep cards as large as possible: the Wills
    // stay in one column (and the Interzone shrinks) before either doubles up
    const izOpts = { maxW: Math.min(inner * 0.9, 170), gap: 8, maxCols: 2 };
    const pzOpts = { maxW: Math.min(inner * 0.9, 150), gap: 8, maxCols: 2 };
    let izShare = 0.82;
    if (wills) {
      let bestScore = -1;
      for (let share = 0.3; share <= 0.821; share += 0.01) {
        const a = columnFit(inner, Math.max(80, available * share), capacity, izOpts);
        const b = columnFit(inner, Math.max(40, available * (1 - share)), wills, pzOpts);
        // the smaller of the two decides; ties keep the larger Interzone
        const score = Math.min(a.w, b.w) * 1000 + a.w;
        if (score > bestScore) { bestScore = score; izShare = share; }
      }
    }
    const izH = Math.max(80, available * izShare);
    const pzH = Math.max(40, available - izH);
    const izTop = top + labelH;
    const pzTop = izTop + izH + 18 + labelH;
    const izFit = columnFit(inner, izH, capacity, izOpts);
    const pzFit = columnFit(inner, pzH, Math.max(wills, 1), pzOpts);
    return {
      column, capacity, fullCapacity, used, wills,
      iz: { t: izTop, h: izH, fit: izFit, labelY: top },
      pz: { t: pzTop, h: pzH, fit: pzFit, labelY: pzTop - labelH },
      divider: izTop + izH + 9,
    };
  }

  // phone: one under the other (both whole) unless that is clearly smaller than
  // two columns; returns null when the cards would be too small either way
  // (under 40 % of a lone card): the caller then overlaps them in a cascade
  function stackedFit(width, height, count, opts) {
    const single = fit(width, height, 1, opts);
    const oneColumn = fit(width, height, count, { ...opts, maxCols: 1 });
    const twoColumns = fit(width, height, count, { ...opts, maxCols: 2 });
    const chosen = oneColumn.w >= twoColumns.w * 0.85 ? oneColumn : twoColumns;
    return chosen.w >= single.w * 0.4 ? chosen : null;
  }
  // cards overlapping down the zone: every card shows its top (name and art) above the
  // next one; the first card of the group (the First Manifestation) is the one in full view
  const CASCADE_STEP = 0.24;
  function cascadePositions(area, count, maxW) {
    const h = Math.min((area.b - area.t) / (1 + CASCADE_STEP * (count - 1)), maxW * RATIO, (area.r - area.l - 12) * RATIO);
    const w = Math.max(24, Math.floor(h / RATIO));
    const height = w * RATIO * (1 + CASCADE_STEP * (count - 1));
    const top = area.t + Math.max(0, (area.b - area.t - height) / 2);
    const left = area.l + (area.r - area.l - w) / 2;
    return Array.from({ length: count }, (_value, index) => {
      const level = count - 1 - index;
      return { x: left, y: top + level * CASCADE_STEP * w * RATIO, w, cascade: true, layer: 2 + level };
    });
  }
  function gridPositions(area, count, cardFit, { fromRight = false, gap = 10, centerY = true } = {}) {
    const cols = Math.min(cardFit.cols, Math.max(count, 1));
    const rows = Math.ceil(Math.max(count, 1) / cols);
    const w = cardFit.w;
    const h = w * RATIO;
    const gridW = cols * w + (cols - 1) * gap;
    const gridH = rows * h + (rows - 1) * gap;
    const left = area.l + (area.r - area.l - gridW) / 2;
    const top = centerY ? area.t + Math.max(0, (area.b - area.t - gridH) / 2) : area.t;
    const out = [];
    for (let index = 0; index < count; index += 1) {
      const row = Math.floor(index / cols);
      const rawCol = index % cols;
      const col = fromRight ? cols - 1 - rawCol : rawCol;
      out.push({ x: left + col * (w + gap), y: top + row * (h + gap), w });
    }
    return out;
  }

  // Computes where each battlefield card goes (battlefield-local boxes) and
  // caches the geometry for the chrome. Called by renderBattlefield.
  function placement() {
    if (!active() || !latestState) return null;
    const { groups, info } = groupItems();
    const players = sidePlayers();
    const G = computeGeometry(groups);
    fitBoard(G);
    const slots = new Map();
    const zc = {};
    const traps = latestState.rulesEngine?.trapCards || {};
    for (const side of ["me", "opp"]) {
      const area = side === "me" ? G.zcMe : G.zcOpp;
      // a Trap played in place of the First Manifestation takes a slot like a card
      const trap = players[side] ? traps[players[side].id] : null;
      const count = groups[side].confrontation.length + (trap ? 1 : 0);
      const width = area.r - area.l;
      const maxW = Math.min(230, width * (G.phone ? 0.85 : 0.62));
      const cardFit = fit(width - 12, area.b - area.t - 30, count, { maxW });
      zc[side] = { area, fit: cardFit, trap: null };
      const inner = { l: area.l, r: area.r, t: area.t + 22, b: area.b - 8 };
      // phone: one under the other, then two columns, and only when even that makes
      // them too small, a cascade (each card showing the top of the one before)
      let rects;
      if (G.phone && count > 1) {
        const stacked = stackedFit(width - 12, inner.b - inner.t, count, { maxW });
        rects = stacked
          ? gridPositions(inner, count, stacked, { fromRight: side === "me" })
          : cascadePositions(inner, count, maxW);
      } else {
        rects = gridPositions(inner, count, cardFit, { fromRight: side === "me" });
      }
      rects.forEach((rect, index) => {
        const entry = groups[side].confrontation[index];
        if (entry) slots.set(entry.item.id, { ...rect, zone: "confrontation", side });
        else zc[side].trap = { ...rect, ...trap };
      });
    }
    const columns = {};
    for (const side of ["me", "opp"]) {
      const col = layoutInterzoneColumn(G, side, groups, players);
      columns[side] = col;
      const izArea = { l: col.column.l + 8, r: col.column.r - 8, t: col.iz.t, b: col.iz.t + col.iz.h };
      col.slotRects = gridPositions(izArea, col.capacity, col.iz.fit, { gap: 8, centerY: false });
      groups[side].interzone.forEach((entry, index) => {
        const rect = col.slotRects[index] || col.slotRects[col.slotRects.length - 1];
        slots.set(entry.item.id, { ...rect, zone: "interzone", side });
      });
      const pzArea = { l: col.column.l + 8, r: col.column.r - 8, t: col.pz.t, b: col.pz.t + col.pz.h };
      gridPositions(pzArea, groups[side].will.length, col.pz.fit, { gap: 8, centerY: false })
        .forEach((rect, index) => slots.set(groups[side].will[index].item.id, { ...rect, zone: "will", side }));
    }
    // stalemate: a thin strip under the totals, or the open panel
    const staleCount = groups.stalemate.length;
    const stale = { count: staleCount };
    // manual play: with no card in it, the Stalemate Zone is a drop band under the totals
    if (!staleCount && !rulesOn()) {
      const dropW = Math.min(640, (G.zcOpp.r - G.zcMe.l) * 0.96);
      stale.drop = { l: G.cx - dropW / 2, r: G.cx + dropW / 2, t: G.oppHandH + G.totalsH + 2, b: G.oppHandH + G.totalsH + 2 + (G.phone ? 30 : 44) };
    }
    if (staleCount) {
      if (local.staleOpen) {
        const panel = staleePanelRect(G);
        stale.panel = panel;
        const halves = { me: [], opp: [] };
        groups.stalemate.forEach((entry) => halves[entry.side].push(entry));
        for (const side of ["me", "opp"]) {
          const half = side === "me"
            ? { l: panel.l + 14, r: panel.cx - 7, t: panel.t + 70, b: panel.b - 14 }
            : { l: panel.cx + 7, r: panel.r - 14, t: panel.t + 70, b: panel.b - 14 };
          const cardFit = fit(half.r - half.l, half.b - half.t - 20, halves[side].length, { maxW: clamp(G.W * 0.13, 100, 200), gap: 10 });
          gridPositions({ ...half, t: half.t + 18 }, halves[side].length, cardFit, { centerY: false })
            .forEach((rect, index) => slots.set(halves[side][index].item.id, { ...rect, zone: "stalemate", side, open: true }));
        }
      } else {
        const stripW = Math.min(640, (G.zcOpp.r - G.zcMe.l) * 0.96);
        const strip = { l: G.cx - stripW / 2, r: G.cx + stripW / 2, t: G.oppHandH + G.totalsH + 6, h: G.staleH - 6 };
        stale.strip = strip;
        const w = Math.floor((strip.h - 16) / RATIO);
        stale.max = Math.max(1, Math.floor((stripW - 220) / (w + 4)));
        stale.w = w;
        const shown = groups.stalemate.slice(0, stale.max);
        const totalW = shown.length * (w + 4) - 4;
        const start = G.cx - totalW / 2;
        groups.stalemate.forEach((entry, index) => {
          const i = Math.min(index, shown.length - 1);
          slots.set(entry.item.id, { x: start + i * (w + 4), y: strip.t + (strip.h - w * RATIO) / 2, w, zone: "stalemate", side: entry.side, strip: true, hiddenExtra: index >= shown.length });
        });
      }
      // a stalemated card whose destination is being chosen leaves the strip:
      // shown big at the field centre so it can be dragged to the deck or Interzone
      const pendingDest = latestState?.rulesEngine?.pendingChoice;
      const destEntry = pendingDest?.kind === "confrontation_destination"
        && groups.stalemate.find((entry) => entry.item.id === pendingDest.itemId);
      if (destEntry) {
        // in my Confrontation Zone (my own cards there have already left), under the
        // choice banner (top: a third of the screen) so nothing covers it
        const w = Math.round(clamp(G.W * 0.09, 90, 150));
        const bannerBottom = G.H / 3 + 90 - (G.wrapTop || 0);
        const y = Math.min(
          Math.max(G.zcTop + 8, bannerBottom + 12, (G.zcTop + G.zcBottom) / 2 - (w * RATIO) / 2),
          Math.max(G.zcTop + 8, G.zcBottom - w * RATIO - 8),
        );
        const x = (G.zcMe.l + G.zcMe.r) / 2 - w / 2;
        slots.set(destEntry.item.id, { x, y, w, zone: "stalemate", side: destEntry.side, focus: true });
      }
    }
    // Float and other stacked cards: on top of their anchor, offset, floating
    const depth = new Map();
    const stackedResolved = [];
    let pending = groups.stacked.slice();
    for (let pass = 0; pass < 4 && pending.length; pass += 1) {
      pending = pending.filter((entry) => {
        const anchor = slots.get(entry.item.stackedOn);
        if (!anchor) return true;
        const n = (depth.get(entry.item.stackedOn) || 0) + 1;
        depth.set(entry.item.stackedOn, n);
        const dir = anchor.side === "opp" ? -1 : 1;
        const w = anchor.w * 0.92;
        slots.set(entry.item.id, {
          x: anchor.x + dir * anchor.w * 0.24 * n + (anchor.w - w) / 2,
          y: anchor.y - anchor.w * RATIO * 0.1 * n,
          w, zone: anchor.zone, side: anchor.side, floating: true, layer: 4 + n,
        });
        stackedResolved.push(entry);
        return false;
      });
    }
    pending.forEach((entry) => {
      const fallback = { x: G.cx - 40, y: G.zcTop + 10, w: 80, zone: "confrontation", side: entry.side };
      slots.set(entry.item.id, fallback);
    });
    const boxes = new Map();
    slots.forEach((rect, id) => boxes.set(id, { ...boxFor(rect.x, rect.y, rect.w), meta: rect, info: info.get(id) }));
    local.geometry = { G, groups, players, zc, columns, stale, info };
    local.placement = boxes;
    return boxes;
  }

  function staleePanelRect(G) {
    const l = G.zcMe.l - 4;
    const r = G.zcOpp.r + 4;
    const t = G.oppHandH + 8;
    const b = Math.min(G.zcBottom, t + Math.max(340, (G.zcBottom - t) * 0.94));
    return { l, r, t, b, cx: (l + r) / 2 };
  }

  // ------------------------------------------------------------ app.js hooks

  function decorateCard(el, item, box) {
    const meta = box.meta || {};
    el.style.scale = box.k.toFixed(4);
    el.classList.add("ub-card", `ub-zone-${meta.zone || "field"}`, `ub-side-${meta.side || "me"}`);
    if (meta.floating) {
      el.classList.add("ub-floating");
      el.style.zIndex = String(meta.layer || 5);
    }
    if (meta.cascade) el.style.zIndex = String(meta.layer);
    if (meta.open) el.classList.add("ub-stale-open");
    if (meta.strip) el.classList.add("ub-stale-strip-card");
    if (meta.hiddenExtra) el.classList.add("ub-hidden-extra");
    if (meta.focus) {
      el.classList.add("ub-stale-focus");
      el.style.zIndex = "40";
    }
    if (box.info?.first && cardsById.get(item.cardId)?.type !== "persistent_will") {
      el.insertAdjacentHTML("beforeend", `<span class="ub-first-badge" title="${esc(t("ubFirstManifestation"))}">${ICONS.first}</span>`);
    }
  }

  // drop on the field -> board position inside the zone under the pointer
  // (or the natural zone of the card when the drop lands anywhere else)
  function dropLogical(clientX, clientY, ctx) {
    const geometry = local.geometry;
    if (!geometry) return { x: 700, y: mySeat() === 1 ? 525 : 800 };
    const { G, groups, columns } = geometry;
    const x = clientX - G.wrapLeft;
    const y = clientY - G.wrapTop;
    const item = ctx?.kind === "battlefield" ? latestState.battlefield.find((entry) => entry.id === ctx.itemId) : null;
    const cardId = item?.cardId || ctx?.cardId;
    const card = cardsById.get(cardId);
    let side = null;
    let zone = null;
    const inside = (area) => x >= area.l && x <= area.r && y >= area.t && y <= area.b;
    if (local.staleOpen && geometry.stale.panel && inside(geometry.stale.panel)) {
      zone = "stalemate";
      side = x < geometry.stale.panel.cx ? "me" : "opp";
    } else if (geometry.stale.strip && inside({ ...geometry.stale.strip, b: geometry.stale.strip.t + geometry.stale.strip.h })) {
      zone = "stalemate";
      side = "me";
    } else if (geometry.stale.drop && inside(geometry.stale.drop)) {
      zone = "stalemate";
      side = "me";
    } else {
      for (const candidate of ["me", "opp"]) {
        const col = columns[candidate];
        if (x >= col.column.l && x <= col.column.r) {
          side = candidate;
          zone = y < col.divider ? "interzone" : "will";
        }
      }
      if (!zone && inside({ ...G.zcMe, t: G.bandH * 0.6 })) { side = "me"; zone = "confrontation"; }
      if (!zone && inside({ ...G.zcOpp, t: G.bandH * 0.6 })) { side = "opp"; zone = "confrontation"; }
    }
    if (!zone) {
      side = "me";
      const type = card?.type;
      zone = type === "persistent_will" || type === "ephemeral_will" ? "will" : "confrontation";
    }
    // in rules mode the engine decides the side; a drop on the opponent's half
    // still targets my own zone (the engine moves it if the card says otherwise)
    if (rulesOn() && side === "opp" && zone !== "stalemate") side = "me";
    const seat = side === "me" ? mySeat() : 1 - mySeat();
    const classicZone = zone === "will" ? "field" : zone;
    let index;
    if (zone === "stalemate") {
      index = groups.stalemate.filter((entry) => entry.item.id !== item?.id).length;
    } else {
      const list = groups[side][zone].filter((entry) => entry.item.id !== item?.id);
      index = list.length;
      // dropped onto a card of that zone: take its place in the order
      const hit = local.placement && [...local.placement.entries()].find(([id, box]) => (
        id !== item?.id && box.meta?.zone === zone && box.meta?.side === side
        && x >= box.meta.x && x <= box.meta.x + box.meta.w && y >= box.meta.y && y <= box.meta.y + box.meta.w * RATIO
      ));
      if (hit) {
        const target = list.findIndex((entry) => entry.item.id === hit[0]);
        if (target >= 0) index = target;
      }
    }
    // slot first, then the next free one: a card dropped mid-list nudges the order
    const slot = classicSlot(classicZone, seat, index);
    const occupied = new Set((latestState.battlefield || []).filter((other) => other.id !== item?.id).map((other) => `${Math.round(other.x)}:${Math.round(other.y)}`));
    let free = slot;
    for (let next = index; next < index + 32; next += 1) {
      const candidate = classicSlot(classicZone, seat, next);
      if (!occupied.has(`${Math.round(candidate.x)}:${Math.round(candidate.y)}`)) { free = candidate; break; }
    }
    if (!rulesOn()) return free;
    return slot.x === free.x && slot.y === free.y ? slot : free;
  }

  function fieldCenter() {
    const slot = classicSlot("confrontation", mySeat(), 1);
    const logical = { x: slot.x + CARD_W / 2, y: slot.y + CARD_H / 2 };
    return rotateForSeat(logical.x, logical.y);
  }

  function itemCenter(item) {
    const box = local.placement?.get(item.id);
    if (!box) return null;
    return { x: box.x + CARD_W / 2, y: box.y + CARD_H / 2 };
  }

  // ------------------------------------------------------------ chrome

  function el(tag, className, html) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (html !== undefined) node.innerHTML = html;
    return node;
  }

  function build() {
    if (local.built) return;
    local.built = true;
    const wrap = document.getElementById("battlefieldWrap");
    const field = el("div", "ub-field");
    field.id = "ubField";
    field.innerHTML = `
      <div class="ub-side me"></div><div class="ub-side opp"></div><div class="ub-midline"></div>
      <div class="ub-izcol me" id="ubIzMe"></div><div class="ub-izcol opp" id="ubIzOpp"></div>
      <div class="ub-zc me" id="ubZcMe"><span class="ub-zlab"></span><p class="ub-empty"></p></div>
      <div class="ub-zc opp" id="ubZcOpp"><span class="ub-zlab"></span><p class="ub-empty"></p></div>
      <svg class="ub-wheel" id="ubWheel" viewBox="-62 -62 124 124" aria-hidden="true"></svg>
      <div class="ub-totals" id="ubTotals"></div>
      <div class="ub-avatar me" id="ubAvMe"></div><div class="ub-avatar opp" id="ubAvOpp"></div>
      <button type="button" class="ub-stale-strip hidden" id="ubStaleStrip"></button>
      <div class="ub-stale-drop hidden" id="ubStaleDrop"></div>
      <div class="ub-stale-panel hidden" id="ubStalePanel"></div>`;
    const battlefield = document.getElementById("battlefield");
    const controls = el("div", "ub-field-controls");
    controls.id = "ubFieldControls";
    controls.appendChild(field.querySelector("#ubTotals"));
    wrap.insertBefore(field, battlefield);
    wrap.insertBefore(controls, battlefield);

    const left = el("aside", "ub-col left");
    left.id = "ubLeft";
    left.innerHTML = `
      <div class="ub-who me" id="ubWhoMe"></div>
      <div class="ub-piles" id="ubMyPiles"></div>
      <div class="ub-score" id="ubMyScore"></div>
      <div class="ub-chat-slot">
        <section class="ub-chat" id="ubChat">
          <header>
            <div class="ub-tabs" id="ubChatTabs" role="tablist">
              <button type="button" role="tab" data-ub-tab="all"></button>
              <button type="button" role="tab" data-ub-tab="chat"><span></span><b class="ub-badge" hidden></b></button>
              <button type="button" role="tab" data-ub-tab="log"></button>
            </div>
            <button type="button" class="ub-iconbtn" id="ubPlayerLogBtn">${ICONS.log}</button>
            <button type="button" class="ub-iconbtn ub-fold" id="ubChatFold" aria-expanded="true" aria-label="${esc(t("ubFold"))}" title="${esc(t("ubFold"))}">${ICONS.chevron}</button>
          </header>
          <div class="ub-log" id="ubChatLog" aria-live="polite"></div>
          <form class="ub-chat-form" id="ubChatForm"><input id="ubChatInput" maxlength="500" autocomplete="off"><button type="submit" class="ub-iconbtn" id="ubChatSend">${ICONS.send}</button></form>
        </section>
      </div>
      <div class="ub-tools" id="ubTools">
        <div class="ub-toolrow">
          <span class="ub-toolslot" id="ubToolHand"></span>
          <div class="ub-toolmenu"><button type="button" class="ub-tool" data-ub-menu="draw">${ICONS.pen}</button><div class="ub-toolpop" id="ubDrawPop"></div></div>
          <div class="ub-toolmenu"><button type="button" class="ub-tool" data-ub-menu="create">${ICONS.plus}</button><div class="ub-toolpop" id="ubCreatePop"></div></div>
          <span class="ub-toolslot" id="ubToolView"></span>
          <button type="button" class="ub-tool ub-autoskip" id="ubAutoSkipBtn" hidden>${ICONS.skip}</button>
        </div>
      </div>`;
    const right = el("aside", "ub-col right");
    right.id = "ubRight";
    right.innerHTML = `
      <div class="ub-who opp" id="ubWhoOpp"></div>
      <div class="ub-oppblock" id="ubOppBlock">
        <button type="button" class="ub-oppbar" id="ubOppBar"></button>
        <div class="ub-oppfull"><div><div class="ub-piles" id="ubOppPiles"></div><div class="ub-score" id="ubOppScore"></div></div></div>
      </div>
      <section class="ub-stack" id="ubStack">
        <header><b></b><small id="ubStackCount"></small></header>
        <div class="ub-stack-body" id="ubStackBody"><p class="ub-stack-empty" id="ubStackEmpty"></p><div class="ub-mstack" id="ubManualStack"></div></div>
      </section>
      <div class="ub-phase" id="ubPhase"><button type="button" class="ub-manual-pass hidden" id="ubManualPass" data-pass-phase></button></div>`;
    wrap.appendChild(left);
    wrap.appendChild(right);
    const rotate = el("div", "ub-rotate");
    rotate.id = "ubRotate";
    rotate.innerHTML = `${ICONS.rotate}<p></p>`;
    document.getElementById("gameScreen").appendChild(rotate);
    // panels keep their own wheel scrolling (the board wheel-zoom is off here)
    [left, right, field].forEach((node) => node.addEventListener("wheel", (event) => event.stopPropagation(), { passive: true }));

    document.getElementById("ubChatTabs").addEventListener("click", (event) => {
      const tab = event.target.closest("[data-ub-tab]")?.dataset.ubTab;
      if (!tab) return;
      local.chatTab = tab;
      if (tab !== "log") local.unread = 0;
      if (local.chatFolded) setChatFolded(false);
      renderChat();
    });
    document.getElementById("ubChatFold").onclick = () => setChatFolded(!local.chatFolded);
    document.getElementById("ubPlayerLogBtn").onclick = () => {
      const opp = sidePlayers().opp;
      if (opp) openPlayerLog(opp.id);
    };
    document.getElementById("ubTools").addEventListener("click", (event) => {
      const trigger = event.target.closest("[data-ub-menu]");
      if (trigger) {
        const menu = trigger.parentElement;
        const open = !menu.classList.contains("open");
        closeToolMenus();
        menu.classList.toggle("open", open);
        if (open) floatOver(menu.querySelector(".ub-toolpop"), trigger);
        return;
      }
      if (event.target.closest(".ub-toolpop button")) {
        closeToolMenus();
        requestAnimationFrame(syncToolState);
      }
    });
    document.addEventListener("pointerdown", (event) => {
      if (!event.target.closest?.(".ub-toolmenu")) closeToolMenus();
      if (local.scoreOpen && !event.target.closest?.(".pile-score-adjust, .ub-score-toggle")) {
        local.scoreOpen = null;
        syncScoreAdjust();
      }
    }, true);
    document.addEventListener("pointerdown", onChoicePointerDown, true);
    document.getElementById("ubChatForm").addEventListener("submit", (event) => {
      event.preventDefault();
      const input = document.getElementById("ubChatInput");
      const text = input.value.trim();
      if (!text) return;
      send({ type: "chat_message", text });
      input.value = "";
    });
    document.getElementById("ubOppBar").onclick = () => {
      const open = document.getElementById("ubOppBlock").classList.contains("open");
      local.oppPilesOpen = !open;
      layoutRight();
    };
    const openStalemate = (event) => {
      event.stopPropagation();
      local.staleOpen = true;
      renderBattlefield();
      renderChrome();
    };
    document.getElementById("ubStaleStrip").onclick = openStalemate;
    // the board layer sits above the strip: route hovers and clicks that land on it
    document.getElementById("battlefield").addEventListener("mousemove", (event) => {
      const strip = document.getElementById("ubStaleStrip");
      if (!active() || strip.classList.contains("hidden")) return;
      const r = strip.getBoundingClientRect();
      const over = event.clientX >= r.left && event.clientX <= r.right && event.clientY >= r.top && event.clientY <= r.bottom;
      strip.classList.toggle("is-hover", over);
      document.getElementById("battlefield").style.cursor = over ? "zoom-in" : "";
    });
    // a Trap also sits under the board layer: its card shows in large on hover once it can be seen
    document.getElementById("battlefield").addEventListener("mousemove", (event) => {
      if (!active()) return;
      const trap = [...document.querySelectorAll(".ub-trap")].find((node) => {
        const r = node.getBoundingClientRect();
        return event.clientX >= r.left && event.clientX <= r.right && event.clientY >= r.top && event.clientY <= r.bottom;
      });
      const cardId = trap && !trap.classList.contains("is-hidden") ? trap.dataset.logCard
        : trap?.classList.contains("is-peek") ? latestState?.rulesEngine?.trapCards?.[myPlayerId]?.cardId : null;
      if (cardId) {
        if (local.peekCard !== trap) schedulePeek(trap, () => cardImage(cardId), 450);
      } else if (local.peekCard?.classList?.contains("ub-trap")) {
        hidePeek();
      }
    });
    document.getElementById("battlefield").addEventListener("click", (event) => {
      if (!active() || local.staleOpen || event.button !== 0) return;
      const strip = document.getElementById("ubStaleStrip");
      if (strip.classList.contains("hidden")) return;
      const r = strip.getBoundingClientRect();
      if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) return;
      if (event.target.closest(".bf-card:not(.ub-stale-strip-card)")) return;
      openStalemate(event);
    }, true);
    // the expanded stalemate closes on any click outside it (and outside its cards)
    document.addEventListener("pointerdown", (event) => {
      if (!local.staleOpen || !active()) return;
      if (event.target.closest("#ubStalePanel, .bf-card.ub-zone-stalemate, .context-menu, .ctx-menu, #ubStaleStrip")) return;
      local.staleOpen = false;
      renderBattlefield();
      renderChrome();
    }, true);

    // board card hover: a big preview after a short rest
    const board = document.getElementById("battlefield");
    board.addEventListener("mouseover", (event) => {
      if (!active()) return;
      const card = event.target.closest(".bf-card[data-item-id]");
      if (!card || card === local.peekCard) return;
      schedulePeek(card, () => boardPeekImage(card), 650);
    });
    board.addEventListener("mouseout", (event) => {
      const card = event.target.closest(".bf-card[data-item-id]");
      if (card && !card.contains(event.relatedTarget)) hidePeek();
    });
    document.addEventListener("pointerdown", (event) => {
      local.lastPointerType = event.pointerType;
      local.peekWasFor = local.peekEl ? local.peekCard : null;
      hidePeek();
    }, true);
    // a finger: a tap on a field card shows it in large beside it (a second tap, or
    // a tap anywhere else, puts it away), unless the tap already does something
    board.addEventListener("click", (event) => {
      if (!active() || local.lastPointerType !== "touch") return;
      const card = event.target.closest(".bf-card[data-item-id]");
      if (!card || event.target.closest("button, .rules-activate-marker, .rules-effect-marker")) return;
      if (card === local.peekWasFor || typeof pendingRulesBoardFlow !== "undefined" && pendingRulesBoardFlow) return;
      if (local.choice || card.matches("[class*=\"target\"], .ub-choice-pick, .ub-choice-drag")) return;
      schedulePeek(card, () => boardPeekImage(card), 0, { touch: true });
    });
    // piles: the top card in large after a short rest
    [left, right].forEach((column) => {
      column.addEventListener("mouseover", (event) => {
        const pile = event.target.closest(".field-pile .pile-trigger");
        if (!pile || pile === local.peekCard) return;
        schedulePeek(pile, () => pile.querySelector("img.pile-top-card")?.src || null, 450);
      });
      column.addEventListener("mouseout", (event) => {
        const pile = event.target.closest(".field-pile .pile-trigger");
        if (pile && !pile.contains(event.relatedTarget)) hidePeek();
      });
    });

    document.getElementById("battlefieldWrap").addEventListener("pointerdown", (event) => {
      if (!active()) return;
      if (event.target.id === "battlefieldWrap" || event.target.id === "battlefield") event.stopImmediatePropagation();
    }, true);

    window.addEventListener("resize", () => {
      if (!active() || !latestState) return;
      cancelAnimationFrame(local.resizeFrame);
      local.resizeFrame = requestAnimationFrame(() => {
        lockHandSize(true);
        renderBattlefield();
        renderChrome();
      });
    });
    const observer = new MutationObserver(() => {
      if (active()) syncStackEmpty();
    });
    document.fonts?.ready.then(() => { if (active() && latestState) fitLabels(); });
    observer.observe(document.getElementById("rulesStackPanel"), { attributes: true, attributeFilter: ["class"] });
    watchColumnMenus();
    initStackExpand();
  }

  function boardPeekImage(card) {
    const item = latestState?.battlefield?.find((entry) => entry.id === card.dataset.itemId);
    if (!item || !item.cardId) return null;
    if (!item.faceUp && !(item.ownerId === myPlayerId || isObserver)) return null;
    return cardImage(item.cardId);
  }

  function schedulePeek(anchor, getSrc, delay, { touch = false } = {}) {
    hidePeek();
    // a finger has no hover: the mouseover a tap emulates would leave the big card
    // on screen until the next touch; a tap on a card shows it instead (touch: true)
    if (local.lastPointerType === "touch" && !touch) return;
    local.peekCard = anchor;
    local.peekTimer = setTimeout(() => {
      const src = getSrc();
      if (!src || !anchor.isConnected) return;
      const peek = el("div", "ub-peek");
      peek.innerHTML = `<img src="${esc(src)}" alt="">`;
      document.body.appendChild(peek);
      const rect = anchor.getBoundingClientRect();
      const height = Math.min(window.innerHeight - 24, Math.max(300, window.innerHeight * 0.52));
      const width = height / RATIO;
      const roomRight = window.innerWidth - rect.right;
      const leftPos = roomRight >= width + 16 ? rect.right + 12 : Math.max(8, rect.left - width - 12);
      peek.style.width = `${width}px`;
      peek.style.height = `${height}px`;
      peek.style.left = `${Math.min(leftPos, window.innerWidth - width - 8)}px`;
      peek.style.top = `${clamp(rect.top + rect.height / 2 - height / 2, 12, window.innerHeight - height - 12)}px`;
      local.peekEl = peek;
      requestAnimationFrame(() => peek.classList.add("on"));
    }, delay);
  }
  function hidePeek() {
    clearTimeout(local.peekTimer);
    local.peekTimer = null;
    local.peekCard = null;
    if (local.peekEl) local.peekEl.remove();
    local.peekEl = null;
  }

  function setChatFolded(folded) {
    local.chatFolded = folded;
    const chat = document.getElementById("ubChat");
    chat.classList.toggle("folded", folded);
    const button = document.getElementById("ubChatFold");
    button.setAttribute("aria-expanded", String(!folded));
    button.title = t(folded ? "ubUnfold" : "ubFold");
    button.setAttribute("aria-label", button.title);
    if (!folded) local.unread = 0;
    renderChat();
  }

  // ------------------------------------------------------------ relocation

  // existing panels move into the columns; a placeholder remembers where they
  // came from so switching the beta off puts everything back
  function adopt(node, container, before = null) {
    if (!node || !container) return;
    if (!local.homes.has(node)) {
      const marker = document.createComment(`ub-home:${node.id || node.className}`);
      node.parentNode.insertBefore(marker, node);
      local.homes.set(node, marker);
    }
    if (node.parentNode !== container || (before && node.nextSibling !== before)) container.insertBefore(node, before);
  }
  function restoreAll() {
    setStackExpanded(false);
    local.homes.forEach((marker, node) => {
      if (marker.parentNode) marker.parentNode.insertBefore(node, marker);
      marker.remove();
    });
    local.homes.clear();
    local.iconSwaps.forEach(([button, html]) => {
      button.innerHTML = html;
      delete button.dataset.ubIcon;
    });
    local.iconSwaps = [];
    closeToolMenus();
    // piles go back onto the board
    const board = document.getElementById("battlefield");
    document.querySelectorAll("#ubMyPiles .field-pile, #ubOppPiles .field-pile").forEach((pile) => board.appendChild(pile));
  }

  // phone: "Auto-skip" is one icon of the tool row (bottom left), sized like
  // the others; a tap asks to confirm, then flips the phase-block box
  function syncAutoSkipButton(phone) {
    const wrap = document.getElementById("rulesAutoSkipWrap");
    const box = document.getElementById("rulesAutoSkip");
    const button = document.getElementById("ubAutoSkipBtn");
    if (!wrap || !box || !button) return;
    button.hidden = !phone || !rulesOn() || wrap.classList.contains("hidden");
    button.classList.toggle("on", box.checked);
    button.setAttribute("aria-pressed", String(box.checked));
    const label = `${t("rulesAutoSkipLabel")} · ${t(box.checked ? "ubOn" : "ubOff")}`;
    button.title = label;
    button.setAttribute("aria-label", label);
    if (!button.dataset.bound) {
      button.dataset.bound = "1";
      box.addEventListener("change", () => syncAutoSkipButton(document.getElementById("gameScreen").classList.contains("ub-phone")));
      button.addEventListener("click", () => {
        const next = !box.checked;
        showConfirm(t(next ? "ubAutoSkipOnAsk" : "ubAutoSkipOffAsk"), () => {
          box.checked = next;
          box.dispatchEvent(new Event("change", { bubbles: true }));
        }, t(next ? "ubEnable" : "ubDisable"));
      });
    }
  }

  function relocate() {
    adopt(document.getElementById("rulesStackPanel"), document.getElementById("ubStackBody"), document.getElementById("ubStackEmpty"));
    adopt(document.getElementById("phaseTracker"), document.getElementById("ubPhase"), document.getElementById("ubManualPass"));
    adopt(document.getElementById("handToolsDock"), document.getElementById("ubToolHand"));
    adopt(document.getElementById("drawToolbar"), document.getElementById("ubDrawPop"));
    adopt(document.getElementById("tokenToolbar"), document.getElementById("ubCreatePop"));
    const view = document.getElementById("ubToolView");
    adopt(document.getElementById("highlightOwnersBtn"), view);
    adopt(document.getElementById("inspectReopenBtn"), view);
    // the emoji buttons get line icons so the whole row reads as one set
    const icons = {
      drawPenBtn: "pen", drawEraseBtn: "erase", drawUndoBtn: "undo", drawRedoBtn: "redo", drawClearBtn: "trash",
      createTokenBtn: "token", createEssenceBtn: "essence", createDiceBtn: "dice", highlightOwnersBtn: "palette",
    };
    Object.entries(icons).forEach(([id, icon]) => {
      const button = document.getElementById(id);
      if (!button || button.dataset.ubIcon) return;
      local.iconSwaps.push([button, button.innerHTML]);
      button.dataset.ubIcon = icon;
      button.innerHTML = ICONS[icon];
    });
  }

  function movePiles() {
    const players = sidePlayers();
    const mine = document.getElementById("ubMyPiles");
    const theirs = document.getElementById("ubOppPiles");
    if (!mine || !theirs) return;
    mine.replaceChildren();
    theirs.replaceChildren();
    const order = ["deck", "graveyard", "exile", "receptacle"];
    const piles = [...document.querySelectorAll("#battlefield .field-pile")];
    piles.sort((a, b) => order.indexOf(a.dataset.zone) - order.indexOf(b.dataset.zone));
    piles.forEach((pile) => {
      const ownerId = pile.dataset.fieldPile.split(":")[0];
      const target = ownerId === players.me?.id ? mine : theirs;
      const player = latestState.players[ownerId];
      pile.style.setProperty("--pc", playerColor(ownerId));
      const zoneData = player?.zones?.[pile.dataset.zone] || {};
      const count = zoneData.count !== undefined ? zoneData.count : (zoneData.cards || []).length;
      pile.classList.toggle("ub-pile-thick", count > 1);
      target.appendChild(pile);
    });
  }

  // ------------------------------------------------------------ chrome render

  function setBox(node, area) {
    node.style.left = `${area.l}px`;
    node.style.top = `${area.t}px`;
    node.style.width = `${Math.max(0, area.r - area.l)}px`;
    node.style.height = `${Math.max(0, area.b - area.t)}px`;
  }

  function activeTemperamentKey(playerId) {
    let best = null;
    (latestState?.battlefield || []).forEach((item, index) => {
      if (!item.faceUp || item.fieldZone !== "confrontation") return;
      if (battlefieldItemControllerId(item) !== playerId) return;
      if (!fieldItemIsManifestation(item)) return;
      const order = Number(item.confrontationOrder || 0);
      if (!best || order > best.order || (order === best.order && index > best.index)) best = { item, order, index };
    });
    if (!best) return null;
    return best.item.effectiveTemperament || best.item.temperament || cardsById.get(best.item.cardId)?.temperaments?.[0] || null;
  }

  function sideHasConfrontation(playerId) {
    return (latestState?.battlefield || []).some((item) => (
      item.faceUp && item.fieldZone === "confrontation" && battlefieldItemControllerId(item) === playerId
      && fieldItemIsManifestation(item)
    ));
  }

  function leader(me, opp) {
    if (!me || !opp || !sideHasConfrontation(me.id) || !sideHasConfrontation(opp.id)) return null;
    const a = confrontationPowerOf(me.id);
    const b = confrontationPowerOf(opp.id);
    if (a !== b) return a > b ? "me" : "opp";
    if (a <= 0) return "tie";
    const ta = activeTemperamentKey(me.id);
    const tb = activeTemperamentKey(opp.id);
    if (!ta || !tb || ta === tb) return "tie";
    if (ta === "transcendent" || tb === "hollow") return "me";
    if (tb === "transcendent" || ta === "hollow") return "opp";
    if (DOMINATES[ta]?.includes(tb)) return "me";
    if (DOMINATES[tb]?.includes(ta)) return "opp";
    return "tie";
  }

  function essencePool(playerId) {
    const pool = new Map();
    (latestState?.tokens || []).forEach((token) => {
      const amount = Number(token.counters?.essence || 0);
      if (token.ownerId !== playerId || !token.isEssence || token.isNeutralCounter || !token.temperament || amount <= 0) return;
      pool.set(token.temperament, (pool.get(token.temperament) || 0) + amount);
    });
    return pool;
  }

  function temperamentLabel(key) {
    return t(`temperament${key[0].toUpperCase()}${key.slice(1)}`);
  }

  function renderTotals(G, players) {
    const totals = document.getElementById("ubTotals");
    const { me, opp } = players;
    // phone: the points pills sit at both ends of this row (renderAvatars)
    const inset = G.phone ? Math.max(0, G.fieldL + G.izW + 10 + 46 - G.zcMe.l) : 0;
    totals.style.left = `${G.zcMe.l + inset}px`;
    totals.style.width = `${G.zcOpp.r - G.zcMe.l - inset * 2}px`;
    totals.style.top = `${G.oppHandH + 4}px`;
    totals.style.height = `${G.totalsH}px`;
    if (!me) { totals.innerHTML = ""; return; }
    const lead = leader(me, opp);
    const block = (side, player) => {
      if (!player) return `<div class="ub-tside ${side}"></div>`;
      const power = confrontationPowerOf(player.id);
      const key = activeTemperamentKey(player.id);
      const ink = key ? temperamentInk(key) : "#7d7d7d";
      const pool = essencePool(player.id);
      const ownPool = !isObserver && player.id === myPlayerId && !rulesOn();
      const essence = pool.size
        ? `<div class="ub-ess" aria-label="${esc(t("essence"))}">${[...pool].map(([temperament, amount]) => ownPool
          ? `<button type="button" data-remove-essence="${esc(temperament)}" style="--ink:${esc(temperamentInk(temperament))}" title="${esc(t("essenceRemoveOne"))}: ${esc(temperamentLabel(temperament))}"><img src="${esc(temperamentSymbol(temperament))}" alt="">${amount}</button>`
          : `<span style="--ink:${esc(temperamentInk(temperament))}" title="${esc(t("essence"))} · ${esc(temperamentLabel(temperament))} ×${amount}"><img src="${esc(temperamentSymbol(temperament))}" alt="">${amount}</span>`).join("")}</div>`
        : "";
      return `<div class="ub-tside ${side}" style="--pc:${esc(playerColor(player.id))}">
        <div class="ub-total ${side}${lead === side ? " win" : ""}${lead === "tie" ? " tie" : ""}" style="--tc:${esc(ink)}" title="${esc(t("rulesPowerTotal"))}">
          <span class="ub-who2">${esc(player.name)}</span>
          <span class="ub-pw">${power}</span>
          <span class="ub-tmp">${key ? `<img src="${esc(temperamentSymbol(key))}" alt="${esc(temperamentLabel(key))}" title="${esc(t("rulesActiveTemperament"))}: ${esc(temperamentLabel(key))}">` : ""}</span>
        </div>${essenceQuickPickerMarkup(player.id)}${essence}
      </div>`;
    };
    const turn = Number(latestState.phaseTracker?.turn || 1);
    totals.innerHTML = `${block("me", me)}<span class="ub-vs ub-turn" title="${esc(t("ubTurn"))} ${turn}"><small>${esc(t("ubTurn"))}</small><b>${turn}</b></span>${block("opp", opp)}`;
    bindEssenceQuickControls(totals);
  }

  function renderWheel(G, players) {
    const svg = document.getElementById("ubWheel");
    const size = Math.min(G.gutW * 1.75, 190, (G.zcBottom - G.zcTop) * 0.6);
    svg.style.width = `${size}px`;
    svg.style.height = `${size}px`;
    svg.style.left = `${G.cx - size / 2}px`;
    svg.style.top = `${(G.zcTop + G.zcBottom) / 2 - size / 2}px`;
    const R = 34;
    const pos = (index) => {
      const angle = -Math.PI / 2 + (index * 2 * Math.PI) / 5;
      return [R * Math.cos(angle), R * Math.sin(angle)];
    };
    const ta = players.me ? activeTemperamentKey(players.me.id) : null;
    const tb = players.opp ? activeTemperamentKey(players.opp.id) : null;
    const duel = players.me && players.opp && sideHasConfrontation(players.me.id) && sideHasConfrontation(players.opp.id)
      && confrontationPowerOf(players.me.id) === confrontationPowerOf(players.opp.id);
    let body = `<circle r="${R}" class="ub-wheel-ring"/>`;
    // every domination as a small arrow (dominant -> dominated)
    const arrow = (x1, y1, x2, y2, cls, start = 10, end = 11) => {
      const length = Math.hypot(x2 - x1, y2 - y1) || 1;
      const ux = (x2 - x1) / length;
      const uy = (y2 - y1) / length;
      return `<line class="${cls}" x1="${(x1 + ux * start).toFixed(2)}" y1="${(y1 + uy * start).toFixed(2)}" x2="${(x2 - ux * end).toFixed(2)}" y2="${(y2 - uy * end).toFixed(2)}" marker-end="url(#ubArrowDim)"/>`;
    };
    RING.forEach((key, index) => {
      const [x1, y1] = pos(index);
      DOMINATES[key].forEach((target) => {
        const [x2, y2] = pos(RING.indexOf(target));
        body += arrow(x1, y1, x2, y2, "ub-wheel-dom");
      });
    });
    // Transcendent sits a little further from the circle than Hollow, whose
    // icon reads lower on its own
    const transY = -(R + 21);
    const hollowY = R + 17;
    body += arrow(0, transY, 0, -R, "ub-wheel-dom", 8, 10) + arrow(0, R, 0, hollowY, "ub-wheel-dom", 10, 8);
    const ia = RING.indexOf(ta);
    const ib = RING.indexOf(tb);
    if (ia >= 0 && ib >= 0 && ia !== ib && (DOMINATES[ta].includes(tb) || DOMINATES[tb].includes(ta))) {
      const [from, to] = DOMINATES[ta].includes(tb) ? [ia, ib] : [ib, ia];
      const [x1, y1] = pos(from);
      const [x2, y2] = pos(to);
      const length = Math.hypot(x2 - x1, y2 - y1);
      const ux = (x2 - x1) / length;
      const uy = (y2 - y1) / length;
      body += `<line class="ub-wheel-arrow${duel ? " on" : ""}" x1="${x1 + ux * 11}" y1="${y1 + uy * 11}" x2="${x2 - ux * 13}" y2="${y2 - uy * 13}" marker-end="url(#ubArrowHead)"/>`;
    }
    const node = (key, x, y, s) => {
      const who = key === ta && key === tb ? "both" : key === ta ? "me" : key === tb ? "opp" : "";
      return `<g class="ub-node${who ? ` hl ${who}` : ""}"><image href="${esc(temperamentSymbol(key))}" x="${x - s / 2}" y="${y - s / 2}" width="${s}" height="${s}"/><title>${esc(temperamentLabel(key))}</title></g>`;
    };
    RING.forEach((key, index) => {
      const [x, y] = pos(index);
      body += node(key, x, y, 17);
    });
    body += node("transcendent", 0, transY, 14) + node("hollow", 0, hollowY, 14);
    svg.innerHTML = `<defs><marker id="ubArrowDim" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z"/></marker><marker id="ubArrowHead" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z"/></marker></defs>${body}`;
    svg.classList.toggle("duel", Boolean(duel));
    svg.classList.toggle("has-arrow", body.includes("ub-wheel-arrow"));
    svg.style.setProperty("--me", players.me ? playerColor(players.me.id) : "#3fc9a8");
    svg.style.setProperty("--opp", players.opp ? playerColor(players.opp.id) : "#d3654a");
  }

  function renderInterzones(geometry) {
    const { G, columns, players } = geometry;
    for (const side of ["me", "opp"]) {
      const node = document.getElementById(side === "me" ? "ubIzMe" : "ubIzOpp");
      const col = columns[side];
      setBox(node, { l: col.column.l, r: col.column.r, t: 0, b: G.H });
      const free = col.slotRects.slice(col.used).map((rect) => (
        `<span class="ub-slot" style="left:${rect.x - col.column.l}px;top:${rect.y}px;width:${rect.w}px;height:${rect.w * RATIO}px">${esc(t("ubFreeSlot"))}</span>`
      )).join("");
      node.innerHTML = `
        <span class="ub-zlab" style="top:${col.iz.labelY}px"><span data-fit="interzone">${esc(t("ubInterzone"))}</span><b>${col.used}/${col.fullCapacity}</b></span>
        ${free}
        <span class="ub-divider" style="top:${col.divider}px"></span>
        <span class="ub-zlab" style="top:${col.pz.labelY}px"><span data-fit="wills">${esc(t("ubWills"))}</span><b>${col.wills}</b></span>`;
      node.style.setProperty("--pc", players[side] ? playerColor(players[side].id) : "transparent");
    }
  }

  function renderZones(geometry) {
    const { G, groups, players } = geometry;
    for (const side of ["me", "opp"]) {
      const node = document.getElementById(side === "me" ? "ubZcMe" : "ubZcOpp");
      setBox(node, side === "me" ? G.zcMe : G.zcOpp);
      node.querySelector(".ub-zlab").textContent = t("ubConfrontation");
      const empty = node.querySelector(".ub-empty");
      const count = groups[side].confrontation.length;
      const trap = geometry.zc?.[side]?.trap;
      empty.textContent = count || trap ? "" : side === "me" ? (isObserver ? "" : t("ubDropHint")) : isObserver ? "" : t("ubWaitingOpponent");
      empty.hidden = Boolean(count || trap);
      renderTrap(side, trap);
    }
    const sides = document.querySelectorAll("#ubField .ub-side");
    sides[0].style.left = `${G.fieldL}px`;
    sides[0].style.width = `${G.cx - G.fieldL}px`;
    sides[1].style.left = `${G.cx}px`;
    sides[1].style.width = `${G.fieldR - G.cx}px`;
    document.querySelector("#ubField .ub-midline").style.left = `${G.cx}px`;
    const field = document.getElementById("ubField");
    field.style.setProperty("--me", players.me ? playerColor(players.me.id) : "#3fc9a8");
    field.style.setProperty("--opp", players.opp ? playerColor(players.opp.id) : "#d3654a");
    const priorityId = rulesOn() ? latestState.rulesEngine.priorityPlayerId : null;
    const prio = priorityId ? (priorityId === players.me?.id ? "me" : priorityId === players.opp?.id ? "opp" : "") : "";
    if (field.dataset.prio !== prio) field.dataset.prio = prio;
    // while the First Manifestations are being placed, the Confrontation Zone
    // of each player who has not validated yet is outlined in their colour
    let placing = "";
    if (rulesOn() && typeof rulesFirstManifestationActive === "function" && rulesFirstManifestationActive()) {
      const validated = latestState.rulesEngine.firstManifestationValidatedPlayerIds || [];
      placing = ["me", "opp"].filter((side) => players[side] && !validated.includes(players[side].id)).join(" ");
    }
    if (field.dataset.pm !== placing) field.dataset.pm = placing;
  }

  // a Trap waiting face down in the Confrontation Zone, turned over when the
  // opponent's First Manifestation is revealed
  function renderTrap(side, trap) {
    const id = side === "me" ? "ubTrapMe" : "ubTrapOpp";
    let node = document.getElementById(id);
    if (!trap) {
      node?.remove();
      return;
    }
    if (!node) {
      node = el("div", "ub-trap");
      node.id = id;
      document.getElementById("ubField").appendChild(node);
    }
    const shown = trap.revealed && trap.cardId;
    const src = shown ? cardImage(trap.cardId) : (trap.cardId && side === "me" ? cardImage(trap.cardId) : "card-back.webp");
    const key = `${src}|${shown ? 1 : 0}`;
    if (node.dataset.key !== key) {
      const flipping = shown && node.dataset.key && !node.dataset.key.endsWith("|1");
      node.dataset.key = key;
      node.innerHTML = `<img src="${esc(src)}" alt="">`;
      node.classList.toggle("is-hidden", !shown);
      node.classList.toggle("is-peek", !shown && side === "me" && Boolean(trap.cardId));
      if (flipping) node.animate([{ transform: "rotateY(90deg)" }, { transform: "rotateY(0)" }], { duration: 420, easing: "cubic-bezier(.22, 1, .36, 1)" });
    }
    node.title = shown ? cardName(trap.cardId) : "";
    node.dataset.logCard = shown ? trap.cardId : "";
    node.style.left = `${trap.x}px`;
    node.style.top = `${trap.y}px`;
    node.style.width = `${trap.w}px`;
    node.style.height = `${trap.w * RATIO}px`;
  }

  function renderStalemate(geometry) {
    const { G, groups, stale, players } = geometry;
    const strip = document.getElementById("ubStaleStrip");
    const panel = document.getElementById("ubStalePanel");
    const has = stale.count > 0;
    const drop = document.getElementById("ubStaleDrop");
    drop.classList.toggle("hidden", !stale.drop);
    if (stale.drop) {
      setBox(drop, stale.drop);
      drop.textContent = t("ubStalemateDrop");
    }
    strip.classList.toggle("hidden", !has || local.staleOpen);
    panel.classList.toggle("hidden", !has || !local.staleOpen);
    document.getElementById("gameScreen").classList.toggle("ub-stale-open", has && local.staleOpen);
    if (!has) { local.staleOpen = false; return; }
    if (stale.strip) {
      setBox(strip, { l: stale.strip.l, r: stale.strip.r, t: stale.strip.t, b: stale.strip.t + stale.strip.h });
      const max = stale.max || 12;
      const shown = Math.min(stale.count, max);
      strip.innerHTML = `<span class="lab">${esc(t("ubStalemate"))} · ${stale.count} · ${stalePoints(groups.stalemate)} ${esc(t("ubPts"))}</span><span class="ub-strip-gap" style="width:${shown * ((stale.w || 25) + 4)}px"></span><span class="more">${stale.count > max ? `+${stale.count - max}` : esc(t("ubEnlarge"))}</span>`;
    }
    if (stale.panel) {
      setBox(panel, stale.panel);
      const half = (side) => {
        const player = players[side];
        const entries = groups.stalemate.filter((entry) => entry.side === side);
        const n = entries.length;
        return `<div class="ub-stale-half ${side}" style="--pc:${player ? esc(playerColor(player.id)) : "transparent"}"><h3>${esc(rulesText("ubStalemateOf", { player: player?.name || "" }))}${n ? ` <small>${stalePoints(entries)} ${esc(t("ubPts"))}</small>` : ""}</h3>${n ? "" : `<span class="ub-none">${esc(t("ubNoCard"))}</span>`}</div>`;
      };
      panel.innerHTML = `<header><h2>${esc(t("ubStalemateTitle"))}</h2><b class="ub-stale-total">${esc(rulesText("ubStaleAtStake", { points: stalePoints(groups.stalemate) }))}</b><p>${esc(t("ubStalemateHint"))}</p></header><div class="ub-stale-rows">${half("me")}${half("opp")}</div>`;
    }
  }

  // the points waiting in the Stalemate Zone (what the next winner takes)
  function stalePoints(entries) {
    return entries.reduce((total, entry) => total + (Number(cardsById.get(entry.item.cardId)?.points) || 0), 0);
  }

  function pileCount(player, zone) {
    const data = player?.zones?.[zone] || {};
    return data.count !== undefined ? data.count : (data.cards || []).length;
  }

  function renderWho(players) {
    const priorityId = rulesOn() ? latestState.rulesEngine.priorityPlayerId : null;
    const passed = new Set(rulesOn() ? (latestState.rulesEngine.priorityPasses || []) : (latestState.phaseTracker?.passedPlayerIds || []));
    for (const side of ["me", "opp"]) {
      const node = document.getElementById(side === "me" ? "ubWhoMe" : "ubWhoOpp");
      const player = players[side];
      if (!player) { node.innerHTML = ""; continue; }
      node.style.setProperty("--pc", playerColor(player.id));
      node.classList.toggle("has-prio", priorityId === player.id);
      const handCount = pileCount(player, "hand");
      const handChip = side === "opp"
        ? `<button type="button" class="ub-chip" data-ub-view-hand="${esc(player.id)}" title="${esc(`${t("viewHand")} (${handCount})`)}"><span class="hand-stack-icon" style="--owner-color:${esc(playerColor(player.id))}"><span class="hand-stack-card"></span><span class="hand-stack-card"></span><span class="hand-stack-card"></span></span>${handCount}</button>`
        : `<span class="ub-chip" title="${esc(`${handCount} ${t("ubHandCards")}`)}"><span class="hand-stack-icon" style="--owner-color:${esc(playerColor(player.id))}"><span class="hand-stack-card"></span><span class="hand-stack-card"></span><span class="hand-stack-card"></span></span>${handCount}</span>`;
      // no "hide the opponent's hand" eye here: the beta table always shows the fan,
      // and the button made the opponent's box taller than mine
      const eye = "";
      const passBadge = passed.has(player.id) && latestState.phaseTracker?.enabled ? `<span class="ub-passed" title="${esc(t("phasePassed"))}">✓</span>` : "";
      const activity = player.activity ? `<span class="ub-activity">${esc(t("activity_" + player.activity))}</span>` : "";
      node.innerHTML = `<span class="ub-dot" title="${esc(priorityId === player.id ? t("ubPriority") : "")}"></span><span class="ub-name" title="${esc(player.name)}">${esc(player.name)}</span>${passBadge}${activity}${handChip}${eye}`;
    }
    document.querySelectorAll("[data-ub-view-hand]").forEach((button) => {
      button.onclick = () => openHandView(button.dataset.ubViewHand);
    });
    document.querySelectorAll("[data-ub-toggle-opp-hand]").forEach((button) => {
      button.onclick = () => {
        opponentHandHiddenByUser = !opponentHandHiddenByUser;
        renderOppRows();
        renderChrome();
      };
    });
  }

  // player icons on each side of the opponent's hand: priority / passed state,
  // and the Vessel total next to them; also a target when a player is chosen
  function renderAvatars(G, players) {
    const priorityId = rulesOn() ? latestState.rulesEngine.priorityPlayerId : null;
    const passed = new Set(rulesOn() ? (latestState.rulesEngine.priorityPasses || []) : (latestState.phaseTracker?.passedPlayerIds || []));
    const size = Math.round(clamp(G.oppHandH - 14, 30, 46));
    document.getElementById("gameScreen").style.setProperty("--ub-avW", `${size + 92}px`);
    for (const side of ["me", "opp"]) {
      const node = document.getElementById(side === "me" ? "ubAvMe" : "ubAvOpp");
      const player = players[side];
      node.hidden = !player;
      if (!player) continue;
      node.style.setProperty("--pc", playerColor(player.id));
      node.style.setProperty("--av", `${size}px`);
      // phone: the opponent's hand fan covers its band, so the points sit in the
      // totals row under it, at the ends (the totals keep the middle)
      node.style.top = G.phone ? `${G.oppHandH + 6}px` : `${Math.round((G.oppHandH - size) / 2) + 2}px`;
      if (side === "me") { node.style.left = `${G.fieldL + G.izW + 10}px`; node.style.right = ""; }
      else { node.style.right = `${G.W - (G.fieldR - G.izW - 10)}px`; node.style.left = ""; }
      const hasPrio = priorityId === player.id;
      const hasPassed = passed.has(player.id) && (rulesOn() || latestState.phaseTracker?.enabled);
      node.classList.toggle("has-prio", hasPrio);
      node.classList.toggle("has-passed", hasPassed && !hasPrio);
      node.dataset.playerId = player.id;
      const points = receptaclePoints(player.zones.receptacle || {}, player.score);
      const state = hasPrio ? t("ubPriority") : hasPassed ? t("ubPassed") : "";
      node.title = `${player.name}${state ? ` · ${state}` : ""}`;
      // the points pill is kept between renders: the "+N" score animation of
      // the game is anchored on it (data-ub-vessel)
      if (!node.querySelector(".ub-av-pts")) {
        node.innerHTML = `<span class="ub-av-circle"></span><span class="ub-av-pts"><b></b><small>pts</small></span>`;
      }
      node.querySelector(".ub-av-circle").innerHTML = `${esc((player.name || "?").trim().charAt(0).toUpperCase())}${hasPassed && !hasPrio ? '<i class="ub-av-check">✓</i>' : ""}`;
      const pill = node.querySelector(".ub-av-pts");
      pill.title = t("ubReceptacle");
      pill.dataset.ubVessel = player.id;
      pill.querySelector("b").textContent = points;
    }
  }

  function renderScores(players) {
    for (const side of ["me", "opp"]) {
      const node = document.getElementById(side === "me" ? "ubMyScore" : "ubOppScore");
      const player = players[side];
      if (!player) { node.innerHTML = ""; continue; }
      const cards = receptacleCardPoints(player.zones.receptacle || {});
      const bonus = Number(player.score) || 0;
      node.innerHTML = `<div><small>${esc(t("ubReceptacle"))}</small><b>${cards}</b></div><div><small>${esc(t("ubBonus"))}</small><b>${bonus >= 0 ? "+" : ""}${bonus}</b></div><div class="tot"><small>${esc(t("ubTotal"))}</small><b>${cards + bonus}</b></div>`;
    }
  }

  const ZONE_ICONS = { deck: "deck", graveyard: "limbo", exile: "exile", receptacle: "vessel" };

  function renderOppBar(players) {
    const bar = document.getElementById("ubOppBar");
    const opp = players.opp;
    if (!opp) { bar.innerHTML = ""; return; }
    const mini = [["deck", "deck"], ["graveyard", "graveyard"], ["exile", "exile"], ["receptacle", "receptacle"]]
      .map(([zone]) => `<span class="mini" title="${esc(t(zone))}"><small>${esc(t(zone).slice(0, 5))}</small><i>${ICONS[ZONE_ICONS[zone]]}</i><b>${pileCount(opp, zone)}</b></span>`).join("");
    const points = receptaclePoints(opp.zones.receptacle || {}, opp.score);
    bar.innerHTML = `<span class="v"><span class="long">${esc(t("ubPilesOf"))} </span>${esc(opp.name)}</span>${mini}<span class="pts">${points}</span><span class="chev">${ICONS.chevron}</span>`;
  }

  function manualStackItems() {
    if (rulesOn()) return [];
    return (latestState?.battlefield || []).filter((item) => item.manualStack)
      .sort((a, b) => Number(b.manualStack) - Number(a.manualStack));
  }

  function syncStackEmpty() {
    const empty = document.getElementById("ubStackEmpty");
    const count = document.getElementById("ubStackCount");
    const stackEl = document.getElementById("ubStack");
    if (!rulesOn()) {
      // manual play: the Stack holds the cards players put in it
      const items = manualStackItems();
      if (empty) {
        empty.hidden = items.length > 0;
        empty.textContent = t(isObserver ? "ubStackEmpty" : "ubManualStackEmpty");
      }
      if (count) count.textContent = items.length ? String(items.length) : "";
      stackEl?.classList.toggle("hidden", false);
      stackEl?.classList.toggle("ub-manual", true);
      return;
    }
    stackEl?.classList.toggle("ub-manual", false);
    const panel = document.getElementById("rulesStackPanel");
    const hidden = !panel || panel.classList.contains("hidden");
    if (empty) {
      empty.hidden = !hidden;
      empty.innerHTML = `<span>${esc(t("ubStackEmpty"))}</span>${hidden ? lastOpponentActionHtml() : ""}`;
      empty.querySelectorAll("[data-rules-card]").forEach((ref) => {
        ref.onmouseenter = () => showCardPreview(ref.dataset.rulesCard, ref);
        ref.onmouseleave = hideCardPreview;
        ref.onclick = () => showInspect(ref.dataset.rulesCard);
      });
    }
    const stack = latestState?.rulesEngine?.actionStack || [];
    if (count) count.textContent = stack.length ? String(stack.length) : "";
    stackEl?.classList.toggle("hidden", false);
  }

  // the cards of the manual Stack keep their own element (drag, menu, preview)
  // and are just moved into the Stack panel, newest on top
  function placeManualStackCards() {
    const list = document.getElementById("ubManualStack");
    if (!list) return;
    list.innerHTML = "";
    if (!active()) return;
    manualStackItems().forEach((item) => {
      const card = document.querySelector(`#battlefield .bf-card[data-item-id="${CSS.escape(item.id)}"]`);
      if (!card) return;
      card.classList.add("ub-mstack-card");
      card.style.left = "";
      card.style.top = "";
      card.style.scale = "";
      list.appendChild(card);
    });
  }

  // the opponent's piles fold into a bar when the Stack needs the room
  function layoutRight() {
    const block = document.getElementById("ubOppBlock");
    const column = document.getElementById("ubRight");
    if (!block || !column) return;
    let open;
    if (local.oppPilesOpen === null) {
      const stackList = document.getElementById("rulesStackList");
      const stackNeed = (rulesOn() ? (stackList?.scrollHeight || 0) : (document.getElementById("ubManualStack")?.scrollHeight || 0)) + 60;
      const full = block.querySelector(".ub-oppfull > div");
      const fullH = (full?.scrollHeight || 0) + 50;
      const used = document.getElementById("ubWhoOpp").offsetHeight + document.getElementById("ubPhase").offsetHeight + 60;
      // small screens: folded by default, the bar opens them
      const smallScreen = window.innerHeight <= 900 || window.innerWidth <= 1500;
      open = !smallScreen && stackNeed + fullH <= column.clientHeight - used;
    } else {
      open = local.oppPilesOpen;
    }
    block.classList.toggle("open", open);
    // the toggle only shows up when the column is short of room
    block.classList.toggle("bar-hidden", local.oppPilesOpen === null && open);
    const bar = document.getElementById("ubOppBar");
    bar.setAttribute("aria-expanded", String(open));
    bar.title = t(open ? "ubHideOppPiles" : "ubShowOppPiles");
  }

  function renderPhaseExtras() {
    // manual play with phases on: the same phase block and button as the
    // assisted mode, only the players move the phases themselves
    document.getElementById("ubManualPass").classList.add("hidden");
    const tracker = latestState.phaseTracker || {};
    const manual = Boolean(tracker.enabled && !rulesOn());
    document.getElementById("ubPhase").classList.toggle("manual", manual);
    if (!manual) {
      document.getElementById("rulesPriority")?.classList.remove("hidden");
      return;
    }
    document.getElementById("phaseTracker")?.classList.remove("hidden");
    ["rulesAutoSkipWrap", "rulesTurnContext", "rulesConfrontationSummary"].forEach((id) => document.getElementById(id)?.classList.add("hidden"));
    const passed = new Set(tracker.passedPlayerIds || []);
    const mine = passed.has(myPlayerId);
    const opponentPassed = [...passed].some((playerId) => playerId !== myPlayerId);
    const priority = document.getElementById("rulesPriority");
    if (priority) {
      const opp = sidePlayers().opp;
      priority.className = "rules-priority";
      priority.classList.toggle("hidden", !opponentPassed && !mine);
      priority.textContent = mine
        ? t("ubWaitingOpponent")
        : opponentPassed ? `${opp?.name || ""} ${t("ubPassed")}` : "";
    }
    const button = document.getElementById("passPriorityBtn");
    if (!button) return;
    const current = typeof currentPhaseUi === "function" ? currentPhaseUi() : null;
    const steps = (current?.group?.sections || []).flatMap((section) => section.steps);
    const step = Math.max(0, steps.findIndex((entry) => entry.id === current?.phase?.id)) + 1;
    button.className = "phase-pass-button primary";
    button.classList.toggle("hidden", isObserver);
    button.classList.toggle("passed", mine);
    button.classList.toggle("must-act", !mine);
    button.disabled = isObserver;
    button.setAttribute("aria-pressed", String(mine));
    button.textContent = mine
      ? t("cancelPhasePass")
      : tracker.advanced && steps.length
        ? rulesText("rulesPassStep", { current: step, total: steps.length })
        : t("passPhase");
    button.title = current?.phase?.detail ? t(current.phase.detail) : "";
  }

  function chatEntries() {
    const entries = [];
    chatMessages.forEach((message, index) => {
      if (!message.ubAt) message.ubAt = (message.timestamp || Date.now() / 1000) + index * 1e-6;
      entries.push({ kind: "chat", at: message.ubAt, message });
    });
    (latestState?.recentLog || []).forEach((entry) => {
      if (entry.type === "chat_message") return;
      entries.push({ kind: "log", at: Number(entry.timestamp || 0) + Number(entry.sequence || 0) * 1e-9, entry });
    });
    local.system.forEach((note) => entries.push({ kind: "log", at: note.at, note }));
    entries.sort((a, b) => a.at - b.at);
    return entries;
  }

  function renderChat() {
    if (!local.built) return;
    const log = document.getElementById("ubChatLog");
    if (!log) return;
    // count by identity, not by length: the history is capped at 200 and shifts
    const lastSeen = chatMessages.lastIndexOf(local.seenChat);
    const fresh = local.seenChat && lastSeen < 0 ? chatMessages.slice(-1) : chatMessages.slice(lastSeen + 1);
    if (fresh.length) {
      const others = fresh.filter((message) => message.byId !== myPlayerId && String(message.text || "").trim());
      if (local.chatFolded || local.chatTab === "log") local.unread += others.length;
      local.seenChat = chatMessages[chatMessages.length - 1];
      if (others.length) pingMessage(others[others.length - 1]);
    }
    const tab = local.chatTab;
    const rows = chatEntries().filter((entry) => tab === "all" || entry.kind === tab).map((entry) => {
      if (entry.kind === "chat") {
        const message = entry.message;
        if (message.channel === "observers") {
          return `<p class="msg ub-obs-msg"><span class="ub-obs-tag">${esc(t("ubObserverTag"))}</span><b>${esc(message.byName)}</b> ${esc(message.text)}</p>`;
        }
        return `<p class="msg" style="--pc:${esc(playerColor(message.byId))}"><b>${esc(message.byName)}</b> ${esc(message.text)}</p>`;
      }
      if (entry.note) return `<p class="sys ub-note ${esc(entry.note.level)}">${esc(entry.note.text)}</p>`;
      const html = (isPlayerLogRelevant(entry.entry) && entry.entry.actorId && formatPlayerLogEntry(entry.entry))
        || formatLogEntry(entry.entry, { html: true });
      // an event without a wording of its own would print its raw type name: skip it
      if (!html || (entry.entry.type.includes("_") && html.includes(entry.entry.type))) return "";
      return `<p class="sys">${html}</p>`;
    }).join("");
    const nearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
    log.innerHTML = rows || `<p class="sys">${esc(t("ubNothingYet"))}</p>`;
    if (nearBottom || !log.dataset.ubScrolled) log.scrollTop = log.scrollHeight;
    log.dataset.ubScrolled = "1";
    wireLogCardNames(log);
    wirePlayerLogCardNames(log);
    const tabs = document.querySelectorAll("#ubChatTabs [data-ub-tab]");
    const labels = { all: "ubTabAll", chat: "ubTabChat", log: "ubTabLog" };
    const fitKeys = { all: "tabAll", chat: "tabChat", log: "tabLog" };
    tabs.forEach((button) => {
      const key = button.dataset.ubTab;
      const label = button.querySelector("span") || button;
      label.dataset.fit = fitKeys[key];
      label.textContent = t(labels[key]);
      button.setAttribute("aria-selected", String(key === tab));
    });
    const badge = document.querySelector("#ubChatTabs .ub-badge");
    badge.hidden = !local.unread;
    badge.textContent = String(Math.min(local.unread, 99));
    document.getElementById("ubChatInput").placeholder = t(isObserver && ["observer", "spectator"].includes(connectionRole) ? "ubObserverPlaceholder" : "chatPlaceholder");
    document.getElementById("ubChatSend").title = t("chatSend");
    document.getElementById("ubPlayerLogBtn").title = t("logHeader");
    const foldButton = document.getElementById("ubChatFold");
    foldButton.title = t(local.chatFolded ? "ubUnfold" : "ubFold");
    foldButton.setAttribute("aria-label", foldButton.title);
  }

  // the journal sits under the inspect panel when it is open: an opponent's
  // message still shows up as a small bubble over it
  function pingMessage(message) {
    const inspectOpen = !document.getElementById("inspectPanel")?.classList.contains("hidden");
    if (!active() || !(inspectOpen || local.chatFolded)) return;
    let ping = document.getElementById("ubMsgPing");
    if (!ping) {
      ping = document.createElement("button");
      ping.type = "button";
      ping.id = "ubMsgPing";
      ping.className = "ub-msg-ping";
      ping.onclick = () => {
        ping.classList.remove("show");
        if (!document.getElementById("inspectPanel")?.classList.contains("hidden")) toggleInspectPanel();
        local.chatTab = "chat";
        local.unread = 0;
        setChatFolded(false);
        renderChat();
      };
      document.body.appendChild(ping);
    }
    ping.style.setProperty("--pc", playerColor(message.byId));
    ping.innerHTML = `${ICONS.send}<span><b>${esc(message.byName)}</b> ${esc(message.text)}</span>`;
    ping.classList.add("show");
    clearTimeout(local.pingTimer);
    local.pingTimer = setTimeout(() => ping.classList.remove("show"), 7000);
  }

  function renderChrome() {
    if (!active() || !latestState || !local.geometry) return;
    const geometry = local.geometry;
    const { G, players } = geometry;
    const screen = document.getElementById("gameScreen");
    screen.style.setProperty("--ub-colW", `${G.colW}px`);
    document.documentElement.style.setProperty("--ub-colW-root", `${G.colW}px`);
    screen.style.setProperty("--ub-izW", `${G.izW}px`);
    screen.style.setProperty("--ub-oppHandH", `${G.oppHandH}px`);
    screen.style.setProperty("--ub-bandH", `${G.bandH}px`);
    screen.style.setProperty("--ub-handPeek", `${G.handPeek}px`);
    screen.style.setProperty("--ub-hand-lift", `${G.handLift}px`);
    screen.style.setProperty("--ub-fieldW", `${G.fieldR - G.fieldL}px`);
    screen.style.setProperty("--me", players.me ? playerColor(players.me.id) : "#3fc9a8");
    screen.style.setProperty("--opp", players.opp ? playerColor(players.opp.id) : "#d3654a");
    screen.classList.toggle("ub-rules", rulesOn());
    screen.classList.toggle("ub-compact", G.compact);
    screen.classList.toggle("ub-phone", G.phone);
    syncAutoSkipButton(G.phone);
    fitHand();
    renderZones(geometry);
    renderInterzones(geometry);
    renderTotals(G, players);
    renderWheel(G, players);
    renderStalemate(geometry);
    renderWho(players);
    renderAvatars(G, players);
    renderScores(players);
    renderOppBar(players);
    renderPhaseExtras();
    syncStackEmpty();
    document.querySelector("#ubStack header b").textContent = t("ubStack");
    renderChat();
    layoutRight();
    syncToolState();
    syncBoardChoice();
    markLastOpponentAction();
    fitLabels();
    // the columns settle a frame later (fonts, scrollbars): fit again then
    cancelAnimationFrame(local.fitFrame);
    local.fitFrame = requestAnimationFrame(() => { if (active()) fitLabels(); });
  }

  // ------------------------------------------------------------ toggles

  function applyTheme() {
    const value = active() ? theme() : "current";
    if (value === "current") delete document.documentElement.dataset.ubTheme;
    else document.documentElement.dataset.ubTheme = value;
    document.querySelectorAll("[data-ub-theme]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.ubTheme === theme()));
    });
  }

  function apply() {
    const on = enabled();
    const screen = document.getElementById("gameScreen");
    if (!screen) return;
    if (on) {
      build();
      localizeToggles();
      screen.classList.add("ui-beta");
      relocate();
      lockHandSize(true);
    } else if (screen.classList.contains("ui-beta")) {
      screen.classList.remove("ui-beta", "ub-rules", "ub-compact", "ub-phone", "ub-stale-open");
      unfitLabels();
      restoreAll();
      lockHandSize(false);
      syncBoardChoice();
      local.placement = null;
      local.geometry = null;
    }
    applyTheme();
    syncToggles();
    if (latestState && !screen.classList.contains("hidden")) {
      if (!on) centerBoardInView();
      renderAll();
    }
  }

  function syncToggles() {
    const on = enabled();
    const home = document.getElementById("uiBetaInput");
    if (home) home.checked = on;
    const menu = document.getElementById("uiBetaMenuBtn");
    if (menu) {
      menu.classList.toggle("active", on);
      menu.setAttribute("aria-pressed", String(on));
    }
    document.getElementById("uiBetaThemeRow")?.classList.toggle("hidden", !on);
  }

  function installToggles() {
    const options = document.getElementById("tournamentLauncherOptions");
    if (options && !document.getElementById("uiBetaInput")) {
      const label = document.createElement("label");
      label.className = "rules-beta-option ui-beta-option";
      label.htmlFor = "uiBetaInput";
      label.innerHTML = `<input type="checkbox" id="uiBetaInput"><span><strong id="uiBetaLabel"></strong><small id="uiBetaHint"></small></span>`;
      const rulesOption = options.querySelector("label[for='rulesBetaInput']");
      options.insertBefore(label, rulesOption ? rulesOption.nextSibling : null);
      label.querySelector("input").addEventListener("change", (event) => {
        setEnabled(event.target.checked);
        apply();
      });
    }
    const popover = document.querySelector("#gameMoreMenu .game-more-popover");
    if (popover && !document.getElementById("uiBetaMenuBtn")) {
      const button = document.createElement("button");
      button.type = "button";
      button.id = "uiBetaMenuBtn";
      button.className = "ui-beta-menu-btn";
      button.innerHTML = `<span id="uiBetaMenuLabel"></span><span class="phase-mode-switch" aria-hidden="true"><span></span></span>`;
      button.onclick = () => {
        setEnabled(!enabled());
        apply();
      };
      const row = document.createElement("div");
      row.id = "uiBetaThemeRow";
      row.className = "ui-beta-theme-row";
      row.innerHTML = `<span id="uiBetaThemeLabel"></span>${THEMES.map((value) => `<button type="button" data-ub-theme="${value}"><i class="ub-swatch ${value}"></i><span data-ub-theme-label="${value}"></span></button>`).join("")}`;
      row.addEventListener("click", (event) => {
        const value = event.target.closest("[data-ub-theme]")?.dataset.ubTheme;
        if (!value) return;
        try { localStorage.setItem(THEME_KEY, value); } catch (error) { /* session only */ }
        applyTheme();
      });
      popover.insertBefore(row, popover.firstChild);
      popover.insertBefore(button, row);
    }
    localizeToggles();
    syncToggles();
  }

  function localizeToggles() {
    const set = (id, key) => {
      const node = document.getElementById(id);
      if (node) node.textContent = t(key);
    };
    set("uiBetaLabel", "ubOption");
    set("uiBetaHint", "ubOptionHint");
    set("uiBetaMenuLabel", "ubMenuToggle");
    set("uiBetaThemeLabel", "ubTheme");
    const names = { current: "ubThemeCurrent", sand: "ubThemeSand", dark: "ubThemeDark" };
    document.querySelectorAll("[data-ub-theme-label]").forEach((node) => {
      node.textContent = t(names[node.dataset.ubThemeLabel]);
    });
    const menu = document.getElementById("uiBetaMenuBtn");
    if (menu) menu.title = t("ubOptionHint");    const rotate = document.querySelector("#ubRotate p");
    if (rotate) rotate.textContent = t("ubRotate");
  }

  // ------------------------------------------------------------ phones and tablets

  function touchDevice() {
    return Boolean(window.matchMedia?.("(pointer: coarse)").matches)
      && Math.min(window.screen?.width || 9999, window.screen?.height || 9999) <= 820;
  }

  // On a phone the new table plays in full screen, held sideways. Browsers only
  // allow both from a tap, so the first tap after the page opens (and the first
  // one in each new game) asks for them; leaving full screen is then respected.
  function goImmersive() {
    if (local.immersiveTried || !enabled() || !touchDevice()) return;
    local.immersiveTried = true;
    const lockLandscape = () => {
      try { window.screen?.orientation?.lock?.("landscape")?.catch?.(() => {}); } catch (error) { /* not supported (iOS) */ }
    };
    const root = document.documentElement;
    const request = root.requestFullscreen || root.webkitRequestFullscreen;
    if (document.fullscreenElement || document.webkitFullscreenElement || !request) { lockLandscape(); return; }
    try {
      const result = request.call(root, { navigationUI: "hide" });
      if (result && typeof result.then === "function") result.then(lockLandscape, () => {});
      else lockLandscape();
    } catch (error) { /* refused: the page stays as it is */ }
  }

  // touch has no right click and no hover: holding a card opens the same menu
  // as a right click (inspect, actions)
  function onTouchPressStart(event) {
    if (event.pointerType !== "touch" || !active()) return;
    cancelLongPress();
    const target = event.target;
    if (!(target instanceof Element) || target.closest("input, textarea, select")) return;
    const press = { x: event.clientX, y: event.clientY, target, id: event.pointerId };
    press.timer = window.setTimeout(() => {
      local.longPress = null;
      if (!target.isConnected) return;
      local.swallowMenuUntil = Date.now() + 900;
      navigator.vibrate?.(12);
      target.dispatchEvent(new MouseEvent("contextmenu", {
        bubbles: true, cancelable: true, clientX: press.x, clientY: press.y, button: 2,
      }));
      local.swallowClick = { until: Date.now() + 700, target };
    }, 480);
    local.longPress = press;
  }
  function onTouchPressMove(event) {
    const press = local.longPress;
    if (press && event.pointerId === press.id && Math.hypot(event.clientX - press.x, event.clientY - press.y) > 10) cancelLongPress();
  }
  function cancelLongPress() {
    if (local.longPress) window.clearTimeout(local.longPress.timer);
    local.longPress = null;
  }

  function installTouch() {
    ["pointerup", "touchend", "click"].forEach((type) => document.addEventListener(type, goImmersive, true));
    document.addEventListener("pointerdown", onTouchPressStart, true);
    document.addEventListener("pointermove", onTouchPressMove, true);
    ["pointerup", "pointercancel"].forEach((type) => document.addEventListener(type, cancelLongPress, true));
    // the browser's own long-press menu would open a second menu
    document.addEventListener("contextmenu", (event) => {
      if (event.isTrusted && Date.now() < local.swallowMenuUntil) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);
    // the tap that ends a long press does not also play or pick the card
    document.addEventListener("click", (event) => {
      const swallow = local.swallowClick;
      if (swallow && Date.now() < swallow.until && event.target instanceof Node && swallow.target.contains(event.target)) {
        local.swallowClick = null;
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);
  }

  // ------------------------------------------------------------ hand

  // the hand has one fixed size in this layout (the old resize is ignored and
  // given back when the layout is switched off)
  function lockHandSize(on) {
    if (typeof handCardHeight !== "number" || typeof applyHandCardHeight !== "function") return;
    if (on) {
      if (local.prevHandH === null) local.prevHandH = handCardHeight;
      handCardHeight = Math.round(window.innerHeight < 520
        ? clamp(window.innerHeight * 0.3, 90, 160)
        : clamp(window.innerHeight * 0.35, 200, 400));
    } else if (local.prevHandH !== null) {
      handCardHeight = local.prevHandH;
      local.prevHandH = null;
    }
    applyHandCardHeight();
  }

  // the hovered hand card is read at about 60% of the screen height
  function setHandHoverScale() {
    if (typeof handCardHeight !== "number") return;
    const hoverH = window.innerHeight < 520 ? window.innerHeight * 0.8 : clamp(window.innerHeight * 0.6, 420, 760);
    document.documentElement.style.setProperty("--hand-hover-scale", Math.max(1.2, hoverH / handCardHeight).toFixed(3));
  }

  // overlap the hand cards just enough for the whole hand to fit between the columns
  function fitHand() {
    const tray = document.getElementById("myHandTray");
    if (!tray) return;
    const cards = tray.querySelectorAll(".hand-card");
    const handH = typeof handCardHeight === "number" ? handCardHeight : 170;
    const cardW = handH * 0.716;
    const style = getComputedStyle(tray);
    const room = tray.clientWidth - parseFloat(style.paddingLeft || 0) - parseFloat(style.paddingRight || 0) - 24;
    const base = handH * 0.32;
    const n = cards.length;
    const needed = n > 1 ? (n * cardW - room) / (n - 1) : 0;
    const overlap = Math.min(cardW * 0.86, Math.max(base, needed));
    tray.style.setProperty("--ub-hand-ml", `${-Math.round(overlap)}px`);
  }

  // when a hand card has to be chosen, the ones that cannot be are dimmed
  function markHandEligibility() {
    const drop = typeof rulesHandDropChoice === "function" ? rulesHandDropChoice() : null;
    const types = drop ? (drop.requireTypes?.length ? drop.requireTypes : drop.requireManifestation ? ["manifestation"] : null) : null;
    let handTop = Infinity;
    document.querySelectorAll("#myHandTray [data-hand-card]").forEach((card) => {
      card.classList.toggle("ub-ineligible", Boolean(types) && !types.includes(cardsById.get(card.dataset.handCard)?.type));
      handTop = Math.min(handTop, card.getBoundingClientRect().top);
    });
    // the hand lives in the fixed field layer, under the choice backdrop: the backdrop
    // stops above it (ui-beta.css) so the cards to pick stay lit
    if (drop && Number.isFinite(handTop)) document.documentElement.style.setProperty("--ub-hand-top", `${Math.round(handTop)}px`);
  }

  // a drawn card shows up in the hand when its draw animation lands, not before
  function holdNewHandCards() {
    const cards = [...document.querySelectorAll("#myHandTray [data-hand-card]")];
    const counts = new Map();
    cards.forEach((card) => counts.set(card.dataset.handCard, (counts.get(card.dataset.handCard) || 0) + 1));
    const remaining = typeof rulesVfxQueueRemaining === "function" ? rulesVfxQueueRemaining() : 0;
    if (local.handSeen && remaining > 0) {
      counts.forEach((count, cardId) => {
        const fresh = count - (local.handSeen.get(cardId) || 0);
        if (fresh > 0) local.handHidden.set(cardId, (local.handHidden.get(cardId) || 0) + fresh);
      });
    }
    local.handSeen = counts;
    const left = new Map(local.handHidden);
    [...cards].reverse().forEach((card) => {
      const hidden = left.get(card.dataset.handCard) || 0;
      card.classList.toggle("ub-draw-pending", hidden > 0);
      if (hidden > 0) left.set(card.dataset.handCard, hidden - 1);
    });
    if (local.handHidden.size && !local.handRevealTimer) scheduleHandReveal(Date.now());
    // nothing is played from the hand (First Manifestation...) before the draw has landed
    document.body.classList.toggle("ub-hand-drawing", local.handHidden.size > 0);
  }

  function scheduleHandReveal(startedAt) {
    const remaining = typeof rulesVfxQueueRemaining === "function" ? rulesVfxQueueRemaining() : 0;
    local.handRevealTimer = setTimeout(() => {
      local.handRevealTimer = null;
      const still = typeof rulesVfxQueueRemaining === "function" ? rulesVfxQueueRemaining() : 0;
      if (still > 0 && Date.now() - startedAt < 8000) {
        scheduleHandReveal(startedAt);
        return;
      }
      local.handHidden.clear();
      document.body.classList.remove("ub-hand-drawing");
      document.querySelectorAll("#myHandTray .ub-draw-pending").forEach((card) => card.classList.remove("ub-draw-pending"));
    }, Math.min(Math.max(remaining, 0) + 120, 2500));
  }

  // ------------------------------------------------------------ tools row

  // A menu opened from a side column floats over the page: the columns clip
  // whatever overflows them (they scroll on short screens, phones hide it).
  function floatOver(pop, anchor, { above = true } = {}) {
    Object.assign(pop.style, { position: "fixed", left: "0px", top: "0px", right: "auto", bottom: "auto", transform: "none", zIndex: "700", maxHeight: "", overflowY: "" });
    const box = anchor.getBoundingClientRect();
    let size = pop.getBoundingClientRect();
    const margin = 8;
    const spaceAbove = box.top - 6 - margin;
    const spaceBelow = window.innerHeight - margin - box.bottom - 6;
    // taller than the room on its side: the roomier side, scrolling within it
    if (size.height > (above ? spaceAbove : spaceBelow)) {
      if (size.height > spaceAbove && size.height > spaceBelow) {
        above = spaceAbove >= spaceBelow;
        Object.assign(pop.style, { maxHeight: `${Math.max(120, above ? spaceAbove : spaceBelow)}px`, overflowY: "auto" });
        size = pop.getBoundingClientRect();
      } else above = !above;
    }
    const top = above ? box.top - size.height - 6 : box.bottom + 6;
    const left = Math.min(Math.max(margin, box.left), window.innerWidth - size.width - margin);
    pop.style.left = `${Math.round(left)}px`;
    pop.style.top = `${Math.round(Math.max(margin, top))}px`;
  }
  function unfloat(pop) {
    ["position", "left", "top", "right", "bottom", "transform", "zIndex", "maxHeight", "overflowY"].forEach((key) => { pop.style[key] = ""; });
  }

  // A click on the Stack opens it in a large window over the table (its cards,
  // buttons and links keep their own click); the header, the backdrop or
  // Escape put it back in its column.
  function setStackExpanded(open) {
    const stack = document.getElementById("ubStack");
    if (!stack) return;
    stack.classList.toggle("ub-expanded", open);
    document.getElementById("ubStackBackdrop")?.classList.toggle("hidden", !open);
    stack.querySelector("header")?.setAttribute("aria-expanded", String(open));
  }
  function initStackExpand() {
    const stack = document.getElementById("ubStack");
    if (!stack || stack.dataset.expandBound) return;
    stack.dataset.expandBound = "1";
    const backdrop = el("div", "ub-stack-backdrop hidden");
    backdrop.id = "ubStackBackdrop";
    stack.parentNode.insertBefore(backdrop, stack);
    backdrop.addEventListener("click", () => setStackExpanded(false));
    const header = stack.querySelector("header");
    header.setAttribute("role", "button");
    header.tabIndex = 0;
    header.title = t("ubStackOpen");
    stack.addEventListener("click", (event) => {
      if (!active()) return;
      const open = stack.classList.contains("ub-expanded");
      if (event.target.closest("header")) { setStackExpanded(!open); return; }
      if (open || event.target.closest("button, a, input, select, label, [data-rules-card], .bf-card, .rules-stack-list li")) return;
      setStackExpanded(true);
    });
    header.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setStackExpanded(!stack.classList.contains("ub-expanded")); }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && stack.classList.contains("ub-expanded")) setStackExpanded(false);
    });
  }

  // Every menu opened from a side column floats: watched here, so a new one only
  // needs a line (what it is, when it is open, what it opens from).
  const COLUMN_MENUS = [
    {
      selector: ".ub-toolmenu .ub-toolpop",
      open: (pop) => pop.closest(".ub-toolmenu").classList.contains("open"),
      anchor: (pop) => pop.closest(".ub-toolmenu").querySelector("[data-ub-menu]"),
      above: true,
    },
    {
      selector: "#handToolbar",
      open: (pop) => !pop.classList.contains("hidden"),
      anchor: () => document.getElementById("handToolsToggleBtn"),
      above: true,
    },
    {
      selector: ".field-pile .zone-popover",
      open: () => true,
      anchor: (pop) => pop.closest(".field-pile"),
      above: false,
    },
    {
      selector: ".field-pile > .pile-score-adjust",
      open: (pop) => pop.classList.contains("ub-open"),
      anchor: (pop) => pop.parentElement.querySelector(":scope > .ub-score-toggle") || pop.parentElement,
      above: false,
    },
  ];
  function floatColumnMenus() {
    if (!active()) return;
    for (const menu of COLUMN_MENUS) {
      document.querySelectorAll(menu.selector).forEach((pop) => {
        if (!pop.closest(".ub-col")) return;
        const anchor = menu.anchor(pop);
        if (menu.open(pop) && anchor && anchor.getBoundingClientRect().width) {
          if (pop.classList.contains("zone-popover")) pop.classList.remove("zone-popover-above");
          floatOver(pop, anchor, { above: menu.above });
        } else {
          unfloat(pop);
        }
      });
    }
  }
  function watchColumnMenus() {
    const observer = new MutationObserver(() => {
      cancelAnimationFrame(local.menuFrame);
      local.menuFrame = requestAnimationFrame(floatColumnMenus);
    });
    document.querySelectorAll(".ub-col").forEach((column) => observer.observe(column, {
      subtree: true, childList: true, attributes: true, attributeFilter: ["class", "hidden"],
    }));
    window.addEventListener("resize", () => requestAnimationFrame(floatColumnMenus));
  }

  function closeToolMenus() {
    document.querySelectorAll(".ub-toolmenu .ub-toolpop").forEach(unfloat);
    document.querySelectorAll(".ub-toolmenu.open").forEach((menu) => menu.classList.remove("open"));
  }

  function syncToolState() {
    const drawing = ["drawPenBtn", "drawEraseBtn"].some((id) => document.getElementById(id)?.classList.contains("active"));
    document.querySelector('[data-ub-menu="draw"]')?.classList.toggle("active", drawing);
    const labels = { draw: "ubToolDraw", create: "ubToolCreate" };
    document.querySelectorAll("[data-ub-menu]").forEach((button) => { button.title = t(labels[button.dataset.ubMenu]); });
  }

  // ------------------------------------------------------------ choices on the board
  // Some rules choices name things that are all on screen in this layout (a
  // card on the field, a player's side, the Interzone, the deck). For those,
  // the choice screen stays hidden and the player answers on the board: the
  // board gesture presses the matching button of the hidden screen, so the
  // engine round-trip stays the one app.js already does.

  const PICK_ATTRS = ["rulesPickItem", "rulesPersistItem", "rulesDistributeItem", "rulesRandomTarget", "rulesReplaceItem"];
  const kebab = (name) => name.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);

  function readBoardChoice() {
    if (!active() || !rulesOn() || isObserver) return null;
    const panel = document.getElementById("rulesChoicePanel");
    const popup = document.querySelector("body > .rules-player-target-panel");
    const source = popup || (panel && !panel.classList.contains("hidden") ? panel : null);
    if (!source) return null;
    const pending = latestState?.rulesEngine?.pendingChoice;
    const choice = {
      source,
      key: popup ? `popup:${pending?.id || ""}:${popup.querySelectorAll("button").length}` : `choice:${pending?.id || ""}:${pending?.kind || ""}`,
      kind: popup ? "player" : pending?.kind || "",
      items: new Map(),
      players: new Map(),
      drag: null,
      extras: [],
    };
    source.querySelectorAll("[data-rules-player-target], [data-player-target]").forEach((button) => {
      const id = button.dataset.rulesPlayerTarget || String(button.dataset.playerTarget || "").replace(/^player:/, "");
      if (id) choice.players.set(id, button);
    });
    PICK_ATTRS.forEach((attr) => {
      source.querySelectorAll(`[data-${kebab(attr)}]`).forEach((button) => choice.items.set(button.dataset[attr], button));
    });
    if (!popup && pending?.kind === "confrontation_destination" && pending.playerId === myPlayerId) {
      const buttons = new Map([...source.querySelectorAll("[data-rules-destination]")].map((button) => [button.dataset.rulesDestination, button]));
      choice.drag = { itemIds: new Set([pending.itemId]), targets: { interzone: buttons.get("interzone"), deck: buttons.get("deck_bottom") } };
      choice.extras = [...buttons].filter(([key]) => !["interzone", "deck_bottom"].includes(key)).map(([, button]) => button);
    } else if (!popup && pending?.kind === "confrontation_replace_interzone") {
      // the chosen Interzone card goes under the deck: drag it onto the deck (or click it)
      choice.drag = { itemIds: new Set(choice.items.keys()), targets: { deck: "item" } };
    }
    // only take over when every option has a place on the board
    const boardItems = [...choice.items.keys()].every((id) => boardCardEl(id));
    if (!boardItems || (!choice.items.size && !choice.players.size && !choice.drag)) return null;
    if (choice.drag && [...choice.drag.itemIds].some((id) => !boardCardEl(id))) return null;
    return choice;
  }

  function boardCardEl(itemId) {
    return [...document.querySelectorAll("#battlefield .bf-card[data-item-id]")].find((card) => card.dataset.itemId === itemId) || null;
  }

  function myDeckPile() {
    return document.querySelector('#ubMyPiles .field-pile[data-zone="deck"]');
  }

  function syncBoardChoice() {
    const choice = readBoardChoice();
    document.querySelectorAll(".ub-choice-pick, .ub-choice-drag, .ub-choice-target, .ub-target-over, .ub-drop-ok").forEach((node) => {
      node.classList.remove("ub-choice-pick", "ub-choice-drag", "ub-choice-target", "ub-target-over", "ub-drop-ok");
    });
    document.querySelectorAll(".ub-proxied").forEach((node) => node.classList.remove("ub-proxied"));
    const banner = document.getElementById("ubChoiceBanner");
    local.choice = choice;
    if (!choice) {
      banner?.classList.add("hidden");
      document.getElementById("gameScreen")?.classList.remove("ub-choosing");
      local.choiceKey = "";
      setSpotlight(null);
      setChoiceArrow(false);
      return;
    }
    if (local.choiceKey !== choice.key) {
      local.choiceKey = choice.key;
      local.choicePanelShown = "";
    }
    const panelShown = local.choicePanelShown === choice.key;
    if (!panelShown) choice.source.classList.add("ub-proxied");
    document.getElementById("gameScreen").classList.toggle("ub-choosing", !panelShown);
    choice.items.forEach((_button, itemId) => boardCardEl(itemId)?.classList.add(choice.drag ? "ub-choice-drag" : "ub-choice-pick"));
    if (choice.drag) {
      choice.drag.itemIds.forEach((itemId) => boardCardEl(itemId)?.classList.add("ub-choice-drag"));
      if (choice.drag.targets.interzone) document.getElementById("ubIzMe")?.classList.add("ub-drop-ok");
      if (choice.drag.targets.deck) {
        myDeckPile()?.classList.add("ub-drop-ok");
        document.getElementById("ubLeft")?.classList.add("ub-drop-ok");
      }
    }
    for (const side of choiceSides(choice)) {
      playerTargetNodes(side).forEach((node) => node.classList.add("ub-choice-target"));
    }
    renderChoiceBanner(choice, panelShown);
    // a destination: everything but the places the card can go is dimmed
    if (choice.drag && !panelShown) {
      const holes = [...choice.drag.itemIds].map(boardCardEl);
      if (choice.drag.targets.interzone) holes.push(document.getElementById("ubIzMe"));
      // the whole left column takes a card under the deck
      if (choice.drag.targets.deck) holes.push(document.getElementById("ubLeft"));
      holes.push(document.getElementById("ubChoiceBanner"));
      setSpotlight(holes.filter(Boolean));
    } else {
      setSpotlight(null);
    }
    setChoiceArrow(Boolean(choice.players.size) && !panelShown);
  }

  // which sides of the table can be picked in a player choice
  function choiceSides(choice) {
    const players = sidePlayers();
    return ["me", "opp"].filter((side) => players[side] && choice.players.has(players[side].id));
  }

  function playerTargetNodes(side) {
    return [
      document.querySelector(`#ubField .ub-side.${side}`),
      document.getElementById(side === "me" ? "ubWhoMe" : "ubWhoOpp"),
      document.getElementById(side === "me" ? "ubAvMe" : "ubAvOpp"),
      document.querySelector(`#ubTotals .ub-tside.${side}`),
    ].filter(Boolean);
  }

  function choiceSourceCardId(choice) {
    if (choice.kind === "player" && !document.getElementById("rulesBoardFlow")?.classList.contains("hidden")) return null;
    const pending = latestState?.rulesEngine?.pendingChoice;
    let placement = null;
    try { placement = pendingTriggeredPlacement; } catch (_error) { placement = null; }
    return placement?.payload?.cardId || pending?.sourceCardId || pending?.cardId || null;
  }

  function renderChoiceBanner(choice, panelShown) {
    let banner = document.getElementById("ubChoiceBanner");
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "ubChoiceBanner";
      banner.className = "ub-choice-banner";
      document.getElementById("gameScreen").appendChild(banner);
    }
    const geometry = local.geometry?.G;
    if (geometry) {
      banner.style.left = `${geometry.cx}px`;
      banner.style.top = `${Math.round(geometry.H / 3)}px`;
      banner.style.maxWidth = `${Math.round(Math.min(640, geometry.fieldR - geometry.fieldL - 2 * geometry.izW - 24))}px`;
    }
    const heading = choice.kind === "player" ? t("ubChoosePlayer") : document.getElementById("rulesChoiceHeading")?.textContent || "";
    const hint = choice.drag
      ? t(choice.drag.targets.interzone ? "ubDragDestination" : "ubDragToDeck")
      : choice.players.size && !choice.items.size ? t("ubClickPlayer") : t("ubClickCard");
    const cardId = choiceSourceCardId(choice);
    banner.innerHTML = `${cardId ? `<button type="button" class="ub-choice-source" data-log-card="${esc(cardId)}" title="${esc(cardName(cardId))}"><img src="${esc(cardImage(cardId))}" alt="${esc(cardName(cardId))}"></button>` : ""}
      <div class="ub-choice-copy"><strong>${esc(heading)}</strong><span>${esc(hint)}</span></div>
      <div class="ub-choice-actions">${choice.extras.map((button, index) => `<button type="button" data-ub-extra="${index}">${esc(button.querySelector("strong")?.textContent || button.textContent.trim())}</button>`).join("")}
      ${choice.drag ? "" : `<button type="button" class="ub-choice-panel-btn">${esc(t(panelShown ? "ubHideChoicePanel" : "ubShowChoicePanel"))}</button>`}</div>`;
    wireLogCardNames(banner);
    banner.querySelectorAll("[data-ub-extra]").forEach((button) => {
      button.onclick = () => choice.extras[Number(button.dataset.ubExtra)]?.click();
    });
    const panelButton = banner.querySelector(".ub-choice-panel-btn");
    if (panelButton) panelButton.onclick = () => {
      local.choicePanelShown = panelShown ? "" : choice.key;
      syncBoardChoice();
    };
    banner.classList.remove("hidden");
    placeChoiceBanner(banner, choice);
  }

  // the prompt sits at the upper third, but never over the cards it is about:
  // above them when there is room, otherwise below them
  function placeChoiceBanner(banner, choice) {
    const geometry = local.geometry?.G;
    if (!geometry) return;
    // phone, moving cards: the prompt stands over the left column, clear of
    // the Confrontation Zone (the column still takes a card under the deck)
    const side = Boolean(geometry.phone && choice.drag);
    banner.classList.toggle("ub-choice-side", side);
    if (side) {
      banner.style.maxWidth = `${Math.round(geometry.colW - 8)}px`;
      banner.style.left = `${Math.round(4 + banner.offsetWidth / 2)}px`;
      banner.style.top = `${Math.round(geometry.H / 2)}px`;
      return;
    }
    const ids = choice.drag ? [...choice.drag.itemIds] : [...choice.items.keys()];
    const rects = ids.map(boardCardEl).filter(Boolean).map((node) => node.getBoundingClientRect()).filter((rect) => rect.width > 0);
    const half = banner.offsetHeight / 2;
    const gap = 14;
    let center = Math.round(geometry.H / 3);
    if (rects.length) {
      const top = Math.min(...rects.map((rect) => rect.top));
      const bottom = Math.max(...rects.map((rect) => rect.bottom));
      if (center + half + gap > top && center - half - gap < bottom) {
        const above = top - gap - half;
        center = above - half >= 6 ? above : Math.min(geometry.H - half - 6, bottom + gap + half);
      }
    }
    banner.style.top = `${Math.round(Math.max(half + 6, center))}px`;
  }

  // a dark layer with holes over what can be used
  function setSpotlight(nodes) {
    let layer = document.getElementById("ubSpotlight");
    local.spotNodes = nodes && nodes.length ? nodes : null;
    if (!nodes || !nodes.length) {
      layer?.remove();
      return;
    }
    // a card still sliding to its place (board FLIP): the holes follow it until they settle
    if (!local.spotFollowing) local.spotStill = 0;
    if (!local.spotFrame) local.spotFrame = requestAnimationFrame(followSpotlight);
    if (!layer) {
      layer = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      layer.id = "ubSpotlight";
      layer.setAttribute("class", "ub-spotlight");
      layer.setAttribute("aria-hidden", "true");
      document.getElementById("gameScreen").appendChild(layer);
    }
    const W = window.innerWidth;
    const H = window.innerHeight;
    const pad = 6;
    const holes = nodes.map((node) => {
      const r = node.getBoundingClientRect();
      const x = r.left - pad, y = r.top - pad, w = r.width + pad * 2, h = r.height + pad * 2, k = 12;
      return `M${x + k} ${y}h${w - 2 * k}a${k} ${k} 0 0 1 ${k} ${k}v${h - 2 * k}a${k} ${k} 0 0 1 -${k} ${k}h-${w - 2 * k}a${k} ${k} 0 0 1 -${k} -${k}v-${h - 2 * k}a${k} ${k} 0 0 1 ${k} -${k}Z`;
    }).join("");
    layer.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const path = `M0 0H${W}V${H}H0Z${holes}`;
    if (layer.dataset.path !== path) {
      layer.dataset.path = path;
      layer.innerHTML = `<path fill-rule="evenodd" d="${path}"/>`;
      local.spotStill = 0;
    } else {
      local.spotStill = (local.spotStill || 0) + 1;
    }
  }

  function followSpotlight() {
    local.spotFrame = null;
    const nodes = local.spotNodes;
    if (!nodes || !document.getElementById("ubSpotlight")) return;
    const live = nodes.filter((node) => node.isConnected);
    if (!live.length || local.spotStill > 45) return;
    local.spotFollowing = true;
    setSpotlight(live);
    local.spotFollowing = false;
  }

  // player choice: an arrow from the card to the pointer
  function setChoiceArrow(on) {
    let svg = document.getElementById("ubChoiceArrow");
    if (!on) {
      if (svg) {
        svg.remove();
        document.removeEventListener("pointermove", moveChoiceArrow);
      }
      return;
    }
    if (svg) return;
    svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.id = "ubChoiceArrow";
    svg.setAttribute("class", "ub-choice-arrow");
    svg.setAttribute("aria-hidden", "true");
    svg.innerHTML = `<defs><marker id="ubArrowHead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z"/></marker></defs><path class="ub-arrow-line" marker-end="url(#ubArrowHead)"/>`;
    document.getElementById("gameScreen").appendChild(svg);
    document.addEventListener("pointermove", moveChoiceArrow, { passive: true });
    const opp = document.getElementById("ubAvOpp")?.getBoundingClientRect();
    if (opp) moveChoiceArrow({ clientX: opp.left + opp.width / 2, clientY: opp.bottom });
  }

  function moveChoiceArrow(event) {
    const path = document.querySelector("#ubChoiceArrow .ub-arrow-line");
    const from = document.querySelector("#ubChoiceBanner .ub-choice-source") || document.getElementById("rulesFloatingCard");
    const rect = from?.getBoundingClientRect();
    if (!path || !rect?.width) return;
    const startX = rect.left + rect.width / 2;
    const startY = rect.top + rect.height / 2;
    const curveX = startX + (event.clientX - startX) * .5;
    const curveY = Math.min(startY, event.clientY) - Math.min(120, Math.abs(event.clientX - startX) * .2 + 40);
    path.setAttribute("d", `M ${startX} ${startY} Q ${curveX} ${curveY} ${event.clientX} ${event.clientY}`);
    const players = sidePlayers();
    const over = sideUnder(event.clientX, event.clientY, event.target);
    for (const side of ["me", "opp"]) {
      playerTargetNodes(side).forEach((node) => node.classList.toggle("ub-target-over", over === side && local.choice?.players.has(players[side]?.id)));
    }
  }

  // which player a point of the screen names (their half of the field, header, icon or total)
  function sideUnder(clientX, clientY, target) {
    const node = target?.closest?.("#ubWhoMe, #ubWhoOpp, #ubAvMe, #ubAvOpp, #ubTotals .ub-tside");
    if (node) return node.id === "ubWhoMe" || node.id === "ubAvMe" || node.classList.contains("me") ? "me" : "opp";
    if (target?.closest?.(".ub-col, .hand-area, .ub-choice-banner, #inspectPanel")) return null;
    const G = local.geometry?.G;
    if (!G || clientX < G.fieldL || clientX > G.fieldR) return null;
    return clientX < G.cx ? "me" : "opp";
  }

  function choiceDropTarget(clientX, clientY) {
    const drag = local.choice?.drag;
    if (!drag) return null;
    const within = (node, pad = 0) => {
      const rect = node?.getBoundingClientRect();
      return rect && clientX >= rect.left - pad && clientX <= rect.right + pad && clientY >= rect.top - pad && clientY <= rect.bottom + pad;
    };
    // the deck: the pile itself, or anywhere in my side column
    if (drag.targets.deck && (within(myDeckPile(), 24) || (drag.targets.interzone && within(document.getElementById("ubLeft"))))) return "deck";
    if (drag.targets.interzone && within(document.getElementById("ubIzMe"))) return "interzone";
    return null;
  }

  function onChoicePointerDown(event) {
    const choice = local.choice;
    if (!choice || !active() || event.button !== 0 || local.choicePanelShown === choice.key) return;
    if (event.target.closest?.(".ub-choice-banner")) return;
    let card = event.target.closest?.("#battlefield .bf-card[data-item-id]");
    if (choice.drag && card && !choice.drag.itemIds.has(card.dataset.itemId)) {
      // overlapping cards: take the one the choice is about under the finger,
      // and never start a board drag of the others meanwhile
      card = document.elementsFromPoint(event.clientX, event.clientY)
        .map((node) => node.closest?.("#battlefield .bf-card[data-item-id]"))
        .find((node) => node && choice.drag.itemIds.has(node.dataset.itemId)) || null;
      if (!card) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
    }
    const itemId = card?.dataset.itemId;
    if (card && choice.drag?.itemIds.has(itemId)) {
      event.preventDefault();
      event.stopPropagation();
      startChoiceDrag(event, card, itemId);
      return;
    }
    if (card && choice.items.has(itemId)) {
      event.preventDefault();
      event.stopPropagation();
      choice.items.get(itemId).click();
      return;
    }
    if (!choice.players.size || event.target.closest?.("button:not(.ub-choice-target)")) return;
    const side = sideUnder(event.clientX, event.clientY, event.target);
    const button = side && choice.players.get(sidePlayers()[side]?.id);
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    button.click();
  }

  function startChoiceDrag(event, card, itemId) {
    const rect = card.getBoundingClientRect();
    const ghost = card.cloneNode(true);
    ghost.removeAttribute("id");
    ghost.className = `${card.className} ub-choice-ghost`;
    ghost.querySelectorAll(".ub-first-badge, .rules-target-reticle").forEach((node) => node.remove());
    Object.assign(ghost.style, {
      position: "fixed", left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px`,
      scale: "1", transform: "none", margin: "0", zIndex: "300", pointerEvents: "none",
    });
    const startX = event.clientX;
    const startY = event.clientY;
    let moved = false;
    const move = (e) => {
      if (!moved && Math.hypot(e.clientX - startX, e.clientY - startY) > 5) {
        moved = true;
        document.body.appendChild(ghost);
        card.classList.add("ub-choice-lifted");
      }
      if (!moved) return;
      ghost.style.transform = `translate(${e.clientX - startX}px, ${e.clientY - startY}px) rotate(-3deg)`;
      const over = choiceDropTarget(e.clientX, e.clientY);
      document.getElementById("ubIzMe")?.classList.toggle("ub-drop-over", over === "interzone");
      myDeckPile()?.classList.toggle("ub-drop-over", over === "deck");
    };
    const up = (e) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      ghost.remove();
      card.classList.remove("ub-choice-lifted");
      document.querySelectorAll(".ub-drop-over").forEach((node) => node.classList.remove("ub-drop-over"));
      const choice = local.choice;
      if (!choice?.drag) return;
      const over = moved ? choiceDropTarget(e.clientX, e.clientY) : null;
      const target = over && choice.drag.targets[over];
      if (target === "item") choice.items.get(itemId)?.click();
      else if (target) target.click();
      else if (!moved && choice.items.has(itemId)) choice.items.get(itemId).click();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  }

  // ------------------------------------------------------------ wrapping

  function wrap(name, make) {
    const original = window[name];
    if (typeof original !== "function") return;
    window[name] = make(original);
  }

  // cards drawn (hand up, deck down by as many): a "+N" over that player's hand
  function showDrawDeltas() {
    const counts = local.handDeckCounts || (local.handDeckCounts = new Map());
    const inGame = !document.getElementById("gameScreen")?.classList.contains("hidden");
    for (const player of Object.values(latestState?.players || {})) {
      const now = { hand: pileCount(player, "hand"), deck: pileCount(player, "deck") };
      const before = counts.get(player.id);
      counts.set(player.id, now);
      if (!before || !inGame) continue;
      const drawn = Math.min(now.hand - before.hand, before.deck - now.deck);
      if (drawn > 0) popDrawDelta(player.id, drawn);
    }
  }

  function popDrawDelta(playerId, drawn) {
    const mine = playerId === myPlayerId && !isObserver;
    const anchor = mine
      ? document.getElementById("myHandTray")
      : document.getElementById("opponentHandFan");
    const rect = anchor?.getBoundingClientRect();
    if (!rect || !rect.width) return;
    const pop = document.createElement("div");
    pop.className = `ub-draw-pop ${mine ? "me" : "opp"}`;
    pop.style.setProperty("--pc", playerColor(playerId));
    pop.textContent = `+${drawn}`;
    pop.setAttribute("aria-hidden", "true");
    // mine sits above the hand, the opponent's beside their fan (the totals are under it)
    pop.style.left = mine ? `${rect.left + rect.width / 2}px` : `${rect.right + 46}px`;
    pop.style.top = mine ? `${Math.max(60, rect.top - 30)}px` : `${Math.max(30, rect.top + rect.height / 2)}px`;
    document.body.appendChild(pop);
    setTimeout(() => pop.remove(), 1900);
  }

  // every hover preview (Stack, log, Inspect, choices) takes the size of the board one
  function sizeLikeBoardPeek(preview, anchor) {
    if (!preview || !anchor?.getBoundingClientRect) return;
    const rect = anchor.getBoundingClientRect();
    const height = Math.min(window.innerHeight - 24, Math.max(300, window.innerHeight * 0.52));
    const width = height / RATIO;
    const roomRight = window.innerWidth - rect.right;
    const leftPos = roomRight >= width + 16 ? rect.right + 12 : Math.max(8, rect.left - width - 12);
    preview.style.width = `${width}px`;
    preview.style.height = `${height}px`;
    preview.style.left = `${Math.min(leftPos, window.innerWidth - width - 8)}px`;
    preview.style.top = `${clamp(rect.top + rect.height / 2 - height / 2, 12, window.innerHeight - height - 12)}px`;
  }
  wrap("showCardPreview", (original) => function uiBetaShowCardPreview(cardId, anchorEl, ...rest) {
    const result = original.call(this, cardId, anchorEl, ...rest);
    if (active()) sizeLikeBoardPeek(document.querySelector("body > .card-preview:last-of-type"), anchorEl);
    return result;
  });
  wrap("showChoiceCardPreview", (original) => function uiBetaShowChoicePreview(source, ...rest) {
    const result = original.call(this, source, ...rest);
    if (active()) sizeLikeBoardPeek(document.querySelector("body > .choice-card-preview:last-of-type"), source);
    return result;
  });

  wrap("renderAll", (original) => function uiBetaRenderAll(...args) {
    const result = original.apply(this, args);
    if (active()) renderChrome();
    if (active()) showDrawDeltas();
    else if (local.handDeckCounts) local.handDeckCounts.clear();
    // a new game asks again for full screen on phones (see goImmersive)
    const inGame = !document.getElementById("gameScreen")?.classList.contains("hidden");
    if (inGame && !local.inGame && !document.fullscreenElement) local.immersiveTried = false;
    local.inGame = inGame;
    return result;
  });
  wrap("renderPiles", (original) => function uiBetaRenderPiles(...args) {
    if (active()) {
      // the previous piles live in the columns now: clear them first
      document.querySelectorAll("#ubMyPiles .field-pile, #ubOppPiles .field-pile").forEach((pile) => pile.remove());
    }
    const result = original.apply(this, args);
    if (active()) {
      movePiles();
      decorateScoreAdjust();
      repositionOpenPopovers();
      // a pile's menu (the deck's draw, shuffle, reveal...) floats over the page
      document.querySelectorAll(".ub-piles .field-pile .zone-popover").forEach((pop) => {
        pop.classList.remove("zone-popover-above");
        floatOver(pop, pop.closest(".field-pile"), { above: false });
      });
    }
    return result;
  });
  wrap("renderBattlefield", (original) => function uiBetaRenderBattlefield(...args) {
    const before = active() ? boardSnapshot() : null;
    const result = original.apply(this, args);
    placeManualStackCards();
    if (before) flyDepartures(before);
    return result;
  });
  // the cards the effects of a state update already stage (flights, destructions...)
  wrap("prepareRulesVfxBatch", (original) => function uiBetaPrepareVfxBatch(...args) {
    const events = original.apply(this, args);
    const claimed = new Set();
    const claim = (value) => { if (value) claimed.add(value); };
    for (const event of events || []) {
      const details = event?.entry?.details || {};
      [...(event?.stateDestroyed || []), ...(event?.cleanupMoves || [])].forEach((move) => claim(move.cardId));
      (details.stateActions?.destroyed || []).forEach((move) => { claim(move.itemId); claim(move.cardId); });
      [...(details.captured || []), ...(details.returned || []), ...(details.supportExiled || [])].forEach((move) => { claim(move?.itemId); claim(move?.cardId); });
      (details.effectResult?.itemIds || []).forEach(claim);
      claim(details.effectResult?.itemId);
      claim(event?.movedCard?.cardId);
      claim(event?.sacrifice?.cardId);
      claim(event?.supportWin?.cardId);
      claim(event?.supportWin?.itemId);
    }
    local.vfxClaims = { ids: claimed, at: Date.now() };
    return events;
  });
  wrap("resolveDrop", (original) => function uiBetaResolveDrop(ctx, ...rest) {
    // a card dragged off the field by hand already landed where it was dropped
    if (ctx?.itemId) local.droppedItem = { id: ctx.itemId, at: Date.now() };
    return original.call(this, ctx, ...rest);
  });
  // while a card is dragged, the drop-only areas (the empty Stalemate band) show up
  wrap("buildDragGhost", (original) => function uiBetaBuildDragGhost(...args) {
    if (active()) document.getElementById("gameScreen")?.classList.add("ub-dragging");
    return original.apply(this, args);
  });
  wrap("removeGhost", (original) => function uiBetaRemoveGhost(...args) {
    document.getElementById("gameScreen")?.classList.remove("ub-dragging");
    return original.apply(this, args);
  });
  wrap("renderChatMessages", (original) => function uiBetaRenderChatMessages(...args) {
    const result = original.apply(this, args);
    if (active()) renderChat();
    return result;
  });
  wrap("centerBoardInView", (original) => function uiBetaCenterBoard(...args) {
    if (active() && local.geometry) return fitBoard(local.geometry.G);
    return original.apply(this, args);
  });
  wrap("setZoomAt", (original) => function uiBetaSetZoomAt(...args) {
    if (active()) return undefined;
    return original.apply(this, args);
  });
  wrap("fieldCenterLogical", (original) => function uiBetaFieldCenter(...args) {
    if (active()) return fieldCenter();
    return original.apply(this, args);
  });
  wrap("battlefieldItemCenter", (original) => function uiBetaItemCenter(item, ...rest) {
    if (active()) {
      const center = itemCenter(item);
      if (center) return center;
    }
    return original.call(this, item, ...rest);
  });
  // in rules mode a casual drop onto a card must not stack it (Float is the
  // engine's job); manual mode keeps stacking
  wrap("stackAnchorAt", (original) => function uiBetaStackAnchorAt(...args) {
    if (active() && rulesOn()) return null;
    return original.apply(this, args);
  });
  wrap("applyHandCardHeight", (original) => function uiBetaApplyHandCardHeight(...args) {
    const result = original.apply(this, args);
    if (active()) setHandHoverScale();
    return result;
  });
  // an observer sees both hands: the right-hand player's along the top, the
  // left-hand player's along the bottom (faces when the server sends them)
  function observerFanHtml(player, bottom) {
    const hand = player?.zones?.hand || {};
    const count = hand.count !== undefined ? hand.count : (hand.cards || []).length;
    const cards = hand.cards || revealedHandSlots(hand, count);
    return Array.from({ length: count }, (_unused, index) => {
      const cardId = cards[index] || null;
      const center = index - (count - 1) / 2;
      const rotate = (bottom ? 1 : -1) * Math.max(-15, Math.min(15, center * 3.5));
      const style = `--fan-rotate:${rotate}deg;--fan-arc:${-Math.abs(center) * Math.abs(center) * 1.7}px;--fan-x:${center * 45}px;--fan-z:${index};--owner-color:${esc(playerColor(player.id))}`;
      return cardId
        ? `<button type="button" class="opponent-hand-card is-known" data-opponent-hand-card="${esc(cardId)}" style="${style}" title="${esc(cardName(cardId))}"><img src="${esc(cardImage(cardId))}" alt="${esc(cardName(cardId))}"></button>`
        : `<button type="button" class="opponent-hand-card is-hidden" style="${style}" aria-label="${esc(t("cards"))}"></button>`;
    }).join("");
  }
  function renderObserverFans() {
    const top = document.getElementById("opponentHandFan");
    let bottom = document.getElementById("ubObsHandFan");
    if (!active() || !isObserver || !top) {
      bottom?.remove();
      return;
    }
    if (!bottom) {
      bottom = document.createElement("div");
      bottom.id = "ubObsHandFan";
      bottom.className = "opponent-hand-fan ub-obs-hand-fan";
      top.parentElement.appendChild(bottom);
    }
    const { me, opp } = sidePlayers();
    [[top, opp, false], [bottom, me, true]].forEach(([fan, player, isBottom]) => {
      fan.classList.toggle("hidden", !player);
      fan.innerHTML = player ? observerFanHtml(player, isBottom) : "";
      fan.title = player ? `${player.name}: ${t("viewHand")}` : "";
      fan.onclick = (event) => {
        const card = event.target.closest("[data-opponent-hand-card]")?.dataset.opponentHandCard;
        if (card) showInspect(card);
        else if (player) openHandView(player.id);
      };
    });
  }
  wrap("renderOpponentHandFan", (original) => function uiBetaRenderOpponentHandFan(...args) {
    const result = original.apply(this, args);
    renderObserverFans();
    return result;
  });
  wrap("renderHandTray", (original) => function uiBetaRenderHandTray(...args) {
    const result = original.apply(this, args);
    if (active()) { holdNewHandCards(); fitHand(); markHandEligibility(); }
    else local.handSeen = null;
    return result;
  });
  // cards on the field are not moved by hand in the rules mode: the engine places them
  wrap("bindCardDragSource", (original) => function uiBetaBindCardDragSource(el, ctx, ...rest) {
    if (ctx?.kind === "battlefield") {
      el.addEventListener("pointerdown", (event) => {
        if (!active() || !rulesOn()) return;
        event.stopImmediatePropagation();
        if (event.button === 0) dragSupportFromInterzone(el, ctx.itemId, event);
      });
    }
    return original.call(this, el, ctx, ...rest);
  });
  wrap("renderRulesChoice", (original) => function uiBetaRenderRulesChoice(...args) {
    // the end-of-confrontation destinations come one card after the other: once
    // the first is on screen the next ones follow at once, without waiting for
    // the previous card's flight to land
    const pending = latestState?.rulesEngine?.pendingChoice;
    const destination = active() && pending?.kind === "confrontation_destination" && pending.playerId === myPlayerId;
    const chained = destination && Date.now() - local.destinationShownAt < 10000;
    let result;
    if (chained && typeof window.rulesAnimationsBusyFor === "function") {
      const busy = window.rulesAnimationsBusyFor;
      window.rulesAnimationsBusyFor = () => 0;
      try { result = original.apply(this, args); } finally { window.rulesAnimationsBusyFor = busy; }
    } else {
      result = original.apply(this, args);
    }
    if (destination && !document.getElementById("rulesChoicePanel")?.classList.contains("hidden")) local.destinationShownAt = Date.now();
    if (active()) markHandEligibility();
    if (local.built) syncBoardChoice();
    fitCardNames();
    return result;
  });
  wrap("renderSideboardEditor", (original) => function uiBetaRenderSideboardEditor(...args) {
    const result = original.apply(this, args);
    fitCardNames();
    return result;
  });
  wrap("armRulesBoardTargets", (original) => function uiBetaArmTargets(...args) {
    const result = original.apply(this, args);
    if (local.built) syncBoardChoice();
    return result;
  });
  wrap("clearRulesBoardTargets", (original) => function uiBetaClearTargets(...args) {
    const result = original.apply(this, args);
    if (local.built) queueMicrotask(syncBoardChoice);
    return result;
  });
  wrap("paintStaticText", (original) => function uiBetaPaintStaticText(...args) {
    const result = original.apply(this, args);
    localizeToggles();
    return result;
  });

  // connection and system notices (reconnecting, connection lost, refused
  // action...) are written into the journal instead of floating on the field
  function pushSystemNote(text, level) {
    const value = String(text || "").trim();
    if (!value || document.getElementById("gameScreen")?.classList.contains("hidden")) return;
    const last = local.system[local.system.length - 1];
    if (last && last.text === value && Date.now() / 1000 - last.at < 30) return;
    local.system.push({ at: Date.now() / 1000, text: value, level: level || "info" });
    if (local.system.length > 60) local.system.shift();
    renderChat();
  }
  wrap("setStatus", (original) => function uiBetaSetStatus(message, kind = "", ...rest) {
    const result = original.call(this, message, kind, ...rest);
    if (active()) pushSystemNote(message, kind || "info");
    return result;
  });
  // rules mode: a Manifestation of my Interzone that may enter Support is
  // dragged onto my Confrontation Zone to play it there (same as the menu)
  function supportFromInterzoneAllowed(item) {
    return Boolean(item)
      && item.fieldZone === "interzone"
      && battlefieldItemControllerId(item) === myPlayerId
      && currentPhaseUi().phase?.id === "confrontation_reaction"
      && latestState.rulesEngine?.priorityPlayerId === myPlayerId
      && cardsById.get(item.cardId)?.type === "manifestation"
      && rulesBattlefieldSupportAvailableClient(item);
  }

  function dragSupportFromInterzone(el, itemId, down) {
    const item = (latestState?.battlefield || []).find((entry) => entry.id === itemId);
    if (!supportFromInterzoneAllowed(item)) return;
    const zc = document.getElementById("ubZcMe");
    let moved = false;
    // no native image drag (it would cancel the pointer stream)
    down.preventDefault();
    const noNativeDrag = (event) => event.preventDefault();
    window.addEventListener("dragstart", noNativeDrag, true);
    const inZone = (event) => {
      const r = zc.getBoundingClientRect();
      return event.clientX >= r.left && event.clientX <= r.right && event.clientY >= r.top && event.clientY <= r.bottom;
    };
    const move = (event) => {
      const dx = event.clientX - down.clientX;
      const dy = event.clientY - down.clientY;
      if (!moved && Math.hypot(dx, dy) < 6) return;
      if (!moved) {
        moved = true;
        el.classList.add("ub-support-drag");
        zc.classList.add("ub-drop-ok");
      }
      // the board layer is zoomed: move in its own units
      const parent = el.parentElement;
      const k = parent && parent.offsetWidth ? parent.getBoundingClientRect().width / parent.offsetWidth : 1;
      el.style.translate = `${dx / (k || 1)}px ${dy / (k || 1)}px`;
      zc.classList.toggle("ub-drop-hover", inZone(event));
    };
    const end = (event) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
      window.removeEventListener("dragstart", noNativeDrag, true);
      el.style.translate = "";
      el.classList.remove("ub-support-drag");
      zc.classList.remove("ub-drop-ok", "ub-drop-hover");
      if (!moved) return;
      // the click that follows a drag is not a click on the card
      const swallow = (click) => { click.stopPropagation(); click.preventDefault(); };
      window.addEventListener("click", swallow, { capture: true, once: true });
      setTimeout(() => window.removeEventListener("click", swallow, true), 0);
      if (event.type !== "pointerup" || !inZone(event)) return;
      const current = (latestState?.battlefield || []).find((entry) => entry.id === itemId);
      if (!supportFromInterzoneAllowed(current)) return;
      const payload = { type: "set_rules_field_zone", itemId: current.id, cardId: current.cardId, faceUp: current.faceUp, fieldZone: "confrontation", x: current.x, y: current.y };
      requestCardPlacement(payload, { cardId: current.cardId, zone: "battlefield", itemId: current.id });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
  }

  // the beta table lays cards out itself: no manual layer order
  wrap("showContextMenu", (original) => function uiBetaShowContextMenu(x, y, items, ...rest) {
    if (active() && Array.isArray(items)) {
      const kept = [];
      for (const item of items.filter((entry) => entry && !entry.zOrder)) {
        if (item.separator && (!kept.length || kept[kept.length - 1].separator)) continue;
        kept.push(item);
      }
      while (kept.length && kept[kept.length - 1].separator) kept.pop();
      if (!kept.length) return undefined;
      items = kept;
    }
    return original.call(this, x, y, items, ...rest);
  });
  wrap("showToast", (original) => function uiBetaShowToast(text, isError = false, ...rest) {
    if (active() && !document.getElementById("gameScreen").classList.contains("hidden")) {
      pushSystemNote(text, isError ? "error" : "info");
      // an error still flashes briefly where the player is looking
      if (!isError) return undefined;
    }
    return original.call(this, text, isError, ...rest);
  });

  window.uiBeta = {
    active,
    enabled,
    placement,
    decorateCard,
    dropLogical,
    setEnabled(on) { setEnabled(on); apply(); },
  };

  installToggles();
  installTouch();
  apply();
})();
