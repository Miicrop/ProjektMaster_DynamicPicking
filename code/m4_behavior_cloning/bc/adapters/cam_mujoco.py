"""Kamera der MuJoCo-Taktiksimulation (CameraPort, bc/sim_mujoco).

Rendert aus DERSELBEN Welt wie :class:`~bc.adapters.mujoco_robot.MujocoRobot`
-- das Bild zeigt den Arm dort, wo das Folgemodell ihn gerade hat, und das
Objekt dort, wo es liegt oder haengt. Vor jedem Bild wird die Welt bis zur
aktuellen Uhrzeit nachgerechnet.

Kameraplaetze wie in der Pipeline: ``wrist`` (am Werkzeug, 3,6 mm, Lochkamera mit Verzeichnung) und
``scene`` (fest, von oben); Lage und Objektiv aus den Referenzbildern
(``bc/sim_mujoco/kalibrierung.py``). Bildgroesse aus der Konfiguration
(Standard 320 x 240 = Schemagroesse, kein Skalieren im Recorder).

Zuordnung auf der Kommandozeile: ``--camera wrist=mujoco --camera
scene=mujoco``. Das Wrist-Licht ist schaltbar ueber das Geraet:
``wrist=mujoco:dunkel`` (aus) bzw. ``wrist=mujoco:hell`` (an, Standard).
``wrist=mujoco:c2`` (Versuch V4): Licht aus, dazu Verstaerkung und
Gauss-Rauschen wie die dunklen C2-Daten (``kameras.wrist.c2`` in
``bc/sim_mujoco/parameter.json``); Rauschen mit festem Seed je Kamera.

Zeitstempel: Uhr der Welt (SimClock oder Host-Uhr) nach dem Rendern -- wie
bei echten Kameras "nach dem Abgriff" (ports.Frame).
"""

from ..clock import RealClock
from ..ports import CameraError, CameraPort, Frame

#: Geraeteangaben (``wrist=mujoco:<licht>``)
LIGHT_ON = "hell"
LIGHT_OFF = "dunkel"
LIGHT_C2 = "c2"
LIGHT_MODES = (LIGHT_ON, LIGHT_OFF, LIGHT_C2)


class MujocoCamera(CameraPort):
    """Rendert ``cfg.name`` ("wrist"/"scene") aus der gemeinsamen Welt."""

    def __init__(self, cfg, clock=None, welt=None):
        super().__init__(cfg)
        if cfg.device not in (None, "") and str(cfg.device) not in LIGHT_MODES:
            raise CameraError("MuJoCo-Kamera: Geraet %r unbekannt (%s)"
                              % (cfg.device, ", ".join(LIGHT_MODES)))
        self.light = str(cfg.device) if cfg.device else LIGHT_ON
        self._clock = clock
        self._welt = welt
        self._c2 = None

    def open(self):
        from .. import sim_mujoco

        if self._welt is None:
            try:
                self._welt = sim_mujoco.welt(clock=self._clock or RealClock())
            except ValueError as exc:
                raise CameraError(str(exc))
        if self._clock is None:
            self._clock = self._welt.clock
        if self.cfg.name == "wrist":
            # Das Licht haengt physisch an der Wrist-Kamera -- ihr Platz entscheidet
            self._welt.wrist_licht = self.light == LIGHT_ON
            if self.light == LIGHT_C2:
                import numpy as np

                par = self._welt.par["kameras"]["wrist"]["c2"]
                self._c2 = (float(par["verstaerkung"]), float(par["rauschen_sigma"]),
                            np.random.default_rng(0))
        self._open = True
        return self

    def read(self):
        if not self._open:
            raise CameraError("Kamera '%s' ist nicht geoeffnet" % self.name)
        width = self.cfg.width or 320
        height = self.cfg.height or 240
        try:
            image = self._welt.render(self.cfg.name, width=width, height=height,
                                      t=self._clock.now())
        except KeyError as exc:
            raise CameraError("MuJoCo-Szene: %s" % exc)
        if self._c2 is not None:
            import numpy as np

            gain, sigma, rng = self._c2
            noisy = image.astype(np.float32) * gain + rng.normal(0.0, sigma, image.shape)
            image = np.clip(np.rint(noisy), 0, 255).astype(np.uint8)
        return Frame(image, self._clock.now(), self._next_index(), self.name)

    def settings(self):
        if self._welt is None:
            return {}
        out = {"renderer": "mujoco", "objektiv": self._welt.par["kameras"][self.cfg.name]["modell"]}
        if self.cfg.name == "wrist":
            out["wrist_licht"] = self.light
            if self._c2 is not None:
                out["c2_verstaerkung"], out["c2_rauschen_sigma"] = self._c2[0], self._c2[1]
        return out

    def close(self):
        self._open = False
