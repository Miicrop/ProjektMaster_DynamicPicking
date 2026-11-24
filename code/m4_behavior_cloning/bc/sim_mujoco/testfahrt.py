"""Geschlossene Sim-Testfahrt unter den Bedingungen der VM-Fahrten.

    python -m bc.sim_mujoco.testfahrt [--ohne-tisch] [--verzoegerung N] <apps/infer.py-Argumente ...>

Laeuft ``apps/infer.py`` (``infer.main()``) unveraendert, ersetzt aber zwei
Stellen, in denen die Sim von den VM-Fahrten der Anlagenmodelle abweicht:

``--verzoegerung N`` (Takte, VM: 2)
    Mit SimClock sagt ``infer.py`` synchron voraus: der Chunk aus der
    Beobachtung von Takt s gilt schon ab Takt s. In der VM/an der Anlage
    laeuft die Vorhersage asynchron (~77-90 ms bei 66,7 ms Takt); der Chunk
    trifft 2 Takte nach seiner Beobachtung ein (G2 vm_val39: 1715 von 1771
    Vorhersagen mit ``delay_steps`` = 2, meist 3 Chunks im Mittel statt 4).
    Das entscheidet ueber den Griff: G2 und die Sim-Modelle sagen das
    Schliessen als ``[0,0,0,0,1,1,1,1]`` voraus. Synchron mitteln die Indizes
    0/2/4/6 der Chunks zu 0,5 -- knapp unter config.GRIPPER_THRESHOLD, der
    Greifer schliesst nicht. Mit 2 Takten Verzug mitteln 2/4/6 zu 0,67.
    :class:`VerzoegerterEnsembler` gibt einen Chunk erst N Takte nach seiner
    Beobachtung frei (Takt 0 wartet wie an der Anlage auf die erste
    Vorhersage). Die Rechnung bleibt synchron und damit reproduzierbar.

``--ohne-tisch``
    Die VM-Fahrten (G, G2, Lernkurve) liefen mit ``GEOFENCE=alt``
    (Berichte/Versuchsreihe_Policy-Varianten/skripte/stufe2_vm.py):
    Tischebene, Sperrzonen und Huelle der Demonstrationen aus
    ``bc_policy.json`` werden NICHT geladen, nur der grobe Tischquader. Tiefe
    Ziele laufen weiter und zaehlen danach als "Tisch < 0 / < -10 mm", statt
    die Fahrt vorab abzubrechen ("kollision vorab: tool an Tischebene"). In
    der Sim folgt der Arm auch unter die Tischebene; ``vergleich.py`` zaehlt
    deshalb "Griff ueber Tisch" getrennt.
"""

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def ensembler_klasse():
    from ..policy import ChunkEnsembler, PredictionTooSlow

    class VerzoegerterEnsembler(ChunkEnsembler):
        """ChunkEnsembler (synchron), Chunks erst ``verzoegerung`` Takte nach
        ihrer Beobachtung nutzbar -- wie die asynchrone Vorhersage der Anlage."""

        verzoegerung = 2

        def reset_state(self):
            super().reset_state()
            self._wartend = []  # (Takt der Beobachtung, Chunk, Sekunden)

        def _freigeben(self, alle=False):
            step = self._step
            bleiben = []
            for s, chunk, sec in self._wartend:
                if alle or s + self.verzoegerung <= step:
                    self._add(s, chunk, sec)
                else:
                    bleiben.append((s, chunk, sec))
            self._wartend = bleiben

        def next_action(self, observation):
            if self.asynchronous:
                return super().next_action(observation)
            step = self._step
            self.policy.observe(observation)
            self._freigeben()
            self._chunks = [(s, c) for s, c in self._chunks if step < s + len(c)]
            due = self._last_request is None or step - self._last_request >= self.replan_steps
            if due:
                t0 = time.perf_counter()
                chunk = self.policy.predict_snapshot(self.policy.snapshot(observation))
                self._wartend.append((step, chunk, time.perf_counter() - t0))
                self._last_request = step
            if not self._covered(step):
                # kein eingetroffener Chunk deckt den Takt: auf die laufende
                # Vorhersage warten (an der Anlage nur in Takt 0)
                self._freigeben(alle=True)
            if not self._covered(step):
                raise PredictionTooSlow("Takt %d: keine gueltige Vorhersage" % step)
            self._chunks = [(s, c) for s, c in self._chunks if s <= step < s + len(c)]
            actions = np.array([c[step - s] for s, c in self._chunks])
            ages = np.array([step - s for s, _ in self._chunks], dtype=float)
            weights = np.exp(-self.decay * ages)
            action = (weights[:, None] * actions).sum(axis=0) / weights.sum()
            self.last_count = len(actions)
            self.last_spread = float(np.max(np.ptp(actions[:, :6], axis=0))) if len(actions) > 1 else 0.0
            self._step += 1
            return action

    return VerzoegerterEnsembler


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ohne_tisch = "--ohne-tisch" in argv
    if ohne_tisch:
        argv.remove("--ohne-tisch")
    verzoegerung = 0
    if "--verzoegerung" in argv:
        i = argv.index("--verzoegerung")
        verzoegerung = int(argv[i + 1])
        del argv[i:i + 2]

    sys.path.insert(0, str(ROOT / "apps"))
    import _bootstrap  # noqa: F401
    import infer

    if ohne_tisch:
        def _ohne_tisch(*_a, **_k):
            print("Kollisionsmodell: wie VM (GEOFENCE=alt) -- Tischebene/Sperrzonen/Huelle NICHT geladen")
            return None

        infer.add_recorded_workspace = _ohne_tisch
    if verzoegerung:
        klasse = ensembler_klasse()
        klasse.verzoegerung = verzoegerung
        infer.ChunkEnsembler = klasse
        print("Vorhersage: synchron gerechnet, Chunks %d Takte nach der Beobachtung nutzbar (wie VM)"
              % verzoegerung)
    sys.argv = ["infer.py"] + argv
    infer.main()


if __name__ == "__main__":
    main()
