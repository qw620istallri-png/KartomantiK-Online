const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const publicRoot = path.resolve(__dirname, "../public");
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };

(async () => {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    const file = path.resolve(publicRoot, "." + (url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname)));
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const failures = [];
  const check = (condition, message) => { if (!condition) failures.push(message); };
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 844, height: 390 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      // No remote card art is required to prove positioning, masks or animation timing.
      await page.route("**/*", (route) => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450 && typeof document.querySelector("#rarityEffectsToggleBtn").onclick === "function");
      const rarity = await page.evaluate(() => {
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        const fixture = document.createElement("div");
        fixture.id = "rarity-fixture";
        fixture.style.cssText = "position:fixed;left:60px;top:50px;display:flex;gap:20px;z-index:200";
        const surfaces = ["hand-card", "bf-card-face", "sideboard-card-art", "inspect-img"];
        for (const [index, kind] of surfaces.entries()) {
          const wrapper = document.createElement("div");
          if (kind === "inspect-img") wrapper.className = "inspect-panel";
          wrapper.style.cssText = "position:static;padding:0;width:100px;height:140px";
          wrapper.innerHTML = `<div data-probe="${kind}" class="${kind}${rarityClassAttr(index % 2 ? "desert-glitter" : "desert")}" style="width:100px;height:140px">${raritySurfaceMarkup(index % 2 ? "desert-glitter" : "desert", '<img src="card-back.webp" alt="">')}</div>`;
          fixture.appendChild(wrapper);
        }
        document.body.appendChild(fixture);
        rarityEffectsDisabled = false;
        applyRarityEffectsPreference();
        const hand = fixture.querySelector(".hand-card");
        wireCardHoverZoom(hand, "hand-card-hover-clone");
        hand.dispatchEvent(new MouseEvent("mouseenter"));
        const clone = document.querySelector(".hand-card-hover-clone");
        const position = getComputedStyle(clone).position;
        document.querySelector("#rarityEffectsToggleBtn").click();
        const disabled = [...fixture.querySelectorAll("[data-probe]"), clone].map((card) => {
          const surface = card.querySelector(".rarity-desert-surface");
          return {
            mask: getComputedStyle(surface).maskImage,
            filter: getComputedStyle(surface.querySelector("img")).filter,
            animation: getComputedStyle(surface).animationName,
            layers: [...surface.querySelectorAll("i")].every((layer) => getComputedStyle(layer).display === "none"),
            before: getComputedStyle(surface, "::before").display,
            after: getComputedStyle(surface, "::after").display,
          };
        });
        const disabledBorder = getComputedStyle(hand).borderTopWidth;
        document.querySelector("#rarityEffectsToggleBtn").click();
        const restored = getComputedStyle(hand.querySelector(".rarity-desert-surface")).maskImage;
        hand.dispatchEvent(new MouseEvent("mouseleave"));
        return { position, disabled, disabledBorder, restored };
      });
      const label = `${viewport.width}x${viewport.height}`;
      check(rarity.position === "fixed", `${label}: Desert hover clone must stay fixed (got ${rarity.position})`);
      for (const [index, surface] of rarity.disabled.entries()) {
        check(surface.mask === "none" && surface.filter === "none" && surface.animation === "none" && surface.layers && surface.before === "none" && surface.after === "none", `${label}: disabled Desert surface ${index}: ${JSON.stringify(surface)}`);
      }
      check(rarity.disabledBorder === "2px", `${label}: disabled Desert restores normal card border`);
      check(rarity.restored.includes("desert-edge-mask"), `${label}: re-enabling restores Desert`);
      if (process.env.SCREENSHOT_DIR) {
        fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true });
        await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `desert-enabled-${label}.png`) });
        await page.evaluate(() => { rarityEffectsDisabled = true; applyRarityEffectsPreference(); });
        await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `desert-disabled-${label}.png`) });
        await page.evaluate(() => { rarityEffectsDisabled = false; applyRarityEffectsPreference(); });
      }

      await page.emulateMedia({ reducedMotion: "reduce" });
      const reducedDesert = await page.evaluate(() => [...document.querySelectorAll("#rarity-fixture .rarity-desert-surface, #rarity-fixture .desert-storm-layer")].map((el) => getComputedStyle(el).animationName));
      check(reducedDesert.every((name) => name === "none"), `${label}: Desert respects reduced motion`);
      const reducedVoid = await page.evaluate(() => {
        const card = document.createElement("div");
        card.className = "ko-rarity-card rarity-void";
        document.body.appendChild(card);
        const animation = getComputedStyle(card).animationName;
        card.remove();
        return animation;
      });
      check(reducedVoid === "none", `${label}: other rarities keep their reduced-motion behavior`);

      for (const reduced of [false, true]) {
        await page.emulateMedia({ reducedMotion: reduced ? "reduce" : "no-preference" });
        const immediate = await page.evaluate(async () => {
          removeRulesVfx();
          document.querySelector("#rarity-fixture").classList.add("hidden");
          const card = [...cardsById.values()][0];
          card.image = "card-back.webp";
          const entry = {
            sequence: 801, type: "rules_action_resolved", actorId: "p1",
            details: { immediate: true, source: { cardId: card.id, zone: "battlefield" }, effectResult: { kind: "draw", playerId: "p1", count: 1 } },
          };
          lastRulesVfxSequence = 800;
          vfxSpeed = "fast";
          const state = { recentLog: [entry] };
          playRulesVfxBatch(prepareRulesVfxBatch(state));
          const panel = document.querySelector(".rules-vfx-immediate");
          const animation = panel?.getAnimations()[0];
          const rect = panel?.getBoundingClientRect();
          const result = {
            preview: Boolean(panel), text: panel?.textContent || "", name: cardName(card.id),
            beforeResult: !document.querySelector(".rules-vfx-impact-draw"),
            duration: animation?.effect.getTiming().duration || 0,
            noSpatialMotion: animation?.effect.getKeyframes().every((frame) => !frame.transform || frame.transform === "none") ?? false,
            contained: Boolean(rect && rect.left >= 0 && rect.top >= 0 && rect.right <= innerWidth && rect.bottom <= innerHeight),
            replay: prepareRulesVfxBatch(state).length,
          };
          // Finish the preview through its real queue timer; then the existing result VFX must play.
          await new Promise((resolve) => setTimeout(resolve, Math.max(1600, result.duration + 100)));
          result.afterResult = Boolean(document.querySelector(".rules-vfx-impact-draw"));
          removeRulesVfx();
          result.cleaned = !document.querySelector(".rules-vfx-immediate, .rules-vfx-resolve-reveal");
          // A second immediate resolution must still preview, and leaving must cancel its result.
          entry.sequence++;
          playRulesVfxBatch(prepareRulesVfxBatch({ recentLog: [entry] }));
          result.repeated = Boolean(document.querySelector(".rules-vfx-immediate"));
          removeRulesVfx();
          result.cancelled = rulesVfxQueue.length === 0 && rulesVfxQueueTimer === null && !document.querySelector(".rules-vfx-immediate");
          lastRulesVfxSequence = null;
          result.reconnectReplay = prepareRulesVfxBatch({ recentLog: [entry] }).length;
          // Several immediate resolutions received together must remain readable at catch-up speed.
          enqueueRulesVfx(() => 1, 1);
          const chain = Array.from({ length: 4 }, (_, index) => ({ ...entry, sequence: entry.sequence + index + 1 }));
          playRulesVfxBatch(prepareRulesVfxBatch({ recentLog: chain }));
          await new Promise((resolve) => setTimeout(resolve, 80));
          result.chainDuration = document.querySelector(".rules-vfx-immediate")?.getAnimations()[0]?.effect.getTiming().duration || 0;
          removeRulesVfx();
          return result;
        });
        check(immediate.preview && immediate.text.includes(immediate.name), `${label}: immediate effect identifies its source (${reduced ? "reduced" : "normal"})`);
        check(immediate.duration >= 1500 && immediate.beforeResult && immediate.afterResult, `${label}: immediate effect previews before its result: ${JSON.stringify(immediate)}`);
        check(immediate.contained, `${label}: immediate preview fits viewport`);
        check(!reduced || immediate.noSpatialMotion, `${label}: reduced-motion preview uses opacity only`);
        check(immediate.cleaned && immediate.repeated && immediate.cancelled && immediate.replay === 0 && immediate.reconnectReplay === 0, `${label}: immediate animation cleanup, repetition and replay guards`);
        check(immediate.chainDuration >= 1500, `${label}: chained immediate effects keep their minimum reading time`);
      }
      if (process.env.SCREENSHOT_DIR) {
        await page.emulateMedia({ reducedMotion: "no-preference" });
        await page.evaluate(() => {
          const card = [...cardsById.values()][0];
          playRulesVfxResolveReveal({ actorId: "p1", details: { source: { cardId: card.id }, immediate: true } }, true);
          const animation = document.querySelector(".rules-vfx-immediate").getAnimations()[0];
          animation.pause();
          animation.currentTime = animation.effect.getTiming().duration * .4;
        });
        await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `immediate-${label}.png`) });
        await page.evaluate(() => removeRulesVfx());
      }
      check(errors.length === 0, `${label}: page errors: ${errors.join("; ")}`);
      await page.close();
    }
    assert.deepEqual(failures, [], failures.join("\n"));
    console.log("Desert rarity and immediate-effect animation regression: OK");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
