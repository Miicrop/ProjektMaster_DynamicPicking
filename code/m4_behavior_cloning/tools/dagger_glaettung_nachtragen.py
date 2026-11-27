"""Glaettung und DDIM-Schritte in aeltere DAgger-Episoden nachtragen.

Seit 2026-11-26 schreibt apps/infer.py ``glaettung`` und ``inference_steps``
in die Metadaten jeder DAgger-Episode. Aeltere Episoden (z. B.
data/2026-11-23_dagger) haben sie nicht. Dieses Werkzeug ordnet jede Episode
ueber die gesendeten Ziele (``aux.joints_command`` gegen ``ziel`` bzw.
``action`` der Fahrtprotokolle ``checkpoints/*/policy/rollouts/*/rollout_*.npz``)
genau einer Policy-Fahrt zu und traegt nach:

  metadata.glaettung            alpha der Fahrt (summary.json, sonst aus dem Log
                                geschaetzt; Fahrten ohne "ziel" im Log stammen von
                                vor dem Tiefpass -> 1.0)
  metadata.inference_steps      DDIM-Schritte der Fahrt (summary.json, sonst aus
                                bc_policy.json, sonst 10)
  metadata.glaettung_nachtrag   Herkunft: Fahrt, Rollout, Abweichung, Datum

Vorhandene Werte werden nicht ueberschrieben. Ohne ``--schreiben`` nur Anzeige.

    python tools/dagger_glaettung_nachtragen.py data/2026-11-23_dagger
    python tools/dagger_glaettung_nachtragen.py data/2026-11-23_dagger --schreiben
"""

import argparse
import glob
import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np

#: groesste Abweichung (rad) der gesendeten Ziele, bis zu der eine Zuordnung gilt
MATCH_TOL_RAD = 0.01


def _alpha(r):
    if 'ziel' not in r.files:
        return 1.0, 'ohne Tiefpass (Log vor 2026-11-23 nachmittags)'
    z, a = r['ziel'], r['action'][:, :6]
    x = (a[1:] - z[:-1]).ravel()
    y = (z[1:] - z[:-1]).ravel()
    est = float(x @ y / (x @ x)) if x @ x > 0 else 1.0
    return round(est, 2), 'aus dem Log geschaetzt'


def load_rollouts(root):
    out = []
    for f in sorted(glob.glob(str(Path(root) / 'checkpoints/*/policy/rollouts/*/rollout_*.npz'))):
        r = np.load(f)
        run = Path(f).parent
        summary = run / 'summary.json'
        try:
            args = json.loads(summary.read_text(encoding='utf-8')).get('args') or {}
        except (OSError, ValueError):
            args = {}
        alpha, quelle = _alpha(r)
        if args.get('glaettung') is not None:
            alpha, quelle = float(args['glaettung']), 'summary.json'
        steps = args.get('inference_steps')
        if steps is None:
            info = run.parent.parent / 'bc_policy.json'
            try:
                steps = json.loads(info.read_text(encoding='utf-8')).get('policy', {}).get('inference_steps')
            except (OSError, ValueError):
                steps = None
        target = r['ziel'] if 'ziel' in r.files else r['action'][:, :6]
        out.append(dict(path=f, run=run.name, target=np.asarray(target, float), alpha=alpha,
                        quelle=quelle, steps=int(steps or 10)))
    return out


def match(cmd, rollouts):
    best = None
    for ro in rollouts:
        n = min(len(ro['target']), len(cmd), 25)
        if n <= 6:
            continue
        err = float(np.abs(ro['target'][5:n] - cmd[5:n]).max())
        if best is None or err < best[0]:
            best = (err, ro)
    return best


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('data', help='DAgger-Ordner mit index.json')
    parser.add_argument('--root', default='.', help='Ordner m4_behavior_cloning (Default: hier)')
    parser.add_argument('--schreiben', action='store_true', help='meta.json wirklich aendern')
    args = parser.parse_args(argv)

    rollouts = load_rollouts(args.root)
    if not rollouts:
        raise SystemExit('keine Fahrtprotokolle unter %s/checkpoints gefunden' % args.root)
    changed = skipped = failed = 0
    for ep in sorted(Path(args.data).glob('ep_*')):
        meta_path = ep / 'meta.json'
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        md = meta.setdefault('metadata', {})
        cmd = np.load(ep / 'arrays.npz')['aux__joints_command']
        best = match(cmd, rollouts)
        if best is None or best[0] > MATCH_TOL_RAD:
            print('%s: keine Fahrt gefunden (beste Abweichung %s)' % (ep.name, best and '%.3g rad' % best[0]))
            failed += 1
            continue
        err, ro = best
        print('%s: %s %s, Glaettung %.2f (%s), DDIM %d, Abweichung %.1e rad'
              % (ep.name, ro['run'], Path(ro['path']).name, ro['alpha'], ro['quelle'], ro['steps'], err))
        if 'glaettung' in md and 'inference_steps' in md:
            skipped += 1
            continue
        md.setdefault('glaettung', ro['alpha'])
        md.setdefault('inference_steps', ro['steps'])
        md['glaettung_nachtrag'] = {
            'datum': date.today().isoformat(),
            'fahrt': os.path.relpath(ro['path'], args.root).replace('\\', '/'),
            'quelle': ro['quelle'],
            'abweichung_rad': err,
        }
        if args.schreiben:
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
        changed += 1
    print('\n%s: %d nachgetragen, %d hatten es schon, %d ohne Zuordnung%s'
          % (args.data, changed, skipped, failed, '' if args.schreiben else ' (nur Anzeige, --schreiben fehlt)'))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
