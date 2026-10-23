// Browser check for design language TD-1 (silexi/portfolio docs/tasarim-dili.md, 3.6).
// Serves dist/ and opens every page at 320, 360, 390 (touch) and 768, 1280 (mouse) CSS px.
// Usage: npm run build && CHROMIUM_PATH=/path/to/chrome node scripts/check-mobile.mjs
import { createServer } from "node:http";
import { readFileSync, existsSync, statSync, readdirSync } from "node:fs";
import { join, extname } from "node:path";
import { chromium } from "playwright-core";

const root = "dist";
const types = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".svg": "image/svg+xml", ".txt": "text/plain" };
const server = createServer((req, res) => {
  let p = join(root, decodeURIComponent(req.url.split("?")[0]));
  if (existsSync(p) && statSync(p).isDirectory()) p = existsSync(join(p, "index.html")) ? join(p, "index.html") : p.replace(/\/$/, "") + ".html";
  else if (!existsSync(p) && existsSync(p + ".html")) p += ".html";
  if (!existsSync(p)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "content-type": types[extname(p)] || "application/octet-stream" });
  res.end(readFileSync(p));
}).listen(0, "127.0.0.1");
await new Promise((r) => server.once("listening", r));
const base = `http://127.0.0.1:${server.address().port}`;

const walk = (d) => readdirSync(d).flatMap((n) => (statSync(join(d, n)).isDirectory() ? walk(join(d, n)) : [join(d, n)]));
const pages = walk(root).filter((f) => f.endsWith(".html") && !f.endsWith("404.html")).map((f) => "/" + f.slice(root.length + 1).replace(/\.html$/, ""));

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const failures = [];
for (const [width, touch] of [[320, true], [360, true], [390, true], [768, false], [1280, false]]) {
  const ctx = await browser.newContext({ viewport: { width, height: 800 }, isMobile: touch, hasTouch: touch });
  for (const path of pages) {
    const page = await ctx.newPage();
    await page.goto(base + path, { waitUntil: "load" });
    const problems = await page.evaluate((touch) => {
      const out = [];
      const W = innerWidth;
      const scrolls = (el) => { for (let a = el.parentElement; a; a = a.parentElement) if (["auto", "scroll"].includes(getComputedStyle(a).overflowX)) return true; return false; };
      if (document.documentElement.scrollWidth > W) out.push(`page scrolls sideways (${document.documentElement.scrollWidth}px > ${W}px)`);
      for (const el of document.body.querySelectorAll("*")) {
        const r = el.getBoundingClientRect();
        if (r.width && r.right > W + 1 && !scrolls(el)) { out.push(`wider than the screen: <${el.tagName.toLowerCase()}>`); break; }
      }
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const n = walker.currentNode; if (!n.textContent.trim()) continue;
        const el = n.parentElement; const st = getComputedStyle(el);
        if (st.display === "none" || st.visibility === "hidden" || !el.getClientRects().length) continue;
        let px = parseFloat(st.fontSize);
        const svg = el.closest("svg");
        if (svg && svg.viewBox.baseVal && svg.viewBox.baseVal.width) px *= svg.getBoundingClientRect().width / svg.viewBox.baseVal.width;
        // TD-1: visible text at least 13 px; diagram (SVG) labels at least 11 px as rendered (3.5).
        const min = svg ? 11 : 13;
        if (px < min - 0.01) { out.push(`text below ${min}px (${px.toFixed(1)}px): "${n.textContent.trim().slice(0, 30)}"`); break; }
      }
      for (const el of document.querySelectorAll("a[href],button,input,select,textarea,summary")) {
        const r = el.getBoundingClientRect(); if (!r.width) continue;
        const inline = getComputedStyle(el).display === "inline" && el.closest("p,li,td,dd");
        if (inline) continue;
        if (r.width < 24 || r.height < 24) out.push(`target below 24px (${Math.round(r.width)}x${Math.round(r.height)}): "${el.textContent.trim().slice(0, 20)}"`);
        else if (touch && el.matches(".target,button,input,select,textarea") && r.height < 44) out.push(`touch target below 44px (${Math.round(r.height)}px): "${el.textContent.trim().slice(0, 20)}"`);
      }
      return out;
    }, touch);
    for (const p of problems) failures.push(`${width}px ${path}: ${p}`);
    await page.close();
  }
  await ctx.close();
}
await browser.close();
server.close();
if (failures.length) { console.error(failures.join("\n")); process.exit(1); }
console.log(`ok: ${pages.length} pages at 320, 360, 390, 768, 1280 px`);
