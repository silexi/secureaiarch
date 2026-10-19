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
if (errs.length) { console.error(errs.join("\n")); process.exit(1); }
console.log(`ok: ${files.length} files`);
