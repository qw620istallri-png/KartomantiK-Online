const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const publicRoot = path.resolve(__dirname, "..", "public");
const mime = {
  ".css": "text/css", ".html": "text/html", ".js": "text/javascript",
  ".json": "application/json", ".png": "image/png", ".webp": "image/webp",
  ".woff2": "font/woff2",
};

function startServer() {
  return new Promise((resolve) => {
    const server = http.createServer((request, response) => {
      const urlPath = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
      const relative = urlPath === "/" ? "index.html" : urlPath.replace(/^\/+/, "");
      const filePath = path.resolve(publicRoot, relative);
      if (!filePath.startsWith(publicRoot + path.sep) || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        response.writeHead(404).end("Not found");
        return;
      }
      response.writeHead(200, { "Content-Type": mime[path.extname(filePath)] || "application/octet-stream" });
      fs.createReadStream(filePath).pipe(response);
    });
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

// Reported 12/11: a permanent +3 and a -3 on Sandokaron showed as two markers,
// and its Banner counter showed as a "+1", like a power bonus.
(async () => {
  const server = await startServer();
  const port = server.address().port;
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  try {
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "networkidle" });
    await page.waitForFunction(() => typeof counterCircles === "function");
    const result = await page.evaluate(() => {
      const render = (...args) => {
        const box = document.createElement("div");
        box.innerHTML = counterCircles(...args);
        return [...box.children].map((node) => ({
          text: node.textContent, classes: [...node.classList].sort(),
          name: node.dataset.counterName || null, title: node.title,
          icon: !!node.querySelector("svg.bf-counter-icon"),
        }));
      };
      const plus3 = { kind: "power_modifier", value: 3, duration: "while_target_on_field" };
      return {
        // +3 modifier, power capped back to the printed 5 (the old Trim): nothing
        cancelled: render({ Banner: 1 }, [plus3], 5, 5),
        // a counter -2 and a printed +2: the same kind, they add up to nothing
        counterAndContinuous: render({ power: -2 }, [], 5, 5),
        // +3 modifier and +1 counter: one +4 marker
        added: render({ power: 1 }, [plus3], 9, 5),
        // permanent and temporary markers stay apart
        mixed: render({ power: 2, tempCounter: -1 }, [], 6, 5),
        // manual tokens keep their plain essence counters
        token: render({ essence: 2 }, [], null, null, false),
      };
    });
    assert.deepEqual(result.cancelled, [{
      text: "1", classes: ["bf-counter", "bf-counter-special"], name: "Banner",
      title: "Banner counters: 1", icon: true,
    }]);
    assert.deepEqual(result.counterAndContinuous, []);
    assert.equal(result.added.length, 1);
    assert.equal(result.added[0].text, "+4");
    assert.ok(result.added[0].classes.includes("bf-counter-effect"));
    assert.match(result.added[0].title, /\+3/);
    assert.deepEqual(result.mixed.map((entry) => entry.text), ["+2", "-1"]);
    assert.ok(result.mixed[1].classes.includes("bf-counter-temp"));
    assert.deepEqual(result.token.map((entry) => [entry.text, entry.icon]), [["+2", false]]);
    if (process.env.SCREENSHOT_DIR) {
      await page.evaluate(() => {
        document.querySelector("#joinScreen").classList.add("hidden");
        const wrap = document.createElement("div");
        wrap.style.cssText = "position:fixed;left:40px;top:40px;z-index:99999;display:flex;gap:40px;padding:30px;background:#222";
        wrap.innerHTML = `<div class="bf-card" style="position:relative;width:120px;height:170px;background:#555"><div class="counters">${counterCircles({ Banner: 2, power: 1 }, [{ kind: "power_modifier", value: 3, duration: "while_target_on_field" }], 9, 5)}</div></div>`;
        document.body.appendChild(wrap);
      });
      fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, "counter-markers.png"), clip: { x: 0, y: 0, width: 400, height: 300 } });
    }
    console.log("Counter markers: OK");
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => { console.error(error); process.exit(1); });
