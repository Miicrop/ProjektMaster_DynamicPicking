"""Folgemodell des Arms: wie die Ist-Stellung dem servo_j-Strom nachlaeuft.

Je Gelenk (unabhaengig voneinander), zweiter Ordnung::

    r(t) = Sollwertstrom, linear zwischen den servo_j-Punkten, um verzug_s verzoegert
    a    = omega^2 * (r - q) - 2 * zeta * omega * v     (Feder-Daempfer)
    a begrenzt auf a_max, v auf v_max; v += a * dt, q += v * dt

Zweite Ordnung, weil die echte Achse 6 bei Richtungswechseln ueberschwingt
(bis ~0,05 rad am 19.11.) -- ein Nachlauf erster Ordnung kann das nicht.

Der Sollwertstrom ist bei der Aufnahme die lineare Interpolation der
15-Hz-Ziele (bc/servo.py: 4 Zwischenschritte je Takt bei 60 Hz); die
Beobachtung des Takts i wird direkt nach dem letzten Zwischenschritt gelesen
(bc/recorder.py). Genau so wird angepasst (:func:`simulate_batch`), damit
Simulation und Anpassung dieselbe Zeitachse haben. Die Kosten der Aufrufe an
der Anlage (servo_j ~5 ms, read_state ~4 ms) stecken damit im Verzug.

Angepasst an ``aux.joints_command`` gegen ``observation.state`` der echten
Aufnahmen vom 2026-11-19 (Override 0,5)::

    python -m bc.sim_mujoco.folgemodell --anpassen            # anzeigen
    python -m bc.sim_mujoco.folgemodell --anpassen --schreiben
    python -m bc.sim_mujoco.folgemodell --vergleich            # Abnahme

Grenze: Ein Gelenk sieht nur seinen eigenen Sollwert -- Kopplung zwischen
den Gelenken, Lastabhaengigkeit und Steuerkanal-Aussetzer fehlen.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from .. import config
from . import parameter as params_module

N_JOINTS = 6


class Folgemodell(object):
    """Zustand (q, v) eines Arms, fortgeschrieben bis zu einer Uhrzeit."""

    def __init__(self, p):
        self.verzug = np.asarray(p["verzug_s"], dtype=float)
        self.omega = np.asarray(p["omega_rads"], dtype=float)
        self.zeta = np.asarray(p["zeta"], dtype=float)
        self.v_max = np.asarray(p["v_max_rads"], dtype=float)
        self.a_max = np.asarray(p["a_max_rads2"], dtype=float)
        self.dt = float(p.get("dt_s", 1.0 / 480.0))
        self.q = np.zeros(N_JOINTS)
        self.v = np.zeros(N_JOINTS)
        self.t = None
        self._ht = []  # Zeitpunkte der Sollwerte
        self._hq = []  # Sollwerte

    def reset(self, q, t=None):
        """Arm steht bei ``q`` (v = 0), Sollwert = Ist."""
        self.q = np.asarray(q, dtype=float).copy()
        self.v = np.zeros_like(self.q)
        self.t = None if t is None else float(t)
        self._ht = [] if t is None else [float(t)]
        self._hq = [] if t is None else [self.q.copy()]

    def push(self, t, q):
        """servo_j-Sollwert, eingegangen zur Zeit ``t``."""
        t = float(t)
        if self.t is None:
            self.t = t
        if not self._ht:
            # Vorher stand der Arm: Sollwert = Ist bis jetzt
            self._ht.append(t - 1e-6)
            self._hq.append(self.q.copy())
        if t <= self._ht[-1]:
            t = self._ht[-1] + 1e-9
        self._ht.append(t)
        self._hq.append(np.asarray(q, dtype=float).copy())
        # Verlauf kurz halten: alles vor (jetzt - laengster Verzug - 1 s) faellt weg
        keep_from = t - float(np.max(self.verzug)) - 1.0
        while len(self._ht) > 2 and self._ht[1] < keep_from:
            self._ht.pop(0)
            self._hq.pop(0)

    def reference(self, t):
        """Sollwertstrom je Gelenk zur Zeit ``t - verzug`` (linear interpoliert)."""
        if not self._ht:
            return self.q.copy()
        ht = np.asarray(self._ht)
        hq = np.asarray(self._hq)
        out = np.empty(N_JOINTS)
        for j in range(N_JOINTS):
            out[j] = np.interp(t - self.verzug[j], ht, hq[:, j])
        return out

    def _step(self, h):
        r = self.reference(self.t + h)
        a = self.omega ** 2 * (r - self.q) - 2 * self.zeta * self.omega * self.v
        a = np.clip(a, -self.a_max, self.a_max)
        self.v = np.clip(self.v + a * h, -self.v_max, self.v_max)
        self.q = self.q + self.v * h
        self.t += h

    def advance(self, t):
        """Bis zur Zeit ``t`` fortschreiben (rueckwaerts: nichts)."""
        t = float(t)
        if self.t is None:
            self.t = t
            return
        while self.t < t - 1e-12:
            self._step(min(self.dt, t - self.t))

    @property
    def target(self):
        return None if not self._hq else self._hq[-1].copy()


# --------------------------------------------------------------------------
# Anpassung an Aufnahmen
# --------------------------------------------------------------------------

def load_recordings(root, every=1, limit=None):
    """Kommandos, Zustaende, Actions und Drehversatz je Episode (ohne Bilder)."""
    root = Path(root)
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))["episodes"]
    out = []
    for k, entry in enumerate(index):
        if k % every:
            continue
        folder = root / entry["dir"]
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        if meta.get("discarded"):
            continue
        with np.load(folder / "arrays.npz") as z:
            cmd = np.asarray(z["aux__joints_command"], dtype=float)
            state = np.asarray(z["observation__state"][:, :N_JOINTS], dtype=float)
            action = np.asarray(z["action"][:, :N_JOINTS], dtype=float)
        md = meta.get("metadata", {})
        out.append({
            "name": entry["dir"], "cmd": cmd, "state": state, "action": action,
            "drehung_grad": md.get("anflug_drehung_grad"),
            "rate_hz": float(md.get("rate_hz") or config.CONTROL_RATE_HZ),
        })
        if limit and len(out) >= limit:
            break
    return out


def simulate_batch(episodes, verzug, omega, zeta, v_max, a_max, dt=1.0 / 480.0, rate_hz=15.0):
    """Folgemodell fuer viele Episoden gleichzeitig.

    Sollwert = lineare Interpolation der 15-Hz-Kommandos (wie die 60-Hz-
    Zwischenschritte), Start in Ruhe an der gemessenen Stellung von Takt 0.
    Rueckgabe: Liste (N_e, 6) -- simulierte Stellung je Takt.
    Parameter je Gelenk (6,) -- oder (6,) fuer ein einzelnes Gelenk in Spalte j.
    """
    E = len(episodes)
    N = max(len(e["cmd"]) for e in episodes)
    cmd = np.zeros((E, N, N_JOINTS))
    for k, e in enumerate(episodes):
        n = len(e["cmd"])
        cmd[k, :n] = e["cmd"]
        cmd[k, n:] = e["cmd"][-1]
    q = np.array([e["state"][0] for e in episodes])
    v = np.zeros_like(q)
    verzug, omega, zeta = np.asarray(verzug, float), np.asarray(omega, float), np.asarray(zeta, float)
    v_max, a_max = np.asarray(v_max, float), np.asarray(a_max, float)
    out = np.zeros((E, N, N_JOINTS))
    out[:, 0] = q
    period = 1.0 / rate_hz
    sub = int(round(period / dt))
    h = period / sub
    cols = np.arange(N_JOINTS)
    t = 0.0
    for i in range(1, N):
        for _ in range(sub):
            t += h
            f = np.clip((t - verzug) * rate_hz, 0.0, N - 1 - 1e-9)
            i0 = np.floor(f).astype(int)
            fr = f - i0
            r = cmd[:, i0, cols] * (1 - fr) + cmd[:, np.minimum(i0 + 1, N - 1), cols] * fr
            a = np.clip(omega ** 2 * (r - q) - 2 * zeta * omega * v, -a_max, a_max)
            v = np.clip(v + a * h, -v_max, v_max)
            q = q + v * h
        out[:, i] = q
    return [out[k, :len(e["cmd"])] for k, e in enumerate(episodes)]


def fit(episodes, start, dt=1.0 / 480.0, verbose=True):
    """Kleinste Quadrate ueber Verzug, omega, zeta, a_max -- alle Gelenke zugleich.

    Die Gelenke sind im Modell entkoppelt; die Residuen werden je Gelenk
    gebildet und gemeinsam minimiert (Jacobi-Matrix duenn besetzt).
    """
    from scipy.optimize import least_squares
    from scipy.sparse import lil_matrix

    obs = [e["state"] for e in episodes]
    v_max = np.asarray(start["v_max_rads"], float)
    n_res = sum(len(o) - 1 for o in obs)

    npar = 4

    def unpack(x):
        x = x.reshape(N_JOINTS, npar)
        return (np.abs(x[:, 0]), np.clip(np.abs(x[:, 1]), 2.0, 0.6 / dt),
                np.clip(np.abs(x[:, 2]), 0.05, 3.0), np.abs(x[:, 3]) + 0.1)

    def residual(x):
        verzug, omega, zeta, a_max = unpack(x)
        sim = simulate_batch(episodes, verzug, omega, zeta, v_max, a_max, dt=dt)
        res = [(s[1:] - o[1:]) for s, o in zip(sim, obs)]
        return np.concatenate(res, axis=0).T.ravel()  # Gelenk fuer Gelenk

    sparsity = lil_matrix((N_JOINTS * n_res, N_JOINTS * npar), dtype=int)
    for j in range(N_JOINTS):
        sparsity[j * n_res:(j + 1) * n_res, npar * j:npar * (j + 1)] = 1
    x0 = np.column_stack([start["verzug_s"], start["omega_rads"], start["zeta"],
                          start["a_max_rads2"]]).ravel()
    res = least_squares(residual, x0, jac_sparsity=sparsity,
                        x_scale=np.tile([0.02, 5.0, 0.2, 3.0], N_JOINTS),
                        diff_step=2e-2, max_nfev=80, verbose=2 if verbose else 0)
    verzug, omega, zeta, a_max = unpack(res.x)
    rms = np.sqrt(np.mean(res.fun.reshape(N_JOINTS, n_res) ** 2, axis=1))
    return {"verzug_s": verzug, "omega_rads": omega, "zeta": zeta, "a_max_rads2": a_max, "rms_rad": rms}


def lag_stats(episodes, states):
    """Schleppfehler je Gelenk: |cmd - state| und |action - state|, gepoolt und
    als Episodenmaximum, getrennt nach Drehversatz ja/nein."""
    cs = np.concatenate([np.abs(e["cmd"] - s) for e, s in zip(episodes, states)])
    acs = np.concatenate([np.abs(e["action"] - s) for e, s in zip(episodes, states)])
    ep_max = np.array([np.max(np.abs(e["cmd"] - s), axis=0) for e, s in zip(episodes, states)])
    ep_amax = np.array([np.max(np.abs(e["action"] - s), axis=0) for e, s in zip(episodes, states)])
    rot = np.array([e["drehung_grad"] is not None for e in episodes])
    return {
        "cmd_p50": np.percentile(cs, 50, axis=0), "cmd_p90": np.percentile(cs, 90, axis=0),
        "cmd_p99": np.percentile(cs, 99, axis=0), "cmd_max": np.max(cs, axis=0),
        "act_p50": np.percentile(acs, 50, axis=0), "act_p90": np.percentile(acs, 90, axis=0),
        "ep_max_rot_p50": np.percentile(ep_max[rot], 50, axis=0) if rot.any() else None,
        "ep_max_rot_p90": np.percentile(ep_max[rot], 90, axis=0) if rot.any() else None,
        "ep_amax_q6_rot_p50": float(np.percentile(ep_amax[rot, 5], 50)) if rot.any() else None,
        "ep_amax_q6_rot_p90": float(np.percentile(ep_amax[rot, 5], 90)) if rot.any() else None,
        "ep_amax_q6_ohne_p50": float(np.percentile(ep_amax[~rot, 5], 50)) if (~rot).any() else None,
        "ep_max": ep_max, "ep_amax": ep_amax, "rot": rot, "pooled": cs,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Folgemodell anpassen / pruefen")
    parser.add_argument("--daten", default="data/2026-11-19")
    parser.add_argument("--anpassen", action="store_true")
    parser.add_argument("--schreiben", action="store_true")
    parser.add_argument("--vergleich", action="store_true",
                        help="Schleppfehler real gegen Modell (alle Episoden), Bild nach --bild")
    parser.add_argument("--jede", type=int, default=4, help="fuer die Anpassung jede n-te Episode")
    parser.add_argument("--bild", default="Dokumentation/Bilder/MuJoCo/folgemodell_schleppfehler.png")
    args = parser.parse_args(argv)
    par = params_module.load()
    fm = par["folgemodell"]
    np.set_printoptions(precision=4, suppress=True)
    if args.anpassen:
        train = load_recordings(args.daten, every=args.jede)
        print("Anpassung an %d Episoden aus %s" % (len(train), args.daten))
        result = fit(train, fm, dt=fm.get("dt_s", 1 / 480.0))
        for k in ("verzug_s", "omega_rads", "zeta", "a_max_rads2", "rms_rad"):
            print("%-12s %s" % (k, np.round(result[k], 4)))
        if args.schreiben:
            fm.update({k: [round(float(v), 5) for v in result[k]]
                       for k in ("verzug_s", "omega_rads", "zeta", "a_max_rads2")})
            fm.pop("tau_s", None)
            fm["rest_rms_rad"] = [round(float(v), 5) for v in result["rms_rad"]]
            fm["_quelle"] = ("angepasst (folgemodell.py --anpassen) an jede %d. Episode von %s: "
                             "aux.joints_command gegen observation.state, Override 0,5"
                             % (args.jede, args.daten))
            params_module.save(par)
            print("-> %s" % params_module.PATH)
            fm = params_module.load()["folgemodell"]
    if args.vergleich:
        eps = load_recordings(args.daten)
        sim = simulate_batch(eps, fm["verzug_s"], fm["omega_rads"], fm["zeta"], fm["v_max_rads"],
                             fm["a_max_rads2"],
                             dt=fm.get("dt_s", 1 / 480.0))
        real = lag_stats(eps, [e["state"] for e in eps])
        model = lag_stats(eps, sim)
        print("Schleppfehler |cmd - state| je Gelenk (rad), %d Episoden" % len(eps))
        for k in ("cmd_p50", "cmd_p90", "cmd_p99", "cmd_max", "act_p50", "act_p90",
                  "ep_max_rot_p50", "ep_max_rot_p90"):
            print("  %-15s real %s" % (k, np.round(real[k], 3)))
            print("  %-15s sim  %s" % ("", np.round(model[k], 3)))
        for k in ("ep_amax_q6_rot_p50", "ep_amax_q6_rot_p90", "ep_amax_q6_ohne_p50"):
            print("  %-22s real %.3f  sim %.3f" % (k, real[k], model[k]))
        dev = np.concatenate([s - e["state"] for s, e in zip(sim, eps)])
        print("Abweichung Modell - real je Gelenk: rms %s, p99 %s"
              % (np.round(np.sqrt(np.mean(dev ** 2, axis=0)), 4),
                 np.round(np.percentile(np.abs(dev), 99, axis=0), 4)))
        if args.bild:
            plot(real, model, args.bild, len(eps))
            print("-> %s" % args.bild)


def plot(real, model, path, n):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 6, figsize=(16, 5.6))
    bins = np.linspace(0, 0.3, 61)
    for j in range(N_JOINTS):
        ax = axes[0, j]
        ax.hist(real["pooled"][:, j], bins=bins, histtype="step", color="#1f77b4", label="real", density=True)
        ax.hist(model["pooled"][:, j], bins=bins, histtype="step", color="#d62728", label="Modell", density=True)
        ax.set_yscale("log")
        ax.set_title("q%d: |cmd - state| je Takt" % (j + 1), fontsize=9)
        ax.set_xlabel("rad", fontsize=8)
        ax = axes[1, j]
        b2 = np.linspace(0, 0.6 if j == 5 else 0.3, 31)
        ax.hist(real["ep_amax"][:, j], bins=b2, histtype="step", color="#1f77b4", label="real")
        ax.hist(model["ep_amax"][:, j], bins=b2, histtype="step", color="#d62728", label="Modell")
        ax.set_title("q%d: max |action - state| je Ep." % (j + 1), fontsize=9)
        ax.set_xlabel("rad", fontsize=8)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Folgemodell gegen Aufnahmen 2026-11-19 (%d Episoden, gleiche Kommandos)" % n)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
