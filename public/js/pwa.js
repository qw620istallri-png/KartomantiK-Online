// Installed app (PWA): install button and iPhone guide, update banner, and
// coming back to the same seat after a reload.
// Loaded before app.js: declarations only, nothing runs at load time.

let deferredInstallPrompt = null;
let appUpdateRegistration = null;
let appUpdateRequested = false;

function appIsInstalled() {
  return window.matchMedia?.("(display-mode: fullscreen), (display-mode: standalone)").matches || navigator.standalone === true;
}
function isAppleMobile() {
  return /iPhone|iPad|iPod/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}
function isAppleSafari() {
  return isAppleMobile() && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(navigator.userAgent);
}

// the button only shows when installing is actually possible here
function renderInstallButton() {
  const button = $("#installAppBtn");
  if (!button) return;
  const canPrompt = Boolean(deferredInstallPrompt);
  const apple = isAppleMobile() && !appIsInstalled();
  button.classList.toggle("hidden", appIsInstalled() || (!canPrompt && !apple));
  button.textContent = t("installApp");
}
async function installApp() {
  if (deferredInstallPrompt) {
    const prompt = deferredInstallPrompt;
    deferredInstallPrompt = null;
    prompt.prompt();
    await prompt.userChoice.catch(() => null);
    renderInstallButton();
    return;
  }
  showInstallGuide();
}
function showInstallGuide() {
  const guide = $("#installGuide");
  if (!guide) return;
  const share = `<svg class="install-guide-share" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M8 7l4-4 4 4"/><path d="M6 11H5v10h14V11h-1"/></svg>`;
  guide.querySelector("h2").textContent = t("installGuideTitle");
  guide.querySelector("ol").innerHTML = [
    rulesText("installGuideStep1", { icon: "@@" }).split("@@").map(esc).join(share),
    esc(t("installGuideStep2")),
    esc(t("installGuideStep3")),
  ].map((step) => `<li>${step}</li>`).join("");
  guide.querySelector(".install-guide-note").textContent = isAppleSafari() ? "" : t("installGuideSafari");
  guide.querySelector("[data-install-close]").textContent = t("close");
  guide.classList.remove("hidden");
}
function initAppInstall() {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    renderInstallButton();
  });
  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    renderInstallButton();
  });
  $("#installAppBtn")?.addEventListener("click", installApp);
  $("#installGuide")?.addEventListener("click", (event) => {
    if (event.target.closest("[data-install-close]") || event.target.id === "installGuide") $("#installGuide").classList.add("hidden");
  });
  renderInstallButton();
}

// A new release installs a new service worker; the page offers a reload and
// never forces one (a game in progress is never interrupted).
function registerAppUpdates() {
  if (!("serviceWorker" in navigator) || !/^https?:$/.test(location.protocol)) {
    checkServedVersion();
    return;
  }
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (appUpdateRequested) reloadFresh();
  });
  navigator.serviceWorker.register("sw.js").then((registration) => {
    appUpdateRegistration = registration;
    const watch = (worker) => worker?.addEventListener("statechange", () => {
      if (worker.state === "installed" && navigator.serviceWorker.controller) onWorkerWaiting();
    });
    if (registration.waiting && navigator.serviceWorker.controller) onWorkerWaiting();
    registration.addEventListener("updatefound", () => watch(registration.installing));
  }).catch(() => {});
  if (new URLSearchParams(location.search).has("fresh")) history.replaceState(null, "", location.pathname);
  checkServedVersion();
  window.setInterval(checkAppUpdate, 30 * 60 * 1000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") checkAppUpdate();
  });
}
function checkAppUpdate() {
  appUpdateRegistration?.update().catch(() => {});
  checkServedVersion();
}
// The release the server serves now, read from its service worker file with
// every cache bypassed: whatever cache sits on the way (browser, proxy, host),
// a page older than the server is noticed. On the home screen it reloads at
// once; in a game it offers the reload.
const RELOADED_FOR_KEY = "kko_reloaded_for";
async function servedVersion() {
  try {
    const text = await (await fetch(`sw.js?check=${Date.now()}`, { cache: "no-store" })).text();
    return text.match(/const VERSION = "([^"]+)"/)?.[1] || null;
  } catch (error) { return null; }
}
async function checkServedVersion() {
  if (!/^https?:$/.test(location.protocol)) return;
  const served = await servedVersion();
  if (!served || served === STATIC_ASSET_VERSION) return;
  let alreadyTried = false;
  try { alreadyTried = sessionStorage.getItem(RELOADED_FOR_KEY) === served; } catch (error) { /* private mode */ }
  const inGame = !$("#gameScreen").classList.contains("hidden") && latestState && !latestState.ended;
  if (!inGame && !alreadyTried) {
    try { sessionStorage.setItem(RELOADED_FOR_KEY, served); } catch (error) { /* private mode */ }
    reloadFresh();
    return;
  }
  showAppUpdateBanner();
}
// a new service worker is waiting: if this page already is that release (it was
// reloaded fresh), the worker takes over quietly; otherwise the reload is offered
async function onWorkerWaiting() {
  const served = await servedVersion();
  if (served && served === STATIC_ASSET_VERSION) {
    appUpdateRegistration?.waiting?.postMessage({ type: "skip-waiting" });
    return;
  }
  showAppUpdateBanner();
}
// a one-off address no cache has ever seen; the address bar is cleaned up on load
function reloadFresh() {
  location.replace(`${location.pathname}?fresh=${Date.now()}`);
}
function showAppUpdateBanner() {
  let banner = $("#appUpdateBanner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "appUpdateBanner";
    banner.className = "app-update-banner";
    banner.setAttribute("role", "status");
    banner.addEventListener("click", (event) => {
      if (event.target.closest("[data-update-later]")) banner.classList.add("hidden");
      if (event.target.closest("[data-update-reload]")) applyAppUpdate();
    });
    document.body.appendChild(banner);
  }
  const inGame = !$("#gameScreen").classList.contains("hidden") && latestState && !latestState.ended;
  banner.innerHTML = `<span>${esc(t(inGame ? "updateAvailableInGame" : "updateAvailable"))}</span>`
    + `<button type="button" data-update-later>${esc(t("updateLater"))}</button>`
    + `<button type="button" class="primary" data-update-reload>${esc(t("updateReload"))}</button>`;
  banner.classList.remove("hidden");
}
function applyAppUpdate() {
  appUpdateRequested = true;
  const waiting = appUpdateRegistration?.waiting;
  if (waiting) waiting.postMessage({ type: "skip-waiting" });
  else reloadFresh();
}

// a reload (update, or the phone dropping the tab) comes back to the same seat
const RESUME_KEY = "kko_resume";
function saveResumeSession() {
  try {
    const code = joinedCode || codePlayer;
    if (code && joinedName) sessionStorage.setItem(RESUME_KEY, JSON.stringify({ code, name: joinedName }));
  } catch (error) { /* private mode */ }
}
function clearResumeSession() {
  try { sessionStorage.removeItem(RESUME_KEY); } catch (error) { /* private mode */ }
}
function resumeSession() {
  let saved = null;
  try { saved = JSON.parse(sessionStorage.getItem(RESUME_KEY) || "null"); } catch (error) { saved = null; }
  if (!saved?.code || !saved?.name) return false;
  connectAndJoin({ code: saved.code, name: saved.name });
  return true;
}
