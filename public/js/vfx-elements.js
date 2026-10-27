// Elemental effects on the cards: each Temperament has its element (fire, plant,
// ice, shadow, lightning, ash, light), played when a card is revealed, arrives,
// moves or does its effect.
// Loaded after vfx.js: declarations only, nothing runs at load time.

// ---------------------------------------------------------------- elemental effects
// A short burst of one element (fire, plant, ice, lightning, ash, sand, shadow,
// light) drawn on one shared canvas above the table. Nothing stays on the
// table: every emitter fades out on its own and the canvas goes away with the
// last one. Intensity follows the card's power, with a base that stays visible.
const VFX_ELEMENT_BY_TEMPERAMENT = {
  choleric: "fire", phlegmatic: "plant", vitreous: "ice", melancholic: "dark",
  capricious: "lightning", hollow: "ash", transcendent: "light",
};

const VFX_ELEMENT_PALETTES = {
  fire: ["#fff1b0", "#ffc24a", "#ff8a1f", "#ff4a1a", "#b81d0a"],
  goldfire: ["#fffbe0", "#ffe6a0", "#f1d377", "#d3a942", "#9a7420"],
  plant: ["#eaffb0", "#b8f060", "#6cc84a", "#2f9a3e"],
  ash: ["#e6e6e6", "#bdbdbd", "#8e8e8e", "#5e5e5e"],
  sand: ["#f6e2b0", "#e0c07e", "#c29a5a", "#8f6a3a"],
  dark: ["#e2c8ff", "#a870e8", "#6a2fb0", "#3a1070"],
};

// flame gradient stops and ground glow, per fire tint
const VFX_FIRE_TINTS = {
  fire: { stops: ["255,240,170", "255,170,40", "235,65,20", "120,10,0"], band: "255,90,20", embers: "fire" },
  goldfire: { stops: ["255,250,225", "255,220,120", "211,169,66", "120,90,20"], band: "230,180,70", embers: "goldfire" },
};

// bolt colours: halo, core, branch, sky flash
const VFX_LIGHTNING_TINTS = {
  gold: { halo: "255,214,90", core: "255,255,235", branch: "255,245,200", sky: "255,230,140", spark: "#ffd84a" },
  blood: { halo: "220,30,40", core: "255,232,232", branch: "255,150,150", sky: "120,0,20", spark: "#ff4a4a" },
};

const vfxElementEmitters = [];

let vfxElementCanvas = null;

let vfxElementScratch = null;

let vfxElementFrame = 0;

const vfxElementGlows = {};

function vfxElementRandom(index, salt) {
  const x = Math.sin(index * 127.1 + salt * 311.7) * 43758.5453;
  return x - Math.floor(x);
}

function vfxElementGlow(color) {
  if (vfxElementGlows[color]) return vfxElementGlows[color];
  const sprite = document.createElement("canvas");
  sprite.width = sprite.height = 48;
  const context = sprite.getContext("2d");
  const gradient = context.createRadialGradient(24, 24, 0, 24, 24, 24);
  gradient.addColorStop(0, "#ffffff");
  gradient.addColorStop(0.2, color);
  gradient.addColorStop(0.5, `${color}55`);
  gradient.addColorStop(1, `${color}00`);
  context.fillStyle = gradient;
  context.fillRect(0, 0, 48, 48);
  vfxElementGlows[color] = sprite;
  return sprite;
}

function vfxElementPalette(name, fraction) {
  const palette = VFX_ELEMENT_PALETTES[name] || VFX_ELEMENT_PALETTES.ash;
  return palette[Math.max(0, Math.min(palette.length - 1, Math.floor(fraction * palette.length)))];
}

// 0.4 with no power, full from 6 up: a weak card still shows its element
function vfxElementPowerFactor(power) {
  return 0.4 + 0.6 * Math.min(6, Math.max(0, Number(power) || 0)) / 6;
}

// Draws one element inside the rectangle R at time t (seconds), at strength alpha (0..1)
function drawVfxElement(cx, kind, t, R, alpha, tint) {
  const w = R.w;
  const h = R.h;
  const area = Math.min(1, (w * h) / (1080 * 1920) * 1.4 + 0.18);
  const count = (n) => Math.max(6, Math.round(n * area));
  const X = (i, s) => R.x + vfxElementRandom(i, s) * w;
  const rnd = vfxElementRandom;
  cx.save();
  cx.globalCompositeOperation = "lighter";
  const dot = (color, x, y, size, a) => {
    if (a <= 0.01) return;
    cx.globalAlpha = Math.min(1, a);
    cx.drawImage(vfxElementGlow(color), x - size / 2, y - size / 2, size, size);
  };
  const band = (y0, y1, rgb, a0, a1) => {
    const gradient = cx.createLinearGradient(0, y0, 0, y1);
    gradient.addColorStop(0, `rgba(${rgb},${a0})`);
    gradient.addColorStop(1, `rgba(${rgb},${a1})`);
    cx.globalAlpha = 1;
    cx.fillStyle = gradient;
    cx.fillRect(R.x, Math.min(y0, y1), w, Math.abs(y1 - y0));
  };
  switch (kind) {
    case "embers": {
      const palette = tint || "fire";
      for (let i = 0, n = count(80); i < n; i++) {
        const speed = 70 + rnd(i, 1) * 170;
        const travel = h * 1.15;
        const d = (t * speed + rnd(i, 2) * travel) % travel;
        const f = d / travel;
        const y = R.y + h + 20 - d;
        const x = X(i, 3) + Math.sin(t * (1.2 + rnd(i, 4) * 1.5) + i) * 30 * (0.4 + f);
        const size = (2.2 + rnd(i, 5) * 3.8) * (1 - f * 0.75);
        const life = (1 - f * f) * (0.6 + 0.4 * Math.sin(t * (9 + rnd(i, 6) * 10) + i * 3));
        dot(vfxElementPalette(palette, f), x, y, size * 7, alpha * life * 0.95);
        dot(vfxElementPalette(palette, 0), x, y, size * 2.4, alpha * life * (1 - f) * 0.8);
      }
      band(R.y + h, R.y + h * 0.72, VFX_FIRE_TINTS[palette]?.band || "255,110,30", 0.26 * alpha, 0);
      break;
    }
    case "fire": {
      const fire = VFX_FIRE_TINTS[tint] || VFX_FIRE_TINTS.fire;
      const [s0, s1, s2, s3] = fire.stops;
      band(R.y + h, R.y + h * 0.6, fire.band, 0.34 * alpha, 0);
      const n = Math.max(5, Math.round(w / 110));
      for (let i = 0; i < n; i++) {
        const speed = 1 + rnd(i, 31) * 1.8;
        const phase = rnd(i, 32) * 6.28;
        const bx = R.x + ((i + 0.5) / n) * w + Math.sin(t * speed * 1.7 + phase) * (w / n) * 0.25;
        const flicker = 0.75 + 0.25 * Math.sin(t * speed * 5 + phase) + 0.12 * Math.sin(t * speed * 11 + phase * 2);
        const h2 = h * (0.2 + 0.16 * rnd(i, 33)) * flicker * 1.05;
        const w2 = (w / n) * 1.7;
        cx.save();
        cx.translate(bx, R.y + h);
        cx.scale(w2 / h2, 1);
        const gradient = cx.createRadialGradient(0, -h2 * 0.35, 0, 0, -h2 * 0.35, h2 * 0.75);
        gradient.addColorStop(0, `rgba(${s0},${0.95 * alpha})`);
        gradient.addColorStop(0.28, `rgba(${s1},${0.85 * alpha})`);
        gradient.addColorStop(0.6, `rgba(${s2},${0.5 * alpha})`);
        gradient.addColorStop(1, `rgba(${s3},0)`);
        cx.globalAlpha = 1;
        cx.fillStyle = gradient;
        cx.fillRect(-h2, -h2 * 1.25, 2 * h2, 1.5 * h2);
        cx.restore();
      }
      cx.restore();
      drawVfxElement(cx, "embers", t, R, alpha * 0.9, fire.embers);
      cx.save();
      break;
    }
    case "ice": {
      const gradient = cx.createRadialGradient(R.x + w / 2, R.y + h / 2, Math.min(w, h) * 0.25, R.x + w / 2, R.y + h / 2, Math.max(w, h) * 0.75);
      gradient.addColorStop(0, "rgba(170,225,255,0)");
      gradient.addColorStop(1, `rgba(170,225,255,${0.42 * alpha})`);
      cx.globalAlpha = 1;
      cx.fillStyle = gradient;
      cx.fillRect(R.x, R.y, w, h);
      for (let i = 0, n = count(70); i < n; i++) {
        const speed = 30 + rnd(i, 51) * 70;
        const y = R.y + ((t * speed + rnd(i, 52) * (h + 100)) % (h + 100)) - 50;
        const x = X(i, 53) + Math.sin(t * 0.7 + i) * 30;
        const s = 3 + rnd(i, 55) * 9;
        cx.save();
        cx.translate(x, y);
        cx.rotate(t * (0.5 + rnd(i, 54)) + i);
        cx.scale(0.55, 1);
        cx.globalAlpha = alpha * (0.45 + 0.4 * rnd(i, 56));
        cx.fillStyle = "rgb(215,240,255)";
        cx.beginPath();
        cx.moveTo(0, -s); cx.lineTo(s, 0); cx.lineTo(0, s); cx.lineTo(-s, 0);
        cx.closePath();
        cx.fill();
        cx.restore();
      }
      for (let i = 0, n = count(24); i < n; i++) {
        const twinkle = Math.pow(Math.max(0, Math.sin(t * (1.5 + rnd(i, 57) * 2) + i * 4)), 3);
        if (twinkle < 0.05) continue;
        const x = X(i, 58);
        const y = R.y + rnd(i, 59) * h;
        const L = (14 + rnd(i, 50) * 26) * twinkle;
        dot("#ffffff", x, y, 22 * twinkle, alpha * twinkle);
        cx.globalAlpha = alpha * twinkle * 0.8;
        cx.strokeStyle = "rgb(235,248,255)";
        cx.lineWidth = 1.5;
        cx.beginPath();
        cx.moveTo(x - L, y); cx.lineTo(x + L, y); cx.moveTo(x, y - L); cx.lineTo(x, y + L);
        cx.stroke();
      }
      break;
    }
    case "lightning": {
      const colors = VFX_LIGHTNING_TINTS[tint] || VFX_LIGHTNING_TINTS.gold;
      const period = 0.55;
      const latest = Math.floor(t / period);
      for (let k = latest - 1; k <= latest; k++) {
        if (k < 0) continue;
        const struck = k * period + rnd(k, 61) * 0.2;
        const dt = t - struck;
        if (dt < 0 || dt > 0.6) continue;
        const e = Math.max(0, 1 - dt / 0.38) * (dt > 0.1 && dt < 0.17 ? 0.35 : 1);
        const x0 = R.x + w * (0.12 + 0.76 * rnd(k, 62));
        const ex = R.x + w * (0.12 + 0.76 * rnd(k, 63));
        const segments = 14;
        const points = [];
        for (let s = 0; s <= segments; s++) {
          points.push([
            x0 + (ex - x0) * (s / segments) + (s && s < segments ? (rnd(k * 31 + s, 64) - 0.5) * w * 0.14 : 0),
            R.y + h * (0.02 + 0.88 * (s / segments)),
          ]);
        }
        const bolt = (path, width, color) => {
          cx.beginPath();
          path.forEach((point, i) => (i ? cx.lineTo(point[0], point[1]) : cx.moveTo(point[0], point[1])));
          cx.lineWidth = width;
          cx.strokeStyle = color;
          cx.lineJoin = "round";
          cx.lineCap = "round";
          cx.stroke();
        };
        const branch = [points[5]];
        for (let s = 1; s <= 5; s++) {
          branch.push([
            points[5][0] + s * w * 0.04 * (rnd(k, 65) < 0.5 ? -1 : 1) + (rnd(k * 17 + s, 66) - 0.5) * w * 0.05,
            points[5][1] + s * h * 0.05,
          ]);
        }
        [[points, 26, 0.25], [points, 11, 0.55], [branch, 8, 0.3]].forEach(([path, width, a]) => {
          cx.globalAlpha = a * e * alpha;
          bolt(path, width, `rgb(${colors.halo})`);
        });
        cx.globalAlpha = e * alpha;
        bolt(points, 3.6, `rgb(${colors.core})`);
        cx.globalAlpha = 0.8 * e * alpha;
        bolt(branch, 1.6, `rgb(${colors.branch})`);
        cx.globalAlpha = 1;
        cx.fillStyle = `rgba(${colors.sky},${0.18 * e * alpha})`;
        cx.fillRect(R.x, R.y, w, h);
      }
      for (let i = 0, n = count(30); i < n; i++) {
        dot(colors.spark, X(i, 66), R.y + rnd(i, 67) * h, 8 + rnd(i, 68) * 10,
          alpha * Math.pow(Math.max(0, Math.sin(t * (4 + rnd(i, 69) * 6) + i * 5)), 4) * 0.9);
      }
      break;
    }
    case "plant": {
      band(R.y + h, R.y + h * 0.6, "60,160,70", 0.2 * alpha, 0);
      cx.globalCompositeOperation = "source-over";
      for (let i = 0, n = count(34); i < n; i++) {
        const speed = 40 + rnd(i, 71) * 60;
        const travel = h + 160;
        const d = (t * speed + rnd(i, 72) * travel) % travel;
        const y = R.y - 80 + d;
        const x = X(i, 73) + Math.sin(t * (0.6 + rnd(i, 74) * 0.8) + i) * 70 + d * 0.08;
        const s = 10 + rnd(i, 75) * 16;
        cx.save();
        cx.translate(x, y);
        cx.rotate(t * (0.8 + rnd(i, 76) * 1.4) + i * 2);
        cx.globalAlpha = alpha * 0.85;
        cx.fillStyle = vfxElementPalette("plant", 0.4 + rnd(i, 77) * 0.55);
        cx.beginPath();
        cx.moveTo(0, -s);
        cx.quadraticCurveTo(s * 0.9, -s * 0.2, 0, s);
        cx.quadraticCurveTo(-s * 0.9, -s * 0.2, 0, -s);
        cx.fill();
        cx.strokeStyle = "rgba(20,80,30,.6)";
        cx.lineWidth = 1;
        cx.beginPath();
        cx.moveTo(0, -s); cx.lineTo(0, s);
        cx.stroke();
        cx.restore();
      }
      cx.globalCompositeOperation = "lighter";
      for (let i = 0, n = count(40); i < n; i++) {
        const twinkle = 0.5 + 0.5 * Math.sin(t * (1.5 + rnd(i, 78) * 2) + i * 3);
        dot(i % 3 ? "#c8ff7a" : "#fff2a0", X(i, 79) + Math.sin(t * 0.5 + i * 1.3) * 40,
          R.y + rnd(i, 80) * h + Math.cos(t * 0.4 + i * 2.1) * 30,
          (8 + rnd(i, 81) * 10) * (0.6 + twinkle * 0.6), alpha * twinkle * 0.9);
      }
      break;
    }
    case "ash":
    case "sand": {
      const palette = kind;
      const sand = kind === "sand";
      band(R.y + h, R.y + h * (sand ? 0.3 : 0.55), sand ? "224,186,116" : "150,150,150", (sand ? 0.42 : 0.24) * alpha, 0);
      for (let i = 0, n = count(sand ? 90 : 60); i < n; i++) {
        dot(vfxElementPalette(palette, 0.3), X(i, 82) + Math.sin(t * 0.5 + i) * 30 + (sand ? (t * 60 + i * 9) % 40 : 0),
          R.y + h - ((t * (10 + rnd(i, 83) * 30) + rnd(i, 84) * h) % h), 16 + rnd(i, 85) * 30, alpha * (sand ? 0.7 : 0.45));
      }
      cx.globalCompositeOperation = "source-over";
      for (let i = 0, n = count(36); i < n; i++) {
        const speed = 180 + rnd(i, 86) * 340;
        const travel = h + 120;
        const d = (t * speed + rnd(i, 87) * travel) % travel;
        const s = (kind === "sand" ? 3 : 5) + rnd(i, 88) * (kind === "sand" ? 7 : 12);
        cx.save();
        cx.translate(X(i, 89) + Math.sin(i * 3) * 10 + (kind === "sand" ? d * 0.35 : 0), R.y - 60 + d);
        cx.rotate(t * (1 + rnd(i, 90) * 3) + i);
        cx.globalAlpha = alpha * 0.9;
        cx.fillStyle = vfxElementPalette(palette, rnd(i, 91));
        cx.beginPath();
        for (let j = 0; j < 5; j++) {
          const angle = (j / 5) * 6.283 + rnd(i * 7 + j, 92) * 0.8;
          const radius = s * (0.6 + rnd(i * 7 + j, 93) * 0.7);
          if (j) cx.lineTo(Math.cos(angle) * radius, Math.sin(angle) * radius);
          else cx.moveTo(Math.cos(angle) * radius, Math.sin(angle) * radius);
        }
        cx.closePath();
        cx.fill();
        cx.restore();
      }
      break;
    }
    case "dark": {
      const halo = cx.createRadialGradient(R.x + w / 2, R.y + h * 0.55, Math.min(w, h) * 0.12, R.x + w / 2, R.y + h * 0.55, Math.max(w, h) * 0.62);
      halo.addColorStop(0, `rgba(150,80,230,${0.42 * alpha})`);
      halo.addColorStop(0.55, `rgba(110,40,190,${0.24 * alpha})`);
      halo.addColorStop(1, "rgba(60,10,120,0)");
      cx.globalAlpha = 1;
      cx.fillStyle = halo;
      cx.fillRect(R.x, R.y, w, h);
      band(R.y + h, R.y + h * 0.5, "140,70,220", 0.35 * alpha, 0);
      cx.globalCompositeOperation = "source-over";
      for (let i = 0, n = count(14) + 4; i < n; i++) {
        const r = (120 + rnd(i, 94) * 160) * Math.sqrt(area) + 60;
        const x = X(i, 95) + Math.sin(t * 0.25 + i * 1.9) * 80;
        const y = R.y + rnd(i, 96) * h + Math.cos(t * 0.2 + i * 2.3) * 70;
        const smoke = cx.createRadialGradient(x, y, 0, x, y, r);
        smoke.addColorStop(0, `rgba(8,0,18,${0.32 * alpha})`);
        smoke.addColorStop(0.7, `rgba(40,0,70,${0.18 * alpha})`);
        smoke.addColorStop(1, "rgba(8,0,18,0)");
        cx.globalAlpha = 1;
        cx.fillStyle = smoke;
        cx.fillRect(x - r, y - r, 2 * r, 2 * r);
      }
      cx.globalCompositeOperation = "lighter";
      for (let i = 0, n = count(70); i < n; i++) {
        const speed = 30 + rnd(i, 97) * 60;
        const travel = h + 100;
        const d = (t * speed + rnd(i, 98) * travel) % travel;
        dot(vfxElementPalette("dark", rnd(i, 99) * 0.75), X(i, 100) + Math.sin(t * 0.7 + i) * 34, R.y + h + 50 - d,
          18 + rnd(i, 101) * 34, alpha * 0.95 * (1 - d / travel));
      }
      break;
    }
    case "light": {
      cx.save();
      cx.translate(R.x + w / 2, R.y + h / 2);
      cx.rotate(t * 0.12);
      for (let i = 0; i < 12; i++) {
        cx.rotate(6.283 / 12);
        const ray = cx.createLinearGradient(0, 0, 0, -h * 0.6);
        ray.addColorStop(0, `rgba(255,236,170,${0.22 * alpha})`);
        ray.addColorStop(1, "rgba(255,236,170,0)");
        cx.globalAlpha = 1;
        cx.fillStyle = ray;
        cx.beginPath();
        cx.moveTo(-6, 0); cx.lineTo(6, 0); cx.lineTo(28, -h * 0.6); cx.lineTo(-28, -h * 0.6);
        cx.closePath();
        cx.fill();
      }
      cx.restore();
      for (let i = 0, n = count(130); i < n; i++) {
        const twinkle = 0.5 + 0.5 * Math.sin(t * (1 + rnd(i, 7) * 3) + i);
        dot(i % 4 ? "#ffffff" : "#fff3c4", X(i, 5), R.y + rnd(i, 6) * h, (1.2 + rnd(i, 8) * 2.4) * 7 * (0.6 + twinkle * 0.6), alpha * (0.2 + 0.8 * twinkle));
      }
      for (let i = 0, n = count(70); i < n; i++) {
        const speed = 25 + rnd(i, 9) * 60;
        const y = R.y + ((t * speed + rnd(i, 10) * (h + 180)) % (h + 180)) - 90;
        const x = X(i, 11) + Math.sin(t * 1.4 + i * 2) * 40;
        const twinkle = 0.5 + 0.5 * Math.sin(t * 5 + i * 3);
        dot("#f2d27a", x, y, (1.5 + rnd(i, 12) * 2.5) * 8 * (0.5 + twinkle), alpha * (0.3 + 0.7 * twinkle));
      }
      break;
    }
    default:
      break;
  }
  cx.restore();
}

// Soft elliptical edges: nothing of the element shows a straight cut
function fadeVfxElementEdges(cx, Z) {
  cx.save();
  cx.globalCompositeOperation = "destination-in";
  cx.translate(Z.x + Z.w / 2, Z.y + Z.h / 2);
  cx.scale(Z.w / 2, Z.h / 2);
  const gradient = cx.createRadialGradient(0, 0, 0, 0, 0, 1);
  // fully clear before the zone's border, so a ground glow never ends on a line
  gradient.addColorStop(0, "#000");
  gradient.addColorStop(0.45, "#000");
  gradient.addColorStop(0.75, "rgba(0,0,0,.45)");
  gradient.addColorStop(0.93, "rgba(0,0,0,0)");
  cx.fillStyle = gradient;
  cx.fillRect(-1, -1, 2, 2);
  cx.restore();
}

// A rectangle (viewport pixels) for a board card, a DOM element, a point or a rect
function vfxElementRect(target) {
  if (!target) return null;
  if (typeof target === "string") {
    const element = rulesVfxFindBattlefieldItem(target);
    return element ? vfxElementRect(element) : null;
  }
  if (target.getBoundingClientRect) {
    const rect = target.getBoundingClientRect();
    return rect.width || rect.height ? { x: rect.left, y: rect.top, w: rect.width, h: rect.height } : null;
  }
  if (Number.isFinite(target.w)) return target;
  if (Number.isFinite(target.width)) return { x: target.left ?? target.x, y: target.top ?? target.y, w: target.width, h: target.height };
  if (Number.isFinite(target.x)) return { x: target.x - 50, y: target.y - 70, w: 100, h: 140 };
  return null;
}

// Plays one element over a target. A board card is followed by its item id,
// so a redrawn board keeps the effect on the card.
// options: duration (ms), delay (ms), envelope "burst" | "aura", power, grow
// (zone size against the target), tint, move (a function of progress 0..1 giving the rect)
function playVfxElement(kind, target, options = {}) {
  if (rulesVfxReducedMotion() || !kind) return;
  const itemId = typeof target === "string" ? target : target?.dataset?.itemId || null;
  let lastRect = vfxElementRect(target);
  if (!lastRect && !options.move) return;
  const rectNow = () => {
    if (itemId) lastRect = vfxElementRect(rulesVfxFindBattlefieldItem(itemId)) || lastRect;
    return lastRect;
  };
  // the oldest burst gives way when too many play at once
  if (vfxElementEmitters.length >= 8) vfxElementEmitters.shift();
  vfxElementEmitters.push({
    kind,
    tint: options.tint || null,
    rect: rectNow,
    move: options.move || null,
    start: performance.now() + vfxMs(options.delay || 0),
    duration: vfxMs(options.duration || 1400) / 1000,
    envelope: options.envelope || "burst",
    factor: vfxElementPowerFactor(options.power ?? 6),
    grow: Number(options.grow || 1.9),
    seed: Math.random() * 40,
  });
  if (!vfxElementFrame) vfxElementFrame = requestAnimationFrame(drawVfxElementFrame);
}

// a Will has no power: its Tribute cost stands for it
function vfxCardElementPower(card) {
  if (Number.isFinite(Number(card?.power)) && card?.power !== null) return Number(card.power);
  return (String(card?.powerCost || "").match(/\{/g) || []).length;
}

// The element of a card, from its temperament, at the strength of its power
function playVfxCardElement(cardId, target, options = {}) {
  const card = cardsById.get(cardId);
  const kind = VFX_ELEMENT_BY_TEMPERAMENT[card?.colorKey];
  if (!kind) return;
  playVfxElement(kind, target, { power: vfxCardElementPower(card), ...options });
}

function vfxElementStrength(emitter, t) {
  const total = emitter.duration;
  if (t < 0 || t > total) return 0;
  const tail = Math.min(1, (total - t) / Math.max(0.05, Math.min(0.8, total * 0.35)));
  if (emitter.envelope === "aura") return Math.min(1, t / 0.3) * tail;
  if (emitter.envelope === "effect") {
    // two pulses: the card gathers its element, then releases it
    const first = t < 0.1 ? t / 0.1 : Math.exp(-(t - 0.1) * 5);
    const second = t < 0.45 ? 0 : t < 0.55 ? (t - 0.45) / 0.1 : Math.exp(-(t - 0.55) * 3.2);
    return Math.min(1, first + second) * tail;
  }
  return (t < 0.12 ? t / 0.12 : Math.exp(-(t - 0.12) * 2.2)) * tail;
}

function drawVfxElementFrame(now) {
  vfxElementFrame = 0;
  if (vfxElementCanvas && !vfxElementCanvas.isConnected) {
    // the table was cleared (game left, reconnect): drop what was still playing
    vfxElementEmitters.length = 0;
    vfxElementCanvas = null;
  }
  for (let index = vfxElementEmitters.length - 1; index >= 0; index -= 1) {
    const emitter = vfxElementEmitters[index];
    if ((now - emitter.start) / 1000 > emitter.duration) vfxElementEmitters.splice(index, 1);
  }
  if (!vfxElementEmitters.length) {
    vfxElementCanvas?.remove();
    vfxElementCanvas = null;
    return;
  }
  const ratio = Math.min(1.5, window.devicePixelRatio || 1);
  if (!vfxElementCanvas) {
    vfxElementCanvas = document.createElement("canvas");
    vfxElementCanvas.className = "rules-vfx-elements";
    vfxElementCanvas.setAttribute("aria-hidden", "true");
    Object.assign(vfxElementCanvas.style, { position: "fixed", inset: "0", width: "100vw", height: "100vh", zIndex: "250", pointerEvents: "none" });
    document.body.appendChild(vfxElementCanvas);
  }
  const width = Math.round(window.innerWidth * ratio);
  const height = Math.round(window.innerHeight * ratio);
  if (vfxElementCanvas.width !== width || vfxElementCanvas.height !== height) {
    vfxElementCanvas.width = width;
    vfxElementCanvas.height = height;
  }
  const main = vfxElementCanvas.getContext("2d");
  main.setTransform(1, 0, 0, 1, 0, 0);
  main.clearRect(0, 0, width, height);
  vfxElementScratch = vfxElementScratch || document.createElement("canvas");
  for (const emitter of vfxElementEmitters) {
    const t = (now - emitter.start) / 1000;
    const strength = vfxElementStrength(emitter, t) * emitter.factor * (emitter.kind === "fire" ? 0.7 : 1);
    if (strength <= 0.01) continue;
    const base = emitter.move ? emitter.move(Math.min(1, Math.max(0, t / emitter.duration))) : emitter.rect();
    if (!base) continue;
    // the zone grows with the card's power
    const grow = emitter.grow * (0.7 + 0.3 * emitter.factor);
    const zoneW = Math.max(60, base.w * grow);
    const zoneH = Math.max(60, base.h * grow);
    const Z = { x: base.x + base.w / 2 - zoneW / 2, y: base.y + base.h / 2 - zoneH / 2, w: zoneW, h: zoneH };
    const scratch = vfxElementScratch;
    const scratchW = Math.ceil(Z.w * ratio);
    const scratchH = Math.ceil(Z.h * ratio);
    if (scratch.width < scratchW || scratch.height < scratchH) {
      scratch.width = Math.max(scratch.width, scratchW);
      scratch.height = Math.max(scratch.height, scratchH);
    }
    const cx = scratch.getContext("2d");
    cx.setTransform(1, 0, 0, 1, 0, 0);
    cx.clearRect(0, 0, scratchW, scratchH);
    cx.setTransform(ratio, 0, 0, ratio, -Z.x * ratio, -Z.y * ratio);
    // fire starts from the card's foot, inside the full part of the fade, not from the zone's edge
    const drawn = ["fire", "ash", "sand", "dark", "plant"].includes(emitter.kind) ? { x: Z.x, y: Z.y - Z.h * 0.12, w: Z.w, h: Z.h } : Z;
    drawVfxElement(cx, emitter.kind, t + emitter.seed, drawn, Math.min(1, strength), emitter.tint);
    fadeVfxElementEdges(cx, Z);
    main.drawImage(scratch, 0, 0, scratchW, scratchH, Z.x * ratio, Z.y * ratio, scratchW, scratchH);
  }
  vfxElementFrame = requestAnimationFrame(drawVfxElementFrame);
}

// ---------------------------------------------------------------- moments of a card on the board
// renderBattlefield calls this for every face-up card it draws: a reveal, an
// arrival or a move plays the card's element once, then it fades.
function playVfxBoardElement(el, item, previous, moment) {
  if (rulesVfxReducedMotion() || !lastBoardLayout || !item.faceUp || item.isTokenCard || !item.cardId) return;
  if (moment.flipped) {
    // with the impact of the reveal flip
    const delay = Math.min(1800, rulesVfxQueueRemaining()) + vfxMs(300);
    setRulesVfxTimeout(() => playVfxCardElement(item.cardId, item.id, { duration: 1500, grow: 2 }), delay);
    return;
  }
  if (moment.arriving) {
    const arrival = Number.parseFloat(el.style.getPropertyValue("--bf-arrive-delay")) || 0;
    setRulesVfxTimeout(() => playVfxCardElement(item.cardId, item.id, { duration: 1300, grow: 1.8 }), arrival + vfxMs(250));
    return;
  }
  const moved = previous && Math.hypot((Number.parseFloat(el.style.left) || 0) - previous.x, (Number.parseFloat(el.style.top) || 0) - previous.y) > 3;
  if (moved) {
    // a trail while it slides, a smaller burst where it lands
    playVfxCardElement(item.cardId, item.id, { envelope: "aura", duration: 700, grow: 1.5 });
  }
}
