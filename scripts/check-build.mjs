// Build output checks: required pages present, no scripts, no em dashes, hreflang present.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
const files = [];
const walk = (d) => { for (const f of readdirSync(d)) { const p = join(d, f); statSync(p).isDirectory() ? walk(p) : files.push(p); } };
walk("dist");
const need = ["dist/en.html", "dist/tr.html", "dist/en/method.html", "dist/tr/method.html", "dist/404.html", "dist/_redirects", "dist/_headers"];
const errs = [];
for (const n of need) if (!files.includes(n)) errs.push(`missing: ${n}`);
for (const f of files.filter((f) => f.endsWith(".html"))) {
  const h = readFileSync(f, "utf8");
  if (/<script\b/i.test(h)) errs.push(`contains script: ${f}`);
  if (h.includes("—")) errs.push(`contains em dash: ${f}`);
  if (!f.endsWith("404.html") && !h.includes('hreflang="x-default"')) errs.push(`missing hreflang: ${f}`);
}

// Design language TD-1 (silexi/portfolio docs/tasarim-dili.md): static checks.
const css = files.filter((f) => f.endsWith(".css")).map((f) => readFileSync(f, "utf8")).join("\n")
  + files.filter((f) => f.endsWith(".html")).map((f) => (readFileSync(f, "utf8").match(/<style[^>]*>[\s\S]*?<\/style>/g) || []).join("")).join("\n");
if (!/--td:\s*"TD-1"/.test(css)) errs.push("tokens.css (TD-1) is not in the build");
for (const m of css.matchAll(/font-size:\s*([\d.]+)(px|rem)/g)) {
  const px = m[2] === "rem" ? parseFloat(m[1]) * 16 : parseFloat(m[1]);
  if (px < 13 && !/\.diagram text\.small|\.diagram text/.test(css.slice(Math.max(0, m.index - 80), m.index))) errs.push(`font-size below 13px: ${m[0]}`);
}
for (const f of files.filter((f) => f.endsWith(".html"))) {
  const vp = (readFileSync(f, "utf8").match(/<meta name="viewport" content="([^"]*)"/) || [])[1];
  if (!vp || !vp.includes("width=device-width") || /user-scalable\s*=\s*no|maximum-scale/.test(vp)) errs.push(`viewport: ${f}`);
}
// Contrast of the role pairs in both themes, from the source tokens.
const tokens = readFileSync("src/tokens.css", "utf8");
const prim = Object.fromEntries([...tokens.matchAll(/--(stone-\d+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));
const roles = (block) => Object.fromEntries([...block.matchAll(/--(color-[a-z-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim().replace(/var\(--(stone-\d+)\)/, (_, k) => prim[k])]));
const [lightSrc, darkSrc] = tokens.split("@media (prefers-color-scheme: dark)");
const light = roles(lightSrc);
const dark = { ...light, ...roles(darkSrc.split("@media")[0]) };
const lum = (hex) => { const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4)); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
const tdNeed = [["color-text", "color-bg", 7], ["color-text-muted", "color-bg", 7], ["color-text", "color-surface", 7], ["color-text-muted", "color-surface", 7],
  ["color-accent", "color-bg", 4.5], ["color-danger", "color-bg", 4.5], ["color-success", "color-bg", 4.5], ["color-warning", "color-warning-bg", 4.5],
  ["color-accent-text", "color-accent", 4.5], ["color-focus", "color-bg", 3]];
for (const [theme, r] of [["light", light], ["dark", dark]]) {
  for (const [fg, bg, min] of tdNeed) {
    const c = ratio(r[fg], r[bg]);
    if (c < min) errs.push(`${theme} ${fg} on ${bg} is ${c.toFixed(2)}:1, needs ${min}:1`);
  }
}
if (errs.length) { console.error(errs.join("\n")); process.exit(1); }
console.log(`ok: ${files.length} files`);
