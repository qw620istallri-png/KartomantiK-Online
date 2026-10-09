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

(async () => {
  const server = await startServer();
  const port = server.address().port;
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  try {
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "networkidle" });
    await page.waitForFunction(() => typeof toggleHandHidden === "function");
    await page.evaluate(() => {
      latestState = { rulesEngine: null };
      myPlayerId = "p1";
      isObserver = false;
      handHiddenByUser = false;
      applyHandVisibility(myPlayerId);
      document.querySelector("#joinScreen").classList.add("hidden");
      document.querySelector("#gameScreen").classList.remove("hidden");
      window.__spaceFocusedButtonClicks = 0;
      const button = document.createElement("button");
      button.id = "spaceShortcutProbe";
      button.type = "button";
      button.textContent = "Probe";
      button.style.cssText = "position:fixed;left:20px;top:20px;z-index:99999";
      button.addEventListener("click", () => { window.__spaceFocusedButtonClicks += 1; });
      document.body.appendChild(button);
      button.focus();
    });

    await page.keyboard.press("Space");
    const buttonResult = await page.evaluate(() => ({
      focusedButtonClicks: window.__spaceFocusedButtonClicks,
      handHidden: document.querySelector("#myHandTray").classList.contains("hidden"),
    }));
    assert.equal(buttonResult.focusedButtonClicks, 0);
    assert.equal(buttonResult.handHidden, true);

    await page.evaluate(() => {
      document.querySelector("#spaceShortcutProbe").remove();
      handHiddenByUser = false;
      applyHandVisibility(myPlayerId);
      chatState = "open";
      applyChatState();
      document.querySelector("#chatPanel").classList.remove("hidden");
    });
    await page.locator("#chatInput").fill("hello");
    await page.locator("#chatInput").focus();
    await page.keyboard.press("Space");
    await page.keyboard.type("world");
    const chatResult = await page.evaluate(() => ({
      value: document.querySelector("#chatInput").value,
      handVisible: !document.querySelector("#myHandTray").classList.contains("hidden"),
    }));
    assert.equal(chatResult.value, "hello world");
    assert.equal(chatResult.handVisible, true);
    console.log("Hand space shortcut regression: OK");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
