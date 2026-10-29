const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const root = path.resolve(__dirname, "../public");
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://localhost");
    const file = path.resolve(root, "." + (url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname)));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.setHeader("Content-Type", ({ ".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".json": "application/json" })[path.extname(file)] || "application/octet-stream");
    fs.createReadStream(file).pipe(res);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, hasTouch: true });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/*", (route) => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => cardsById.size === 450 && typeof document.querySelector("#rarityEffectsToggleBtn").onclick === "function");
    const setup = async () => { await page.evaluate(() => {
      for (const card of cardsById.values()) card.image = "card-back.webp";
      const zone = () => ({ cards: [], count: 0, owners: {} });
      const player = (id, seat) => ({ id, name: id, seat, score: 0, zones: Object.fromEntries(ZONES.map((key) => [key, zone()])) });
      myPlayerId = "p1"; isObserver = false; connectionRole = "player";
      const cardId = [...cardsById.values()].find((card) => card.type === "manifestation").id;
      latestState = { players: { p1: player("p1", 0), p2: player("p2", 1) },
        battlefield: [{ id: "drag-source", cardId, ownerId: "p1", faceUp: true, x: 500, y: 1000, rotation: 0 }], tokens: [], drawings: [],
        phaseTracker: { enabled: false }, rulesEngine: { enabled: false, actionStack: [] } };
      window.__sent = []; send = (payload) => window.__sent.push(payload);
      document.querySelector("#joinScreen").classList.add("hidden");
      document.querySelector("#gameScreen").classList.remove("hidden");
      window.uiBeta.setEnabled(true);
      renderAll();
      if (!document.querySelector("#ubOppBlock").classList.contains("open")) document.querySelector("#ubOppBar").click();
    }); await page.waitForTimeout(400); };
    const points = async () => {
      const source = await page.locator('#battlefield [data-item-id="drag-source"]').boundingBox();
      const target = await page.locator('[data-drop-zone="p2:receptacle"] .pile-trigger').boundingBox();
      return { x: source.x + source.width / 2, y: source.y + source.height / 2,
        tx: target.x + target.width / 2, ty: target.y + target.height / 2 };
    };
    const count = () => page.locator(".drag-ghost").count();
    await setup();
    const p = await points();
    await page.mouse.move(p.x, p.y); await page.mouse.down();
    await page.mouse.move(p.tx, p.ty, { steps: 12 });
    assert.equal(await count(), 1);
    await page.mouse.up();
    assert.equal(await count(), 0);
    assert.equal(await page.evaluate(() => window.__sent[0]?.toZone), "receptacle");
    await page.evaluate(() => {
      const item = latestState.battlefield.pop();
      latestState.players.p2.zones.receptacle = { cards: [item.cardId], count: 1, owners: { [item.cardId]: "p1" } };
      renderAll();
    });
    assert.equal(await count(), 0);
    assert.equal(await page.locator('[data-field-pile="p2:receptacle"] img.pile-top-card').count(), 1);

    // A lost pointerup must not leave the 65%-opacity ghost following an idle mouse.
    await setup();
    const missingRelease = await page.evaluate(({ x, y, tx, ty }) => {
      const source = document.querySelector('#battlefield [data-item-id="drag-source"]');
      source.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, isPrimary: true, pointerId: 71, pointerType: "mouse", buttons: 1, clientX: x, clientY: y }));
      window.dispatchEvent(new PointerEvent("pointermove", { pointerId: 71, pointerType: "mouse", buttons: 1, clientX: tx, clientY: ty }));
      const ghost = document.querySelector(".drag-ghost");
      const before = { count: document.querySelectorAll(".drag-ghost").length, opacity: getComputedStyle(ghost).opacity };
      window.dispatchEvent(new PointerEvent("pointermove", { pointerId: 71, pointerType: "mouse", buttons: 0, clientX: tx + 4, clientY: ty }));
      const after = document.querySelectorAll(".drag-ghost").length;
      window.dispatchEvent(new Event("blur"));
      return { before, after, sent: window.__sent.length };
    }, await points());
    console.log("Missing-release reproduction:", missingRelease);
    assert.deepEqual(missingRelease, { before: { count: 1, opacity: "0.65" }, after: 0, sent: 0 });

    for (const interrupt of ["pointercancel", "blur", "pagehide", "hidden", "rerender", "new-gesture", "capture-lost"]) {
      await setup();
      const result = await page.evaluate(async ({ p, interrupt }) => {
        const source = document.querySelector('#battlefield [data-item-id="drag-source"]');
        const pointer = (type, id = 81, buttons = 1) => new PointerEvent(type, {
          bubbles: true, cancelable: true, isPrimary: true, pointerId: id, pointerType: "mouse", buttons, clientX: p.tx, clientY: p.ty,
        });
        source.dispatchEvent(pointer("pointerdown"));
        window.dispatchEvent(new PointerEvent("pointermove", { pointerId: 81, pointerType: "mouse", buttons: 1, clientX: p.tx - 20, clientY: p.ty }));
        const before = document.querySelectorAll(".drag-ghost").length;
        if (interrupt === "hidden") {
          Object.defineProperty(document, "hidden", { configurable: true, value: true });
          document.dispatchEvent(new Event("visibilitychange"));
          delete document.hidden;
        } else if (interrupt === "rerender") {
          renderBattlefield();
          await new Promise(queueMicrotask);
        } else if (interrupt === "new-gesture") {
          source.dispatchEvent(pointer("pointerdown", 82));
          window.dispatchEvent(new PointerEvent("pointercancel", { pointerId: 82 }));
        } else if (interrupt === "capture-lost") source.dispatchEvent(pointer("lostpointercapture"));
        else window.dispatchEvent(interrupt === "pointercancel" ? pointer(interrupt) : new Event(interrupt));
        // A late release/move after cancellation must not recreate a ghost or send a move.
        window.dispatchEvent(pointer("pointermove"));
        window.dispatchEvent(pointer("pointerup", 81, 0));
        return { before, after: document.querySelectorAll(".drag-ghost").length, highlighted: document.querySelectorAll(".drop-target-active").length,
          dragging: document.querySelector("#gameScreen").classList.contains("ub-dragging"), sent: window.__sent.length };
      }, { p: await points(), interrupt });
      assert.deepEqual(result, { before: 1, after: 0, highlighted: 0, dragging: false, sent: 0 }, interrupt);
    }

    await setup();
    const unrelatedPointer = await page.evaluate((p) => {
      const source = document.querySelector('#battlefield [data-item-id="drag-source"]');
      const fire = (target, type, id, x, buttons) => target.dispatchEvent(new PointerEvent(type, {
        bubbles: true, cancelable: true, isPrimary: true, pointerId: id, pointerType: "mouse", buttons, clientX: x, clientY: p.ty,
      }));
      source.addEventListener("pointerup", (e) => e.stopPropagation(), { once: true });
      fire(source, "pointerdown", 91, p.tx - 30, 1);
      fire(window, "pointermove", 91, p.tx, 1);
      fire(window, "pointercancel", 92, p.tx, 0);
      fire(window, "pointermove", 92, p.tx + 100, 0);
      const during = document.querySelectorAll(".drag-ghost").length;
      fire(source, "pointerup", 91, p.tx, 0);
      return { during, after: document.querySelectorAll(".drag-ghost").length, sent: window.__sent };
    }, await points());
    assert.equal(unrelatedPointer.during, 1);
    assert.equal(unrelatedPointer.after, 0);
    assert.equal(unrelatedPointer.sent.length, 1);
    assert.equal(unrelatedPointer.sent[0].toZone, "receptacle");

    // Real touch input uses browser pointer capture, including a state redraw mid-gesture.
    const cdp = await page.context().newCDPSession(page);
    for (const redraw of [false, true]) {
      await setup();
      const touch = await points();
      await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: touch.x, y: touch.y }] });
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: touch.tx, y: touch.ty }] });
      assert.equal(await count(), 1);
      if (redraw) {
        await page.evaluate(() => renderBattlefield());
        assert.equal(await count(), 0);
      }
      await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
      assert.equal(await count(), 0);
      assert.equal(await page.evaluate(() => window.__sent.length), redraw ? 0 : 1);
    }

    // A detached parent panel used to leave its fixed hover clone behind too.
    const hover = await page.evaluate(async () => {
      const panel = document.createElement("div");
      panel.innerHTML = '<div><div class="hover-probe"><img src="card-back.webp"></div></div>';
      document.body.appendChild(panel);
      const source = panel.querySelector(".hover-probe");
      wireCardHoverZoom(source, "db-card-hover-clone");
      lastPointerType = "touch";
      source.dispatchEvent(new MouseEvent("mouseenter"));
      const assertTouchHover = document.querySelectorAll(".db-card-hover-clone").length;
      lastPointerType = "mouse";
      source.dispatchEvent(new MouseEvent("mouseenter"));
      const before = document.querySelectorAll(".db-card-hover-clone").length;
      panel.remove();
      await new Promise(queueMicrotask);
      return { touch: assertTouchHover, before, after: document.querySelectorAll(".db-card-hover-clone").length };
    });
    assert.deepEqual(hover, { touch: 0, before: 1, after: 0 });

    // Slot choices must clean up on cancel without treating it as a selection.
    const slot = await page.evaluate(() => {
      const panel = document.createElement("div");
      panel.innerHTML = '<div class="slot-card"></div><button class="slot-target"></button>';
      Object.assign(panel.style, { position: "fixed", top: "5px", left: "5px" });
      document.body.appendChild(panel);
      const card = panel.querySelector(".slot-card"), target = panel.querySelector(".slot-target");
      let picks = 0;
      wireCardToSlots(card, [target], () => picks++);
      const fire = (node, type, buttons = 1) => node.dispatchEvent(new PointerEvent(type, {
        bubbles: true, cancelable: true, isPrimary: true, pointerId: 101, pointerType: "mouse", buttons, clientX: 15, clientY: 15,
      }));
      fire(card, "pointerdown"); fire(window, "pointermove"); fire(window, "pointercancel", 0);
      const canceled = { picks, dragging: card.classList.contains("is-dragging"), transform: card.style.transform, over: target.classList.contains("is-over") };
      fire(card, "pointerdown"); fire(window, "pointerup", 0);
      panel.remove();
      return { canceled, picks };
    });
    assert.deepEqual(slot.canceled, { picks: 0, dragging: false, transform: "", over: false });
    assert.equal(slot.picks, 1);

    const token = await page.evaluate(() => {
      const el = document.createElement("div");
      Object.assign(el.style, { left: "50px", top: "70px" });
      document.body.appendChild(el);
      let drops = 0;
      bindDrag(el, () => drops++);
      const fire = (node, type, x, buttons = 1) => node.dispatchEvent(new PointerEvent(type, {
        bubbles: true, cancelable: true, isPrimary: true, pointerId: 111, pointerType: "mouse", buttons, clientX: x, clientY: 15,
      }));
      fire(el, "pointerdown", 15); fire(window, "pointermove", 80); fire(window, "pointercancel", 80, 0);
      fire(window, "pointermove", 100); fire(window, "pointerup", 100, 0);
      const canceled = { drops, left: el.style.left, top: el.style.top };
      fire(el, "pointerdown", 15); fire(window, "pointermove", 80); fire(window, "pointerup", 80, 0);
      el.remove();
      return { canceled, drops };
    });
    assert.deepEqual(token.canceled, { drops: 0, left: "50px", top: "70px" });
    assert.equal(token.drops, 1);

    // The beta board's separate choice ghost must also disappear without selecting a destination.
    await setup();
    await page.evaluate(() => {
      const item = latestState.battlefield[0];
      item.fieldZone = "confrontation";
      latestState.phaseTracker = { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex(p => p.id === "confrontation_resolution"), turn: 2 };
      latestState.rulesEngine = { enabled: true, priorityPlayerId: "p1", actionStack: [], firstManifestationComplete: true,
        readyPlayerIds: ["p1", "p2"], deckConfirmedPlayerIds: ["p1", "p2"],
        pendingChoice: { id: "destination-cleanup", kind: "confrontation_destination", playerId: "p1", itemId: item.id, cardId: item.cardId, options: ["interzone", "deck_bottom"] } };
      renderAll();
    });
    await page.waitForFunction(() => document.querySelector(".ub-choice-drag"));
    await page.waitForTimeout(500);
    const choice = await page.locator("#battlefield .ub-choice-drag").boundingBox();
    await page.mouse.move(choice.x + choice.width / 2, choice.y + choice.height / 2); await page.mouse.down();
    await page.mouse.move(choice.x + choice.width + 20, choice.y + choice.height / 2);
    assert.equal(await page.locator(".ub-choice-ghost").count(), 1);
    await page.evaluate(() => window.dispatchEvent(new Event("blur")));
    await page.mouse.up();
    assert.equal(await page.locator(".ub-choice-ghost, .ub-choice-lifted, .ub-drop-over").count(), 0);
    assert.equal(await page.evaluate(() => window.__sent.length), 0);

    // The Support gesture moves the original element rather than a ghost.
    await setup();
    await page.evaluate(() => {
      latestState.battlefield[0].cardId = [...cardsById.values()].find(c => Number(c.collectionNumber) === 3).id;
      latestState.battlefield[0].fieldZone = "interzone";
      latestState.phaseTracker = { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex(p => p.id === "confrontation_reaction"), turn: 2 };
      latestState.rulesEngine = { enabled: true, priorityPlayerId: "p1", actionStack: [], firstManifestationComplete: true,
        readyPlayerIds: ["p1", "p2"], deckConfirmedPlayerIds: ["p1", "p2"] };
      renderAll();
    });
    await page.waitForTimeout(500);
    const support = await page.locator('#battlefield [data-item-id="drag-source"]').boundingBox();
    await page.mouse.move(support.x + support.width / 2, support.y + support.height / 2); await page.mouse.down();
    await page.mouse.move(support.x + support.width + 20, support.y + support.height / 2);
    assert.equal(await page.locator(".ub-support-drag").count(), 1);
    await page.evaluate(() => window.dispatchEvent(new Event("blur")));
    await page.mouse.up();
    assert.equal(await page.locator(".ub-support-drag, .ub-drop-ok, .ub-drop-hover").count(), 0);
    assert.equal(await page.evaluate(() => document.querySelector('#battlefield [data-item-id="drag-source"]').style.translate), "");
    assert.equal(await page.evaluate(() => window.__sent.length), 0);
    assert.deepEqual(errors, []);
    console.log("Drag cleanup regression: OK");
  } finally { await browser.close(); await new Promise((resolve) => server.close(resolve)); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
