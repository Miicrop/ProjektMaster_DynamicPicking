// HUD im Stil eines Schriftfelds: Szene, Akt, Sprecher, Fortschritt; dazu Übersicht und Sprungeingabe.
import { ACTS } from '../storyboard.js';

export class Hud {
  constructor(root, storyboard) {
    this.storyboard = new Map(storyboard.map((e) => [e.id, e]));
    root.innerHTML = `
      <div class="hud" id="hud">
        <div class="hud-progress" id="hud-progress"></div>
        <div class="hud-block">
          <div class="hud-cell hud-title"><span class="hud-key">SZENE</span><span id="hud-title"></span></div>
          <div class="hud-cell hud-ff"><span class="hud-key">SPRICHT</span><span id="hud-ff"></span></div>
          <div class="hud-cell hud-id"><span class="hud-key">BLATT</span><span id="hud-id"></span></div>
          <div class="hud-cell hud-act"><span class="hud-key">AKT</span><span id="hud-act"></span></div>
        </div>
      </div>
      <div class="jump" id="jump"></div>
      <div class="toast" id="toast"></div>
      <div class="overview" id="overview" hidden></div>`;
    this.el = (id) => root.querySelector(`#${id}`);
    this.overviewEl = this.el('overview');
    this.toastTimer = null;
  }

  update(nav) {
    const sc = nav.scenes[nav.i];
    const e = this.storyboard.get(sc.id);
    this.el('hud-id').textContent = `${sc.id}`;
    this.el('hud-title').textContent = e?.title ?? '';
    this.el('hud-act').textContent = ACTS[sc.act] ?? '';
    this.el('hud-ff').textContent = e?.speaker ?? '–';
    // Fortschritt: ein Strich je Szene des aktuellen Akts, Schritte als Füllung
    const act = nav.scenes.filter((s) => s.act === sc.act && nav.visible(s));
    this.el('hud-progress').innerHTML = act
      .map((s) => {
        const cur = s.id === sc.id;
        const done = nav.scenes.indexOf(s) < nav.i;
        const fill = cur ? nav.k / s.steps.length : done ? 1 : 0;
        return `<span class="tick${cur ? ' cur' : ''}"><i style="width:${(fill * 100).toFixed(0)}%"></i></span>`;
      })
      .join('');
    if (!this.overviewEl.hidden) this.renderOverview(nav);
  }

  jump(buffer) {
    const j = this.el('jump');
    j.textContent = buffer ? `→ ${buffer}_` : '';
    j.classList.toggle('on', !!buffer);
  }

  toast(msg) {
    const t = this.el('toast');
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => t.classList.remove('on'), 1600);
  }

  toggleOverview(nav, show = this.overviewEl.hidden) {
    this.overviewEl.hidden = !show;
    if (show) this.renderOverview(nav);
  }

  renderOverview(nav) {
    const acts = [...new Set(nav.scenes.map((s) => s.act))];
    this.overviewEl.innerHTML = acts
      .map((a) => {
        const cards = nav.scenes
          .filter((s) => s.act === a)
          .map((s) => {
            const e = this.storyboard.get(s.id);
            const cls = ['card', s.id === nav.scenes[nav.i].id ? 'cur' : '', nav.visible(s) || s.appendix ? '' : 'hidden', s.placeholder ? 'ph' : 'built'].join(' ');
            return `<button class="${cls}" data-id="${s.id}">
              <span class="card-id">${s.id}</span>
              <span class="card-title">${e?.title ?? ''}</span>
              <span class="card-text">${e?.statement ?? ''}</span>
              <span class="card-meta">${s.placeholder ? 'Entwurf' : 'gebaut'}${e?.speaker ? ' · ' + e.speaker : ''}</span>
            </button>`;
          })
          .join('');
        return `<section><h2><span>${a === 'A' ? 'Anhang' : 'Akt ' + a}</span> ${ACTS[a]}</h2><div class="cards">${cards}</div></section>`;
      })
      .join('');
    this.overviewEl.querySelectorAll('.card').forEach((b) =>
      b.addEventListener('click', () => {
        this.toggleOverview(nav, false);
        nav.jumpToId(b.dataset.id);
      }),
    );
  }
}
