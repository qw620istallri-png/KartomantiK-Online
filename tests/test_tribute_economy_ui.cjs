const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const publicRoot = path.join(root, "public");
const mime = {
  ".html": "text/html", ".js": "text/javascript",
  ".css": "text/css", ".json": "application/json",
};

(async () => {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    const file = path.resolve(
      publicRoot,
      `.${url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname)}`,
    );
    if (!file.startsWith(`${publicRoot}${path.sep}`)
      || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, {
      "Content-Type": mime[path.extname(file)] || "application/octet-stream",
    });
    fs.createReadStream(file).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({
    channel: process.env.BROWSER_CHANNEL || "chrome", headless: true,
  });
  try {
    const page = await browser.newPage();
    await page.route("**/*", (route) => (
      new URL(route.request().url()).hostname === "127.0.0.1"
        ? route.continue() : route.abort()
    ));
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => (
      cardsById.size === 450 && typeof rulesActionPaymentDraft === "function"
    ));
    const result = await page.evaluate(() => {
      const zero = {
        id: "tribute-ui-zero", type: "ephemeral_will",
        powerCost: "", cost: 0, effect: "",
      };
      const two = {
        id: "tribute-ui-two", type: "ephemeral_will",
        powerCost: "{R}{R}", cost: 2, effect: "",
      };
      cardsById.set(zero.id, zero);
      cardsById.set(two.id, two);
      myPlayerId = "p1";
      latestState = {
        ended: false, battlefield: [
          {
            id: "teapot", ownerId: "p1", controllerId: "p1",
            cardId: "pxp1zvyxfv16bdd_en", faceUp: true,
            fieldZone: "interzone", counters: {},
          },
          {
            id: "fog", ownerId: "p2", controllerId: "p2",
            cardId: "ul1tffi1wn5l3q5_en", faceUp: true,
            fieldZone: "field", counters: {},
          },
        ],
        tokens: [], phaseTracker: { turn: 4 },
        rulesEngine: { playPermissions: [], firstManifestationItemIds: {} },
        players: {
          p1: { zones: { hand: { cards: [] }, graveyard: { cards: [] }, receptacle: { cards: [] } } },
          p2: { zones: { hand: { cards: [] }, graveyard: { cards: [] }, receptacle: { cards: [] } } },
        },
      };
      const total = (card) => Object.values(
        rulesActionPaymentDraft({ cardId: card.id, zone: "hand" }, card, null)
          .paymentRequirements,
      ).reduce((sum, amount) => sum + Number(amount || 0), 0);
      const p1Zero = total(zero);
      const p1Two = total(two);
      myPlayerId = "p2";
      const p2Zero = total(zero);
      const p2Two = total(two);
      return { p1Zero, p1Two, p2Zero, p2Two };
    });
    assert.deepEqual(result, {
      p1Zero: 0, p1Two: 2, p2Zero: 1, p2Two: 3,
    });
    console.log("tribute economy UI: 4/4 passed");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
