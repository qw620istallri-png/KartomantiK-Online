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
    ubToolDraw: "Dessin",
    ubToolCreate: "Créer (jeton, essence, dé)",
    ubChoosePlayer: "Choisis un joueur",
    ubClickPlayer: "Clique sur le côté du terrain (ou le nom) du joueur visé.",
    ubClickCard: "Clique sur une des cartes en surbrillance sur le terrain.",
    ubDragDestination: "Glisse la carte vers ton Interzone ou sur ton deck.",
    ubDragToDeck: "Glisse une carte en surbrillance sur ton deck (ou clique dessus).",
    ubShowChoicePanel: "Voir les options",
    ubHideChoicePanel: "Choisir sur le terrain",
    ubOption: "UI beta (nouvelle table)",
    ubOptionHint: "Moi à gauche, l’adversaire à droite, colonnes latérales. Réversible à tout moment depuis le menu de la partie.",
    ubMenuToggle: "UI beta",
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
    ubNoCard: "Aucune carte",
    ubEnlarge: "Agrandir",
    ubStack: "Stack",
    ubStackEmpty: "La Stack est vide.",
    ubTabAll: "Tout",
    ubTabChat: "Chat",
    ubTabLog: "Actions",
    ubNothingYet: "Rien pour l’instant.",
    ubFold: "Replier",
    ubUnfold: "Déplier",
    ubPilesOf: "Piles de",
    ubShowOppPiles: "Afficher les piles adverses",
    ubHideOppPiles: "Replier les piles adverses",
    ubLeads: "mène",
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
    ubToolDraw: "Drawing",
    ubToolCreate: "Create (token, essence, die)",
    ubChoosePlayer: "Choose a player",
    ubClickPlayer: "Click the targeted player's side of the field (or their name).",
    ubClickCard: "Click one of the highlighted cards on the field.",
    ubDragDestination: "Drag the card to your Interzone or onto your deck.",
    ubDragToDeck: "Drag a highlighted card onto your deck (or click it).",
    ubShowChoicePanel: "See the options",
    ubHideChoicePanel: "Choose on the field",
    ubOption: "UI beta (new table)",
    ubOptionHint: "Me on the left, the opponent on the right, side columns. Switch back any time from the game menu.",
    ubMenuToggle: "UI beta",
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
    ubNoCard: "No card",
    ubEnlarge: "Enlarge",
    ubStack: "Stack",
    ubStackEmpty: "The Stack is empty.",
    ubTabAll: "All",
    ubTabChat: "Chat",
    ubTabLog: "Actions",
    ubNothingYet: "Nothing yet.",
    ubFold: "Fold",
    ubUnfold: "Unfold",
    ubPilesOf: "Piles of",
    ubShowOppPiles: "Show the opponent’s piles",
    ubHideOppPiles: "Fold the opponent’s piles",
    ubLeads: "leads",
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
    ubToolDraw: "Disegno",
    ubToolCreate: "Crea (segnalino, essenza, dado)",
    ubChoosePlayer: "Scegli un giocatore",
    ubClickPlayer: "Clicca sul lato del campo (o sul nome) del giocatore bersaglio.",
    ubClickCard: "Clicca su una delle carte evidenziate sul campo.",
    ubDragDestination: "Trascina la carta nella tua Interzona o sul tuo mazzo.",
    ubDragToDeck: "Trascina una carta evidenziata sul tuo mazzo (o cliccala).",
    ubShowChoicePanel: "Vedi le opzioni",
    ubHideChoicePanel: "Scegli sul campo",
    ubOption: "UI beta (nuovo tavolo)",
    ubOptionHint: "Io a sinistra, l’avversario a destra, colonne laterali. Reversibile in ogni momento dal menu della partita.",
    ubMenuToggle: "UI beta",
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
    ubNoCard: "Nessuna carta",
    ubEnlarge: "Ingrandisci",
    ubStack: "Stack",
    ubStackEmpty: "Lo Stack è vuoto.",
    ubTabAll: "Tutto",
    ubTabChat: "Chat",
    ubTabLog: "Azioni",
    ubNothingYet: "Niente per ora.",
    ubFold: "Chiudi",
    ubUnfold: "Apri",
    ubPilesOf: "Pile di",
    ubShowOppPiles: "Mostra le pile avversarie",
    ubHideOppPiles: "Chiudi le pile avversarie",
    ubLeads: "in vantaggio",
    ubDropHint: "Rilascia una carta della mano ovunque sul campo",
    ubWaitingOpponent: "In attesa dell’avversario",
    ubFreeSlot: "libero",
    ubReceptacle: "Ricettacolo",
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
    eye: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.6"/></svg>',
  };

  const local = {
    chatTab: "all",
    chatFolded: false,
    unread: 0,
    seenChat: 0,
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
  };

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const qs = (selector, root = document) => root.querySelector(selector);

  function enabled() {
    try { return localStorage.getItem(ENABLED_KEY) === "1"; } catch (error) { return false; }
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
    };
    const info = new Map();
    (latestState?.battlefield || []).forEach((item, index) => {
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
    const colW = Math.round(clamp(W * 0.17, compact ? 150 : 220, 330));
    const fieldL = colW;
    const fieldR = W - colW;
    const fieldW = fieldR - fieldL;
    const cx = (fieldL + fieldR) / 2;
    const zcCount = Math.max(groups.me.confrontation.length, groups.opp.confrontation.length);
    const kBase = zcCount <= 2 ? 1.7 : zcCount <= 4 ? 1.6 : 1.5;
    const k = compact ? 1 + (kBase - 1) * 0.5 : kBase;
    const intW = clamp(W * 0.074, 78, 150);
    const izW = Math.round(Math.min(intW * k, fieldW * 0.2));
    const gutW = Math.round(clamp(W * 0.062, 56, 116));
    const handH = typeof handCardHeight === "number" ? handCardHeight : 170;
    const handCollapsed = document.getElementById("handArea")?.classList.contains("hand-collapsed");
    const handPeek = handCollapsed ? 48 : Math.round(handH * 0.62 + 18);
    const oppHandH = Math.round(clamp(H * 0.085, 46, 86));
    const totalsH = compact ? 44 : 54;
    const stale = groups.stalemate.length > 0;
    const staleH = stale ? 42 : 0;
    const bandTop = 0;
    const bandH = oppHandH + totalsH + staleH + 10;
    const zcTop = bandTop + bandH;
    const zcBottom = Math.max(zcTop + 120, H - handPeek);
    return {
      W, H, compact, colW, fieldL, fieldR, cx, izW, gutW, handPeek, oppHandH, totalsH, staleH, bandH,
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
    const bottom = G.H - 12;
    const available = bottom - top - labelH * 2 - 18;
    const wills = groups[side].will.length;
    const used = groups[side].interzone.length;
    const capacity = Math.max(player ? interzoneCapacity(player.id) : 3, used);
    const izShare = wills ? 0.64 : 0.82;
    const izH = Math.max(80, available * izShare);
    const pzH = Math.max(40, available - izH);
    const izTop = top + labelH;
    const pzTop = izTop + izH + 18 + labelH;
    const izFit = fit(inner, izH, capacity, { maxW: Math.min(inner * 0.9, 170), gap: 8, maxCols: 2 });
    const pzFit = fit(inner, pzH, Math.max(wills, 1), { maxW: Math.min(inner * 0.9, 150), gap: 8, maxCols: 2 });
    return {
      column, capacity, used, wills,
      iz: { t: izTop, h: izH, fit: izFit, labelY: top },
      pz: { t: pzTop, h: pzH, fit: pzFit, labelY: pzTop - labelH },
      divider: izTop + izH + 9,
    };
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
    for (const side of ["me", "opp"]) {
      const area = side === "me" ? G.zcMe : G.zcOpp;
      const count = groups[side].confrontation.length;
      const width = area.r - area.l;
      const cardFit = fit(width - 12, area.b - area.t - 30, count, { maxW: Math.min(230, width * 0.62) });
      zc[side] = { area, fit: cardFit };
      gridPositions({ l: area.l, r: area.r, t: area.t + 22, b: area.b - 8 }, count, cardFit, { fromRight: side === "me" })
        .forEach((rect, index) => slots.set(groups[side].confrontation[index].item.id, { ...rect, zone: "confrontation", side }));
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
          const cardFit = fit(half.r - half.l, half.b - half.t - 20, halves[side].length, { maxW: clamp(G.W * 0.09, 80, 130), gap: 10 });
          gridPositions({ ...half, t: half.t + 18 }, halves[side].length, cardFit, { centerY: false })
            .forEach((rect, index) => slots.set(halves[side][index].item.id, { ...rect, zone: "stalemate", side, open: true }));
        }
      } else {
        const stripW = Math.min(640, (G.zcOpp.r - G.zcMe.l) * 0.96);
        const strip = { l: G.cx - stripW / 2, r: G.cx + stripW / 2, t: G.oppHandH + G.totalsH + 6, h: 36 };
        stale.strip = strip;
        const w = 25;
        const shown = groups.stalemate.slice(0, 12);
        const totalW = shown.length * (w + 4) - 4;
        const start = G.cx - totalW / 2;
        groups.stalemate.forEach((entry, index) => {
          const i = Math.min(index, shown.length - 1);
          slots.set(entry.item.id, { x: start + i * (w + 4), y: strip.t + (strip.h - w * RATIO) / 2, w, zone: "stalemate", side: entry.side, strip: true, hiddenExtra: index >= shown.length });
        });
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
    const b = Math.min(G.zcBottom, t + Math.max(320, (G.zcBottom - t) * 0.82));
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
    if (meta.open) el.classList.add("ub-stale-open");
    if (meta.strip) el.classList.add("ub-stale-strip-card");
    if (meta.hiddenExtra) el.classList.add("ub-hidden-extra");
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
      <button type="button" class="ub-stale-strip hidden" id="ubStaleStrip"></button>
      <div class="ub-stale-panel hidden" id="ubStalePanel"></div>`;
    wrap.insertBefore(field, document.getElementById("battlefield"));

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
            <button type="button" class="ub-iconbtn ub-fold" id="ubChatFold" aria-expanded="true">${ICONS.chevron}</button>
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
        <div class="ub-stack-body" id="ubStackBody"><p class="ub-stack-empty" id="ubStackEmpty"></p></div>
      </section>
      <div class="ub-phase" id="ubPhase"><button type="button" class="ub-manual-pass hidden" id="ubManualPass" data-pass-phase></button></div>`;
    wrap.appendChild(left);
    wrap.appendChild(right);
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
        return;
      }
      if (event.target.closest(".ub-toolpop button")) {
        closeToolMenus();
        requestAnimationFrame(syncToolState);
      }
    });
    document.addEventListener("pointerdown", (event) => {
      if (!event.target.closest?.(".ub-toolmenu")) closeToolMenus();
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
    document.getElementById("ubStaleStrip").onclick = (event) => {
      event.stopPropagation();
      local.staleOpen = true;
      renderBattlefield();
      renderChrome();
    };
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
    document.addEventListener("pointerdown", hidePeek, true);
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

    window.addEventListener("resize", () => {
      if (!active() || !latestState) return;
      cancelAnimationFrame(local.resizeFrame);
      local.resizeFrame = requestAnimationFrame(() => {
        renderBattlefield();
        renderChrome();
      });
    });
    const observer = new MutationObserver(() => {
      if (active()) syncStackEmpty();
    });
    observer.observe(document.getElementById("rulesStackPanel"), { attributes: true, attributeFilter: ["class"] });
  }

  function boardPeekImage(card) {
    const item = latestState?.battlefield?.find((entry) => entry.id === card.dataset.itemId);
    if (!item || !item.cardId) return null;
    if (!item.faceUp && !(item.ownerId === myPlayerId || isObserver)) return null;
    return cardImage(item.cardId);
  }

  function schedulePeek(anchor, getSrc, delay) {
    hidePeek();
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
      if (cardsById.get(item.cardId)?.type !== "manifestation" && !item.isTokenCard) return;
      const order = Number(item.confrontationOrder || 0);
      if (!best || order > best.order || (order === best.order && index > best.index)) best = { item, order, index };
    });
    if (!best) return null;
    return best.item.effectiveTemperament || best.item.temperament || cardsById.get(best.item.cardId)?.temperaments?.[0] || null;
  }

  function sideHasConfrontation(playerId) {
    return (latestState?.battlefield || []).some((item) => (
      item.faceUp && item.fieldZone === "confrontation" && battlefieldItemControllerId(item) === playerId
      && (cardsById.get(item.cardId)?.type === "manifestation" || item.isTokenCard)
    ));
  }

  function leader(me, opp) {
    if (!me || !opp || !sideHasConfrontation(me.id) || !sideHasConfrontation(opp.id)) return null;
    const a = confrontationPowerOf(me.id);
    const b = confrontationPowerOf(opp.id);
    if (a !== b) return a > b ? "me" : "opp";
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
    totals.style.left = `${G.zcMe.l}px`;
    totals.style.width = `${G.zcOpp.r - G.zcMe.l}px`;
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
      const essence = pool.size
        ? `<div class="ub-ess" aria-label="${esc(t("essence"))}">${[...pool].map(([temperament, amount]) => `<span style="--ink:${esc(temperamentInk(temperament))}" title="${esc(t("essence"))} · ${esc(temperamentLabel(temperament))} ×${amount}"><img src="${esc(temperamentSymbol(temperament))}" alt="">${amount}</span>`).join("")}</div>`
        : "";
      return `<div class="ub-tside ${side}" style="--pc:${esc(playerColor(player.id))}">
        <div class="ub-total ${side}${lead === side ? " win" : ""}${lead === "tie" ? " tie" : ""}" style="--tc:${esc(ink)}" title="${esc(t("rulesPowerTotal"))}">
          <span class="ub-who2">${esc(player.name)}${lead === side ? ` · ${esc(t("ubLeads"))}` : ""}</span>
          <span class="ub-pw">${power}</span>
          <span class="ub-tmp">${key ? `<img src="${esc(temperamentSymbol(key))}" alt="${esc(temperamentLabel(key))}" title="${esc(t("rulesActiveTemperament"))}: ${esc(temperamentLabel(key))}">` : ""}</span>
        </div>${essence}
      </div>`;
    };
    totals.innerHTML = `${block("me", me)}<span class="ub-vs">${lead === "tie" ? "=" : "VS"}</span>${block("opp", opp)}`;
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
    RING.forEach((_key, index) => {
      const [x1, y1] = pos(index);
      const [x2, y2] = pos((index + 2) % 5);
      body += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="ub-wheel-line"/>`;
    });
    // Transcendent sits a little further from the circle than Hollow, whose
    // icon reads lower on its own
    const transY = -(R + 21);
    const hollowY = R + 17;
    body += `<line x1="0" y1="${transY + 8}" x2="0" y2="${-R - 2}" class="ub-wheel-line"/><line x1="0" y1="${R + 2}" x2="0" y2="${hollowY - 8}" class="ub-wheel-line"/>`;
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
    svg.innerHTML = `<defs><marker id="ubArrowHead" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z"/></marker></defs>${body}`;
    svg.classList.toggle("duel", Boolean(duel));
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
        <span class="ub-zlab" style="top:${col.iz.labelY}px"><span>${esc(t("ubInterzone"))}</span><b>${col.used}/${col.capacity}</b></span>
        ${free}
        <span class="ub-divider" style="top:${col.divider}px"></span>
        <span class="ub-zlab" style="top:${col.pz.labelY}px"><span>${esc(t("ubWills"))}</span><b>${col.wills}</b></span>`;
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
      empty.textContent = count ? "" : side === "me" ? (isObserver ? "" : t("ubDropHint")) : t("ubWaitingOpponent");
      empty.hidden = Boolean(count);
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
  }

  function renderStalemate(geometry) {
    const { G, groups, stale, players } = geometry;
    const strip = document.getElementById("ubStaleStrip");
    const panel = document.getElementById("ubStalePanel");
    const has = stale.count > 0;
    strip.classList.toggle("hidden", !has || local.staleOpen);
    panel.classList.toggle("hidden", !has || !local.staleOpen);
    document.getElementById("gameScreen").classList.toggle("ub-stale-open", has && local.staleOpen);
    if (!has) { local.staleOpen = false; return; }
    if (stale.strip) {
      setBox(strip, { l: stale.strip.l, r: stale.strip.r, t: stale.strip.t, b: stale.strip.t + stale.strip.h });
      const shown = Math.min(stale.count, 12);
      strip.innerHTML = `<span class="lab">${esc(t("ubStalemate"))} · ${stale.count}</span><span class="ub-strip-gap" style="width:${shown * 29}px"></span><span class="more">${stale.count > 12 ? `+${stale.count - 12}` : esc(t("ubEnlarge"))}</span>`;
    }
    if (stale.panel) {
      setBox(panel, stale.panel);
      const half = (side) => {
        const player = players[side];
        const n = groups.stalemate.filter((entry) => entry.side === side).length;
        return `<div class="ub-stale-half ${side}" style="--pc:${player ? esc(playerColor(player.id)) : "transparent"}"><h3>${esc(rulesText("ubStalemateOf", { player: player?.name || "" }))}</h3>${n ? "" : `<span class="ub-none">${esc(t("ubNoCard"))}</span>`}</div>`;
      };
      panel.innerHTML = `<header><h2>${esc(t("ubStalemateTitle"))}</h2><p>${esc(t("ubStalemateHint"))}</p></header><div class="ub-stale-rows">${half("me")}${half("opp")}</div>`;
    }
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
      const eye = side === "opp" && !isObserver
        ? `<button type="button" class="ub-iconbtn" data-ub-toggle-opp-hand aria-pressed="${opponentHandHiddenByUser}" title="${esc(t(opponentHandHiddenByUser ? "showOpponentHand" : "hideOpponentHand"))}">${eyeCardIconSvg(!opponentHandHiddenByUser)}</button>`
        : "";
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

  function renderOppBar(players) {
    const bar = document.getElementById("ubOppBar");
    const opp = players.opp;
    if (!opp) { bar.innerHTML = ""; return; }
    const mini = [["deck", "deck"], ["graveyard", "graveyard"], ["exile", "exile"], ["receptacle", "receptacle"]]
      .map(([zone]) => `<span class="mini">${esc(t(zone)).slice(0, 5)}<b>${pileCount(opp, zone)}</b></span>`).join("");
    const points = receptaclePoints(opp.zones.receptacle || {}, opp.score);
    bar.innerHTML = `<span class="v"><span class="long">${esc(t("ubPilesOf"))} </span>${esc(opp.name)}</span>${mini}<span class="pts">${points}</span><span class="chev">${ICONS.chevron}</span>`;
  }

  function syncStackEmpty() {
    const panel = document.getElementById("rulesStackPanel");
    const hidden = !panel || panel.classList.contains("hidden");
    const empty = document.getElementById("ubStackEmpty");
    if (empty) empty.hidden = !hidden;
    const stack = latestState?.rulesEngine?.actionStack || [];
    const count = document.getElementById("ubStackCount");
    if (count) count.textContent = stack.length ? String(stack.length) : "";
    document.getElementById("ubStack")?.classList.toggle("hidden", !rulesOn());
  }

  // the opponent's piles fold into a bar when the Stack needs the room
  function layoutRight() {
    const block = document.getElementById("ubOppBlock");
    const column = document.getElementById("ubRight");
    if (!block || !column) return;
    let open;
    if (local.oppPilesOpen === null) {
      const stackList = document.getElementById("rulesStackList");
      const stackNeed = (rulesOn() ? (stackList?.scrollHeight || 0) + 60 : 0);
      const full = block.querySelector(".ub-oppfull > div");
      const fullH = (full?.scrollHeight || 0) + 50;
      const used = document.getElementById("ubWhoOpp").offsetHeight + document.getElementById("ubPhase").offsetHeight + 60;
      open = stackNeed + fullH <= column.clientHeight - used;
    } else {
      open = local.oppPilesOpen;
    }
    block.classList.toggle("open", open);
    const bar = document.getElementById("ubOppBar");
    bar.setAttribute("aria-expanded", String(open));
    bar.title = t(open ? "ubHideOppPiles" : "ubShowOppPiles");
  }

  function renderPhaseExtras() {
    const button = document.getElementById("ubManualPass");
    const tracker = latestState.phaseTracker || {};
    const manual = tracker.enabled && !rulesOn() && !isObserver;
    button.classList.toggle("hidden", !manual);
    document.getElementById("ubPhase").classList.toggle("manual", Boolean(manual));
    if (!manual) return;
    const passed = new Set(tracker.passedPlayerIds || []);
    const mine = passed.has(myPlayerId);
    button.classList.toggle("active", mine);
    button.textContent = t(mine ? "cancelPhasePass" : "passPhase");
    wirePhasePassControls(document.getElementById("ubPhase"));
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
    const fresh = chatMessages.length - local.seenChat;
    if (fresh > 0) {
      const others = chatMessages.slice(-fresh).filter((message) => message.byId !== myPlayerId);
      if (local.chatFolded || local.chatTab === "log") local.unread += others.length;
      local.seenChat = chatMessages.length;
      if (others.length) pingMessage(others[others.length - 1]);
    }
    const tab = local.chatTab;
    const rows = chatEntries().filter((entry) => tab === "all" || entry.kind === tab).map((entry) => {
      if (entry.kind === "chat") {
        const message = entry.message;
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
    tabs.forEach((button) => {
      const key = button.dataset.ubTab;
      const label = button.querySelector("span") || button;
      label.textContent = t(labels[key]);
      button.setAttribute("aria-selected", String(key === tab));
    });
    const badge = document.querySelector("#ubChatTabs .ub-badge");
    badge.hidden = !local.unread;
    badge.textContent = String(Math.min(local.unread, 99));
    document.getElementById("ubChatInput").placeholder = t("chatPlaceholder");
    document.getElementById("ubChatSend").title = t("chatSend");
    document.getElementById("ubPlayerLogBtn").title = t("logHeader");
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
    screen.style.setProperty("--ub-fieldW", `${G.fieldR - G.fieldL}px`);
    screen.style.setProperty("--me", players.me ? playerColor(players.me.id) : "#3fc9a8");
    screen.style.setProperty("--opp", players.opp ? playerColor(players.opp.id) : "#d3654a");
    screen.classList.toggle("ub-rules", rulesOn());
    screen.classList.toggle("ub-compact", G.compact);
    renderZones(geometry);
    renderInterzones(geometry);
    renderTotals(G, players);
    renderWheel(G, players);
    renderStalemate(geometry);
    renderWho(players);
    renderScores(players);
    renderOppBar(players);
    renderPhaseExtras();
    syncStackEmpty();
    document.querySelector("#ubStack header b").textContent = t("ubStack");
    document.getElementById("ubStackEmpty").textContent = t("ubStackEmpty");
    renderChat();
    layoutRight();
    syncToolState();
    syncBoardChoice();
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
      screen.classList.add("ui-beta");
      relocate();
    } else if (screen.classList.contains("ui-beta")) {
      screen.classList.remove("ui-beta", "ub-rules", "ub-compact", "ub-stale-open");
      restoreAll();
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
    if (menu) menu.title = t("ubOptionHint");
  }

  // ------------------------------------------------------------ tools row

  function closeToolMenus() {
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
    document.querySelectorAll(".ub-choice-pick, .ub-choice-drag, .ub-choice-target, .ub-drop-ok").forEach((node) => {
      node.classList.remove("ub-choice-pick", "ub-choice-drag", "ub-choice-target", "ub-drop-ok");
    });
    document.querySelectorAll(".ub-proxied").forEach((node) => node.classList.remove("ub-proxied"));
    const banner = document.getElementById("ubChoiceBanner");
    local.choice = choice;
    if (!choice) {
      banner?.classList.add("hidden");
      document.getElementById("gameScreen")?.classList.remove("ub-choosing");
      local.choiceKey = "";
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
      if (choice.drag.targets.deck) myDeckPile()?.classList.add("ub-drop-ok");
    }
    const players = sidePlayers();
    choice.players.forEach((_button, playerId) => {
      const side = playerId === players.me?.id ? "me" : "opp";
      document.querySelector(`.ub-side.${side}`)?.classList.add("ub-choice-target");
      document.getElementById(side === "me" ? "ubWhoMe" : "ubWhoOpp")?.classList.add("ub-choice-target");
    });
    renderChoiceBanner(choice, panelShown);
  }

  function renderChoiceBanner(choice, panelShown) {
    let banner = document.getElementById("ubChoiceBanner");
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "ubChoiceBanner";
      banner.className = "ub-choice-banner";
      document.getElementById("ubField").appendChild(banner);
    }
    const heading = choice.kind === "player" ? t("ubChoosePlayer") : document.getElementById("rulesChoiceHeading")?.textContent || "";
    const hint = choice.drag
      ? t(choice.drag.targets.interzone ? "ubDragDestination" : "ubDragToDeck")
      : choice.players.size && !choice.items.size ? t("ubClickPlayer") : t("ubClickCard");
    banner.innerHTML = `<div><strong>${esc(heading)}</strong><span>${esc(hint)}</span></div>
      <div class="ub-choice-actions">${choice.extras.map((button, index) => `<button type="button" data-ub-extra="${index}">${esc(button.querySelector("strong")?.textContent || button.textContent.trim())}</button>`).join("")}
      <button type="button" class="ub-choice-panel-btn">${esc(t(panelShown ? "ubHideChoicePanel" : "ubShowChoicePanel"))}</button></div>`;
    banner.querySelectorAll("[data-ub-extra]").forEach((button) => {
      button.onclick = () => choice.extras[Number(button.dataset.ubExtra)]?.click();
    });
    banner.querySelector(".ub-choice-panel-btn").onclick = () => {
      local.choicePanelShown = panelShown ? "" : choice.key;
      syncBoardChoice();
    };
    banner.classList.toggle("hidden", false);
  }

  function choiceDropTarget(clientX, clientY) {
    const drag = local.choice?.drag;
    if (!drag) return null;
    const within = (node, pad = 0) => {
      const rect = node?.getBoundingClientRect();
      return rect && clientX >= rect.left - pad && clientX <= rect.right + pad && clientY >= rect.top - pad && clientY <= rect.bottom + pad;
    };
    if (drag.targets.deck && within(myDeckPile(), 24)) return "deck";
    if (drag.targets.interzone && within(document.getElementById("ubIzMe"))) return "interzone";
    return null;
  }

  function onChoicePointerDown(event) {
    const choice = local.choice;
    if (!choice || !active() || event.button !== 0 || local.choicePanelShown === choice.key) return;
    const header = event.target.closest?.("#ubWhoMe, #ubWhoOpp");
    if (header && !event.target.closest("button") && pickPlayerFromHeader(header.id === "ubWhoMe" ? "me" : "opp")) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    const card = event.target.closest?.("#battlefield .bf-card[data-item-id]");
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
    if (choice.players.size && !event.target.closest?.(".ub-col, .hand-area, .ub-choice-banner, #inspectPanel")) {
      const field = document.getElementById("ubField").getBoundingClientRect();
      const mid = document.querySelector(".ub-midline")?.getBoundingClientRect();
      const inField = event.clientX >= field.left && event.clientX <= field.right;
      if (!inField || !mid) return;
      const players = sidePlayers();
      const playerId = (event.clientX < mid.left ? players.me : players.opp)?.id;
      const button = choice.players.get(playerId);
      if (!button) return;
      event.preventDefault();
      event.stopPropagation();
      button.click();
    }
  }

  function pickPlayerFromHeader(side) {
    const choice = local.choice;
    if (!choice?.players.size) return false;
    const players = sidePlayers();
    const button = choice.players.get(players[side]?.id);
    if (!button) return false;
    button.click();
    return true;
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

  wrap("renderAll", (original) => function uiBetaRenderAll(...args) {
    const result = original.apply(this, args);
    if (active()) renderChrome();
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
      repositionOpenPopovers();
    }
    return result;
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
  wrap("renderRulesChoice", (original) => function uiBetaRenderRulesChoice(...args) {
    const result = original.apply(this, args);
    if (local.built) syncBoardChoice();
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
    if (level === "error" && (local.chatFolded || local.chatTab === "chat")) local.unread += 1;
    renderChat();
  }
  wrap("setStatus", (original) => function uiBetaSetStatus(message, kind = "", ...rest) {
    const result = original.call(this, message, kind, ...rest);
    if (active()) pushSystemNote(message, kind || "info");
    return result;
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
  apply();
})();
