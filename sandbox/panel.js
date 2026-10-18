// Card sandbox panel (local only: injected by the server when KKO_SANDBOX=1).
// Open /?sandbox (or /?sandbox=<card id or scenario id>): the page joins a private
// session already set up for that card, on the new table (UI beta). The panel picks
// the card, reloads its state, plays the opponent's seat, replays the scenario's
// script step by step and records whether the card is validated.
(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  if (!params.has("sandbox")) return;

  const FILTER_KEY = "ko_sandbox_filter";
  const OPEN_KEY = "ko_sandbox_open";
  const TYPE_LABELS = { manifestation: "Manifestation", ephemeral_will: "Volonté éphémère", persistent_will: "Volonté persistante" };
  const STATUS_ICON = { ok: "✓", bug: "✗" };

  let cards = [];
  let validation = {};
  let current = null; // scenario summary sent by the server
  let seat = "me";
  let opponentPasses = true;
  let scriptReports = null;
  let selectedCardId = null;

  const storage = {
    get(key, fallback) { try { return localStorage.getItem(key) ?? fallback; } catch (error) { return fallback; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (error) { /* private mode */ } },
  };

  const el = (tag, attrs = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (key === "class") node.className = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else if (value !== undefined && value !== null && value !== false) node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of [].concat(children)) if (child != null) node.append(child);
    return node;
  };

  // ------------------------------------------------------------ server link

  const originalHandle = window.handleServerMessage;
  window.handleServerMessage = function sandboxHandleServerMessage(msg) {
    if (msg.type === "sandbox_scenario") {
      if (!current || current.id !== msg.scenario.id) scriptReports = null;
      current = msg.scenario;
      seat = msg.seat;
      opponentPasses = msg.opponentPasses;
      selectedCardId = current.cardId;
      render();
      return;
    }
    if (msg.type === "sandbox_step") {
      (scriptReports ||= []).push(msg.report);
      render();
      return;
    }
    if (msg.type === "sandbox_script_done") {
      scriptReports = msg.reports;
      scriptRunning = false;
      render();
      return;
    }
    if (msg.type === "sandbox_validation") {
      validation = msg.validation;
      for (const card of cards) card.validation = validation[card.id] || null;
      render();
      return;
    }
    return originalHandle.apply(this, arguments);
  };

  let scriptRunning = false;

  function load(target) {
    scriptReports = null;
    send({ type: "sandbox_load", ...target });
  }

  function start() {
    const wanted = params.get("sandbox") || "";
    const isCard = cards.some((card) => card.id === wanted);
    const name = storage.get("ko_name", "") || "Testeur";
    connectAndJoin({ name, sandbox: wanted ? (isCard ? { cardId: wanted } : { scenarioId: wanted }) : { cardId: firstScenarioCard() } });
  }

  function firstScenarioCard() {
    return (cards.find((card) => card.scenarios.length) || cards[0] || {}).id;
  }

  // ------------------------------------------------------------ panel

  const root = el("aside", { id: "sandboxPanel", class: storage.get(OPEN_KEY, "1") === "1" ? "open" : "" });
  const toggle = el("button", {
    id: "sandboxToggle", type: "button", title: "Bac à sable des cartes",
    onclick: () => {
      root.classList.toggle("open");
      storage.set(OPEN_KEY, root.classList.contains("open") ? "1" : "0");
    },
  }, "Bac à sable");
  document.body.append(toggle, root);

  function matches(card, query, filter) {
    if (query) {
      const text = `${card.number ?? ""} ${card.name} ${card.set}`.toLowerCase();
      if (!query.split(/\s+/).every((word) => text.includes(word))) return false;
    }
    const status = card.validation?.status;
    if (filter === "scenario") return card.scenarios.length > 0;
    if (filter === "todo") return !status;
    if (filter === "bug") return status === "bug";
    if (filter === "ok") return status === "ok";
    if (filter === "auto") return Boolean(card.validation?.auto);
    if (filter === "manual") return status === "ok" && !card.validation?.auto;
    if (filter === "partial") return card.coverage && card.coverage !== "automated";
    return true;
  }

  let query = "";

  function renderList() {
    const filter = storage.get(FILTER_KEY, "all");
    const rows = cards.filter((card) => matches(card, query.toLowerCase().trim(), filter));
    const done = cards.filter((card) => card.validation?.status === "ok").length;
    const auto = cards.filter((card) => card.validation?.auto).length;
    const bugs = cards.filter((card) => card.validation?.status === "bug").length;
    const list = el("ol", { class: "sb-list" }, rows.slice(0, 300).map((card) => el("li", {}, el("button", {
      type: "button",
      class: `sb-card${card.id === selectedCardId ? " selected" : ""}${card.validation ? ` ${card.validation.status}` : ""}`,
      onclick: () => { selectedCardId = card.id; load({ cardId: card.id }); },
    }, [
      el("span", { class: "sb-num" }, String(card.number ?? "").padStart(3, "0")),
      el("span", { class: "sb-name" }, card.name),
      card.scenarios.length ? el("span", { class: "sb-tag", title: "Scénario écrit" }, card.scenarios.some((s) => s.scripted) ? "script" : "scénario") : null,
      el("span", { class: `sb-state${card.validation?.auto ? " auto" : ""}`, title: card.validation?.note || "" }, STATUS_ICON[card.validation?.status] || "·"),
    ]))));
    return [
      el("div", { class: "sb-progress" }, `${done} validées (dont ${auto} auto) · ${bugs} en bug · ${cards.length} cartes`),
      el("div", { class: "sb-filters" }, [
        el("input", {
          type: "search", placeholder: "Nom ou numéro", value: query, "aria-label": "Chercher une carte",
          oninput: (event) => { query = event.target.value; refreshList(); },
        }),
        el("select", {
          "aria-label": "Filtre",
          onchange: (event) => { storage.set(FILTER_KEY, event.target.value); refreshList(); },
        }, [
          ["all", "Toutes"], ["scenario", "Avec scénario écrit"], ["todo", "À tester"],
          ["bug", "En bug"], ["ok", "Validées"], ["manual", "Validées à la main"], ["auto", "Validées automatiquement"],
          ["partial", "Automatisation partielle"],
        ].map(([value, label]) => el("option", { value, selected: value === filter }, label))),
      ]),
      list,
    ];
  }

  function refreshList() {
    const holder = root.querySelector(".sb-list-holder");
    if (!holder) return;
    holder.replaceChildren(...renderList());
    holder.querySelector("input[type=search]")?.focus();
    const input = holder.querySelector("input[type=search]");
    if (input) input.setSelectionRange(input.value.length, input.value.length);
  }

  function renderCurrent() {
    if (!current) return el("p", { class: "sb-muted" }, "Connexion…");
    const card = cards.find((entry) => entry.id === current.cardId) || {};
    const others = card.scenarios || [];
    const options = others.map((s) => [s.id, s.title])
      .concat((card.variants || []).map((s) => [s.id, `${s.title} (générique${s.scripted ? ", script" : ""})`]));
    const status = card.validation?.status;
    const note = el("textarea", { rows: 2, placeholder: "Note (ce qui ne va pas, ce qui a été vérifié)" });
    note.value = card.validation?.note || "";
    const steps = current.script || [];
    return el("section", { class: "sb-current" }, [
      el("h2", {}, [card.name || current.cardId, el("small", {}, ` ${TYPE_LABELS[card.type] || ""} · auto : ${card.coverage || "?"}`)]),
      el("label", { class: "sb-row" }, [
        "Scénario",
        el("select", { onchange: (event) => load({ scenarioId: event.target.value }) },
          options.map(([value, label]) => el("option", { value, selected: value === current.id }, label))),
      ]),
      el("div", { class: "sb-actions" }, [
        el("button", { type: "button", onclick: () => load({ scenarioId: current.id }) }, "Recharger"),
        el("button", { type: "button", class: seat === "opp" ? "active" : "", onclick: () => send({ type: "sandbox_seat" }) },
          seat === "opp" ? "Revenir à mon siège" : "Jouer l'adversaire"),
        el("label", { class: "sb-check" }, [
          el("input", { type: "checkbox", checked: opponentPasses, onchange: (event) => send({ type: "sandbox_opponent_passes", on: event.target.checked }) }),
          "L'adversaire passe tout seul",
        ]),
      ]),
      seat === "opp" ? el("p", { class: "sb-warn" }, "Tu joues le siège adverse.") : null,
      current.checks?.length ? el("div", { class: "sb-block" }, [
        el("h3", {}, "À vérifier"),
        el("ul", { class: "sb-checks" }, current.checks.map((line) => el("li", {}, line))),
      ]) : null,
      steps.length ? el("div", { class: "sb-block" }, [
        el("h3", {}, [
          "Script automatique",
          el("button", {
            type: "button", disabled: scriptRunning,
            onclick: () => { scriptRunning = true; scriptReports = []; render(); send({ type: "sandbox_run_script" }); },
          }, scriptRunning ? "En cours…" : "Rejouer"),
        ]),
        el("ol", { class: "sb-steps" }, steps.map((label, index) => {
          const report = (scriptReports || []).find((entry) => entry.step === index);
          const state = !report ? "" : (report.ok ? "ok" : "bug");
          return el("li", { class: state }, [
            el("span", { class: "sb-state" }, report ? (report.ok ? "✓" : "✗") : "·"),
            el("span", {}, [label || `Étape ${index + 1}`, report?.error ? el("em", {}, ` ${report.error}`) : null,
              report?.refusal ? el("em", {}, ` refusé : ${report.refusal}`) : null]),
          ]);
        })),
      ]) : null,
      el("div", { class: "sb-block" }, [
        el("h3", {}, ["Verdict", status ? el("small", {}, ` ${status === "ok" ? "validée" : "en bug"}${card.validation.auto ? " automatiquement" : ""} le ${card.validation.at.replace("T", " à ")}`) : null]),
        card.validation?.auto ? el("p", { class: "sb-muted" }, card.validation.note) : null,
        note,
        el("div", { class: "sb-actions" }, [
          el("button", { type: "button", class: "ok", onclick: () => validate("ok", note.value) }, "Valider"),
          el("button", { type: "button", class: "bug", onclick: () => validate("bug", note.value) }, "Signaler un bug"),
          status ? el("button", { type: "button", onclick: () => validate("todo", "") }, "Effacer") : null,
        ]),
      ]),
    ]);
  }

  function validate(status, note) {
    if (!current) return;
    send({ type: "sandbox_validate", cardId: current.cardId, scenarioId: current.id, status, note });
  }

  function render() {
    const listScroll = root.querySelector(".sb-list")?.scrollTop || 0;
    root.replaceChildren(
      el("header", {}, [el("strong", {}, "Bac à sable des cartes"), el("span", { class: "sb-muted" }, "local")]),
      renderCurrent(),
      el("div", { class: "sb-list-holder" }, renderList()),
    );
    const list = root.querySelector(".sb-list");
    if (list) list.scrollTop = listScroll;
  }

  render();
  fetch("/sandbox/index.json", { cache: "no-store" })
    .then((response) => response.json())
    .then((data) => {
      cards = data.cards || [];
      for (const card of cards) if (card.validation) validation[card.id] = card.validation;
      render();
      start();
    })
    .catch(() => {
      root.replaceChildren(el("p", { class: "sb-warn" }, "Index du bac à sable introuvable : lance le serveur avec KKO_SANDBOX=1."));
    });
})();
