// Crop tuner for compact battlefield cards (open the game with ?crop-tuner).
// Lets the cut of Manifestations and Wills be set by hand: where the top slice
// (title and art) starts and ends, and where the bottom slice (footer) starts
// and ends, in % of the printed card's height. The top slice always lies 1px
// over the bottom one. Values apply live to the board and stay saved in this
// browser; "Copier" gives them as JSON to bake into COMPACT_CROP_DEFAULTS.
(() => {
  const api = window.uiBeta?.compactCrop;
  if (!api || document.getElementById("ubCropTuner")) return;

  const KINDS = {
    manifestation: { label: "Manifestations", types: ["manifestation"], sample: "inner-deserts-066" },
    will: { label: "Volontés", types: ["persistent_will", "ephemeral_will"], sample: "inner-deserts-147" },
  };
  const FIELDS = [
    ["topFrom", "Partie haute : début"],
    ["topTo", "Partie haute : fin"],
    ["bottomFrom", "Partie basse : début"],
    ["bottomTo", "Partie basse : fin"],
  ];
  const PREVIEW_W = 220;
  let kind = "manifestation";
  const chosen = { manifestation: KINDS.manifestation.sample, will: KINDS.will.sample };

  const style = document.createElement("style");
  style.textContent = `
.ub-crop-tuner { position: fixed; z-index: 2000; right: 16px; top: 16px; width: min(620px, calc(100vw - 32px)); max-height: calc(100dvh - 32px); overflow: auto; box-sizing: border-box;
  padding: 14px 16px 16px; border-radius: 14px; border: 1px solid #d3a94266; background: #0e1018f2; color: #f2ead4; font: 14px/1.4 system-ui, sans-serif; box-shadow: 0 18px 50px #000c; }
.ub-crop-tuner.is-min > :not(header) { display: none; }
.ub-crop-tuner header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; cursor: move; user-select: none; }
.ub-crop-tuner h2 { flex: 1; margin: 0; font-size: 15px; color: #f0d98f; }
.ub-crop-tuner button { min-height: 32px; padding: 4px 12px; border-radius: 8px; border: 1px solid #d3a94266; background: #ffffff10; color: inherit; font: inherit; cursor: pointer; }
.ub-crop-tuner button:hover, .ub-crop-tuner button:focus-visible { background: #d3a94233; }
.ub-crop-tuner button[aria-pressed="true"] { background: #d3a942; color: #17120a; border-color: #d3a942; }
.ub-crop-tuner .tabs, .ub-crop-tuner .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.ub-crop-tuner .stage { display: grid; grid-template-columns: ${PREVIEW_W}px ${PREVIEW_W}px; gap: 16px; justify-content: center; margin-bottom: 12px; }
.ub-crop-tuner figure { margin: 0; text-align: center; font-size: 12px; color: #a9b2c6; }
.ub-crop-tuner figcaption { margin-top: 6px; }
.ub-crop-tuner .source { position: relative; width: ${PREVIEW_W}px; height: ${PREVIEW_W * 1.4}px; border-radius: 8px; overflow: hidden; background: #171714; }
.ub-crop-tuner .source img { display: block; width: 100%; height: 100%; object-fit: fill; }
.ub-crop-tuner .band { position: absolute; left: 0; right: 0; box-sizing: border-box; pointer-events: none; }
.ub-crop-tuner .band.top { border: 2px solid #4fd1c5; background: #4fd1c522; }
.ub-crop-tuner .band.bottom { border: 2px solid #f6ad55; background: #f6ad5522; }
.ub-crop-tuner .result { width: ${PREVIEW_W}px; margin: 0 auto; border-radius: 8px; filter: drop-shadow(0 8px 16px #000a); }
.ub-crop-tuner .row { display: grid; grid-template-columns: 150px 1fr 76px; align-items: center; gap: 10px; margin: 6px 0; }
.ub-crop-tuner .row label { font-size: 13px; }
.ub-crop-tuner .row.top label { color: #4fd1c5; }
.ub-crop-tuner .row.bottom label { color: #f6ad55; }
.ub-crop-tuner input[type="range"] { width: 100%; accent-color: #d3a942; }
.ub-crop-tuner input[type="number"], .ub-crop-tuner input[type="search"] { box-sizing: border-box; width: 100%; min-height: 30px; padding: 3px 6px; border-radius: 6px; border: 1px solid #d3a94255; background: #00000055; color: inherit; font: inherit; }
.ub-crop-tuner .picker { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: center; margin-bottom: 10px; }
.ub-crop-tuner .note { margin: 8px 0 0; font-size: 12px; color: #a9b2c6; }
.ub-crop-tuner .status { min-height: 1.4em; margin: 6px 0 0; font-size: 12px; color: #9ae6b4; }
@media (max-width: 560px) { .ub-crop-tuner .stage { grid-template-columns: 1fr; } .ub-crop-tuner .row { grid-template-columns: 1fr 64px; } .ub-crop-tuner .row input[type="range"] { grid-column: 1 / -1; grid-row: 2; } }
`;
  document.head.appendChild(style);

  const panel = document.createElement("section");
  panel.id = "ubCropTuner";
  panel.className = "ub-crop-tuner";
  panel.setAttribute("aria-label", "Réglage de la coupe des cartes compactes");
  panel.innerHTML = `
    <header><h2>Coupe des cartes compactes</h2><button type="button" data-act="min" aria-label="Réduire">–</button><button type="button" data-act="close" aria-label="Fermer">×</button></header>
    <div class="tabs" role="group" aria-label="Type de carte">${Object.entries(KINDS).map(([key, entry]) => `<button type="button" data-kind="${key}">${entry.label}</button>`).join("")}</div>
    <div class="picker"><label for="ubCropCard">Carte d'exemple</label><input type="search" id="ubCropCard" list="ubCropCardList" autocomplete="off"><datalist id="ubCropCardList"></datalist></div>
    <div class="stage">
      <figure><div class="source"><img alt=""><span class="band top"></span><span class="band bottom"></span></div><figcaption>Carte imprimée : <span style="color:#4fd1c5">haut</span> et <span style="color:#f6ad55">bas</span> gardés</figcaption></figure>
      <figure><div class="result bf-card-face ub-compact-card-face"><span class="ub-compact-crop ub-compact-crop-top"><img alt=""></span><span class="ub-compact-crop ub-compact-crop-bottom"><img alt=""></span></div><figcaption>Résultat sur le plateau</figcaption></figure>
    </div>
    <div class="fields">${FIELDS.map(([field, label]) => `<div class="row ${field.startsWith("top") ? "top" : "bottom"}"><label for="ubCrop-${field}">${label}</label><input type="range" min="0" max="100" step="0.1" data-field="${field}" aria-label="${label}"><input type="number" min="0" max="100" step="0.1" id="ubCrop-${field}" data-field="${field}"></div>`).join("")}</div>
    <div class="actions"><button type="button" data-act="copy">Copier les valeurs</button><button type="button" data-act="reset-kind">Réinitialiser ce type</button><button type="button" data-act="reset">Tout réinitialiser</button></div>
    <p class="status" role="status" aria-live="polite"></p>
    <p class="note">En % de la hauteur de la carte imprimée. La partie haute passe toujours 1 px par-dessus la partie basse. Les réglages s'appliquent tout de suite au plateau et restent enregistrés dans ce navigateur.</p>`;
  document.body.appendChild(panel);

  const $ = (selector) => panel.querySelector(selector);
  const status = (text) => { $(".status").textContent = text; };
  // the catalogue is a top-level "let" of cards.js: not a window property
  const catalogue = () => (typeof cardsById !== "undefined" ? cardsById : new Map());

  function cardsOfKind(key) {
    const types = KINDS[key].types;
    return [...catalogue().values()].filter((card) => types.includes(card.type));
  }
  function imageOf(cardId) {
    return typeof window.cardImage === "function" ? window.cardImage(cardId) : (catalogue().get(cardId)?.image || "");
  }

  function render() {
    const crop = api.get()[kind];
    panel.querySelectorAll("[data-kind]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.kind === kind)));
    panel.querySelectorAll("[data-field]").forEach((input) => { input.value = String(crop[input.dataset.field]); });
    const list = cardsOfKind(kind);
    $("#ubCropCardList").innerHTML = list.map((card) => `<option value="${String(card.name).replace(/"/g, "&quot;")}"></option>`).join("");
    if (!catalogue().get(chosen[kind])) chosen[kind] = list[0]?.id || chosen[kind];
    const card = catalogue().get(chosen[kind]);
    if (document.activeElement !== $("#ubCropCard")) $("#ubCropCard").value = card?.name || "";
    const src = imageOf(chosen[kind]);
    panel.querySelectorAll(".source img, .result img").forEach((img) => { if (img.getAttribute("src") !== src) img.src = src; });
    const H = PREVIEW_W * 1.4;
    Object.assign($(".band.top").style, { top: `${crop.topFrom / 100 * H}px`, height: `${(crop.topTo - crop.topFrom) / 100 * H}px` });
    Object.assign($(".band.bottom").style, { top: `${crop.bottomFrom / 100 * H}px`, height: `${(crop.bottomTo - crop.bottomFrom) / 100 * H}px` });
    const result = $(".result");
    result.classList.toggle("ub-compact-card-face-manifestation", kind === "manifestation");
    result.classList.toggle("ub-compact-card-face-will", kind === "will");
    result.style.height = `${PREVIEW_W * api.ratio(kind)}px`;
  }

  let pending = 0;
  function update(field, value) {
    const current = api.get();
    current[kind] = { ...current[kind], [field]: Number(value) };
    // the "+1px" overlap is in CSS; render the board at most once a frame
    cancelAnimationFrame(pending);
    pending = requestAnimationFrame(() => { api.set(current); render(); status(""); });
  }

  panel.addEventListener("input", (event) => {
    const field = event.target.dataset?.field;
    if (field && event.target.value !== "") update(field, event.target.value);
    if (event.target.id === "ubCropCard") {
      const card = cardsOfKind(kind).find((entry) => entry.name === event.target.value);
      if (card) { chosen[kind] = card.id; render(); }
    }
  });
  panel.addEventListener("click", async (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.kind) { kind = button.dataset.kind; render(); return; }
    const act = button.dataset.act;
    if (act === "close") panel.remove();
    if (act === "min") panel.classList.toggle("is-min");
    if (act === "reset") { api.reset(); render(); status("Valeurs d'origine remises."); }
    if (act === "reset-kind") {
      const current = api.get();
      current[kind] = api.defaults()[kind];
      api.set(current); render(); status(`${KINDS[kind].label} : valeurs d'origine remises.`);
    }
    if (act === "copy") {
      const text = JSON.stringify(api.get(), null, 2);
      try { await navigator.clipboard.writeText(text); status("Valeurs copiées : colle-les-moi dans le fil."); }
      catch { window.prompt("Copie ces valeurs :", text); }
    }
  });

  // drag the panel by its title bar
  const header = panel.querySelector("header");
  header.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button")) return;
    const rect = panel.getBoundingClientRect();
    const dx = event.clientX - rect.left;
    const dy = event.clientY - rect.top;
    header.setPointerCapture(event.pointerId);
    const move = (e) => {
      panel.style.left = `${Math.max(0, Math.min(window.innerWidth - 80, e.clientX - dx))}px`;
      panel.style.top = `${Math.max(0, Math.min(window.innerHeight - 40, e.clientY - dy))}px`;
      panel.style.right = "auto";
    };
    const up = () => { header.removeEventListener("pointermove", move); header.removeEventListener("pointerup", up); };
    header.addEventListener("pointermove", move);
    header.addEventListener("pointerup", up);
  });

  render();
  // the card catalogue may still be loading when the tuner opens
  if (!catalogue().size) {
    const wait = setInterval(() => { if (catalogue().size) { clearInterval(wait); render(); } }, 300);
  }
})();
