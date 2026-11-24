// A rarity card that just entered the Hand must be visible: the perf rule that
// pauses rarity loops must not freeze the .ko-pop-in entrance (opacity 0 start).
const fs = require("fs");
const path = require("path");
const assert = require("assert");
const { chromium } = require("playwright");

(async () => {
  const css = fs.readFileSync(path.join(__dirname, "..", "public", "style.css"), "utf8");
  const rarities = ["foil", "silver", "gold", "desert", "galaxy", "void", "zen", "common"];
  let cards = "";
  for (const rarity of rarities) {
    for (const glitter of [false, true]) {
      const img = rarity === "desert" ? '<span class="rarity-desert-surface"><img alt=""></span>' : '<img alt="">';
      cards += `<div class="hand-card ko-pop-in ko-rarity-card rarity-${rarity}${glitter ? " rarity-glitter-fx" : ""}" data-k="${rarity}${glitter ? "-glitter" : ""}" style="width:90px;height:126px">${img}</div>`;
    }
  }
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1200, height: 800 } });
    await page.setContent(`<html><head><style>${css}</style></head><body>${cards}</body></html>`);
    await page.mouse.move(1199, 799);
    await page.waitForTimeout(600);
    const hidden = await page.$$eval("[data-k]", (els) => els
      .filter((el) => Number(getComputedStyle(el).opacity) < 0.99)
      .map((el) => el.dataset.k));
    assert.deepStrictEqual(hidden, [], `rarity cards left invisible after entering the Hand: ${hidden.join(", ")}`);
    console.log("rarity hand pop-in visibility: ok");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exit(1); });
