// Alle Szenen im Endzustand fotografieren (Kontaktbogen-Kontrolle vor dem Vortrag).
// Aufruf: node tools/shoot_all.mjs <ausgabeordner> [url]   – meldet Konsolenfehler und externe Requests.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';

const [out = 'shots_all', url = 'http://localhost:5180/'] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: +(process.env.SHOT_W ?? 1600), height: +(process.env.SHOT_H ?? 900) } });
const errors = [];
const external = [];
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`${m.type()}: ${m.text()}`); });
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
const origin = new URL(url).origin;
page.on('request', (r) => { const u = r.url(); if (!u.startsWith(origin) && !u.startsWith('data:') && !u.startsWith('blob:')) external.push(u); });
await page.goto(url);
await page.waitForFunction(() => document.body.classList.contains('ready'), null, { timeout: 30000 });
const scenes = await page.evaluate(() => window.__nav.scenes.map((s, i) => ({ i, id: s.id, steps: s.steps.length, placeholder: !!s.placeholder })));
for (const s of scenes) {
  await page.evaluate(([i, k]) => window.__nav.applyInstant(i, k), [s.i, s.steps]);
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(out, `${s.id}.png`) });
}
console.log(`${scenes.length} Szenen, davon Platzhalter: ${scenes.filter((s) => s.placeholder).map((s) => s.id).join(', ') || 'keine'}`);
console.log('errors:', errors.length ? '\n  ' + [...new Set(errors)].join('\n  ') : 'none');
console.log('external requests:', external.length ? '\n  ' + [...new Set(external)].join('\n  ') : 'none');
await browser.close();
