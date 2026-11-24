import json, glob, os, sys
import numpy as np
sys.path.insert(0, '.')
from bc import geometry
def yaw360(q):
    R = geometry.quat_to_matrix(np.asarray(q, float)[3:]); return np.degrees(np.arctan2(R[1, 0], R[0, 0]))
def wrap(a): return (a + 180) % 360 - 180
rows = []
for m in ['G2_licht_langsam_nur_griff', 'G3_kappen030', 'G4_ausblenden030']:
    for p in sorted(glob.glob(f'checkpoints/{m}/policy/rollouts/2026-11-23_*/summary.json')):
        d = os.path.dirname(p); s = json.load(open(p))
        if not s['episodes']: rows.append((m[:2], os.path.basename(d)[11:16], 'keine Fahrt (0 Episoden)')); continue
        e = s['episodes'][0]; L = e['lage']; r = np.load(d + '/rollout_000.npz')
        tcp = np.vstack([r['tcp'], r['final_tcp'][None]]); pick = np.array(L['pick'])
        dz = (tcp[:, 2] - pick[2]) * 1e3; xy = np.linalg.norm(tcp[:, :2] - pick[:2], axis=1) * 1e3
        d3 = np.sqrt(dz**2 + xy**2); i = int(np.argmin(d3))
        yaw_u = wrap(np.array([yaw360(q) for q in tcp]) - yaw360(pick))
        # Spruenge: Soll-Gelenke Takt zu Takt und Soll gegen Ist
        jumps = np.abs(np.diff(r['action'][:, :6], axis=0)).max() if len(r['action']) > 1 else 0
        gap = np.abs(r['action'][:, :6] - r['joints']).max()
        vz = np.diff(tcp[-6:, 2]).mean() * 1e3 * 15  # mm/s bei 15 Hz
        gr = r['gripper_cmd'].max(); chunk_gr = r['pred_chunk'][:, :, 6].max() if len(r['pred_chunk']) else np.nan
        last_chunk_gr = r['pred_chunk'][-1, :, 6].max() if len(r['pred_chunk']) else np.nan
        pr = L.get('predicted') or {}
        ps = r['predict_s'][np.isfinite(r['predict_s'])] * 1e3
        rows.append(dict(m=m[:2], run=os.path.basename(d)[11:16], lage=f"{pick[0]*1e3:.0f}/{pick[1]*1e3:.0f}", pyaw=L['pick_yaw_deg'],
            steps=e['steps'], stop=e['stop_reason'][:60], dzmin=dz.min(), xy_i=xy[i], dz_i=dz[i], xy_end=xy[-1], dz_end=dz[-1],
            yaw_end=yaw_u[-1], yaw_folded=L['at_stop']['yaw_deg'], tab=L['table_min_m']*1e3, vz=vz, grip=gr, chunk_gr=chunk_gr, last_chunk=last_chunk_gr,
            pred_xy=(pr.get('xy_m') or np.nan)*1e3, pred_dz=(pr.get('dz_m') or np.nan)*1e3, jump=jumps, gap=gap,
            pms_med=np.median(ps), pms_p95=np.percentile(ps, 95), pms_max=ps.max(), ovr=e['pacer_overruns'], skip=e['predictions_skipped_busy'],
            clamp=e['limiter_clamped_steps'], exp=(e.get('experte') or {}).get('result', '')[:9], succ=e['success']))
for x in rows:
    if isinstance(x, tuple): print(*x); continue
    print(f"{x['m']} {x['run']} {x['lage']:>9} n{x['steps']:3} dzmin{x['dzmin']:6.1f} @xy{x['xy_i']:5.1f} | end xy{x['xy_end']:5.1f} dz{x['dz_end']:5.1f} yawU{x['yaw_end']:7.1f} (f{x['yaw_folded']:5.1f}) tab{x['tab']:5.1f} vz{x['vz']:6.1f} | grip{x['grip']:.0f} chunkG{x['chunk_gr']:.2f} lastG{x['last_chunk']:.2f} | pred xy{x['pred_xy']:5.1f} dz{x['pred_dz']:5.1f} | jmp{x['jump']:.3f} gap{x['gap']:.3f} | ms {x['pms_med']:.0f}/{x['pms_p95']:.0f}/{x['pms_max']:.0f} ovr{x['ovr']} clamp{x['clamp']} {x['exp']} succ{x['succ']} | {x['stop']}")
json.dump([x for x in rows if isinstance(x, dict)], open(os.environ.get('OUT', 'NUL'), 'w'), default=float, indent=0)
