// Screenshots einzelner Zustände zur Kontrolle (headless Edge), sammelt Konsolenfehler und externe Requests.
// Aufruf: node tools/shoot.mjs <ausgabeordner> [url] [zustand ...]   z. B.  1.3.2  2.2.3  play:1.4.2:0.9
//   zustand   = Szene.Schritt, sofort hergestellt
//   play:Z:s  = Zustand Z herstellen, dann einmal „weiter“ und nach s Sekunden fotografieren
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';

const [out = 'shots', url = 'http://localhost:5180/', ...states] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const W = +(process.env.SHOT_W ?? 1600);
const H = +(process.env.SHOT_H ?? 900);

const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
const errors = [];
const external = [];
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`${m.type()}: ${m.text()}`); });
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
const origin = new URL(url).origin;
page.on('request', (r) => { const u = r.url(); if (!u.startsWith(origin) && !u.startsWith('data:') && !u.startsWith('blob:')) external.push(u); });

await page.goto(url);
await page.waitForFunction(() => document.body.classList.contains('ready'), null, { timeout: 30000 });
await page.waitForTimeout(800);

for (const st of states.length ? states : ['1.1.1']) {
  let name = st.replace(/[:]/g, '_');
  if (st.startsWith('play:')) {
    const [, z, sec] = st.split(':');
    const [a, b, k] = z.split('.');
    await page.evaluate(([id, k]) => { const n = window.__nav; n.applyInstant(n.scenes.findIndex((s) => s.id === id), k); }, [`${a}.${b}`, +k]);
    await page.waitForTimeout(400);
    await page.evaluate(() => window.__nav.next());
    await page.waitForTimeout(+sec * 1000);
  } else {
    const [a, b, k] = st.split('.');
    await page.evaluate(([id, k]) => { const n = window.__nav; n.applyInstant(n.scenes.findIndex((s) => s.id === id), k); }, [`${a}.${b}`, +k]);
    await page.waitForTimeout(700);
  }
  await page.screenshot({ path: path.join(out, `${name}.png`) });
  console.log('shot', name);
}
console.log('errors:', errors.length ? '\n  ' + [...new Set(errors)].join('\n  ') : 'none');
console.log('external requests:', external.length ? '\n  ' + [...new Set(external)].join('\n  ') : 'none');
await browser.close();
