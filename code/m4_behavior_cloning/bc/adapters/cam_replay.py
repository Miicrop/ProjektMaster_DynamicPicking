"""Replay-Kamera: liefert die Bilder einer Aufnahme statt eines Live-Bilds.

Fuer den Test "Policy in der VM mit den Bildern einer echten Fahrt"
(bc/replay.py, apps/infer.py ``--replay``). Jeder ``read()`` liefert das
NAECHSTE aufgezeichnete Bild -- die Bilder laufen also im Regeltakt weiter
(ein ``latest()`` je Takt ueber capture.DirectCapture), nicht nach der Uhr.
Nach dem letzten Bild bleibt das letzte stehen.

Der Zeitstempel ist die aktuelle Uhrzeit: das Bild ist "frisch" im Sinn
von safety.FrameAgeGuard, es wird ja gerade eingespielt.

``cfg.device``: (Aufnahme-Ordner, Episodenindex).
"""

import numpy as np

from ..clock import RealClock
from ..ports import CameraError, CameraPort, Frame

BACKEND = "replay"


class ReplayCamera(CameraPort):
    def __init__(self, cfg, clock=None):
        super().__init__(cfg)
        self._clock = clock if clock is not None else RealClock()
        self._images = None
        self.root, self.episode = cfg.device

    def open(self):
        self.select(self.episode)
        self._open = True
        return self

    def select(self, episode):
        """Andere Episode laden und von vorn beginnen."""
        from .. import replay

        self.episode = int(episode)
        self._images = replay.load_images(self.root, self.episode, self.name)
        self.rewind()
        return self

    def rewind(self):
        self._index = 0

    @property
    def length(self):
        return 0 if self._images is None else len(self._images)

    @property
    def position(self):
        """Index des als naechstes gelieferten Bilds."""
        return self._index

    def read(self):
        if not self._open or self._images is None:
            raise CameraError("Replay-Kamera '%s' ist nicht geoeffnet" % self.name)
        index = self._next_index()
        image = self._images[min(index, len(self._images) - 1)]
        return Frame(np.ascontiguousarray(image), self._clock.now(), index, self.name)

    def settings(self):
        return {"replay": "%s ep %d" % (self.root, self.episode)}

    def close(self):
        self._open = False
        self._images = None
