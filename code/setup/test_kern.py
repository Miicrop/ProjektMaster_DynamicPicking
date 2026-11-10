"""Tests fuer kern.py -- nur Standardbibliothek, installieren nichts.

    python setup\\test_kern.py        (oder: python -m pytest setup)
"""

import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import kern  # noqa: E402
import komponenten as K  # noqa: E402


class TestVersionen(unittest.TestCase):
    def test_tupel(self):
        self.assertEqual(kern.version_tupel("2.11.0+cu128"), (2, 11, 0))
        self.assertEqual(kern.version_tupel("4.13.0.92"), (4, 13, 0, 92))
        self.assertEqual(kern.version_tupel("2026.3.post1"), (2026, 3))

    def test_erfuellt(self):
        self.assertTrue(kern.erfuellt("2.11.0+cu128", "==2.11.0"))
        self.assertFalse(kern.erfuellt("2.11.0", "==2.11.0+cu128"))
        self.assertTrue(kern.erfuellt("2.2.6", ">=2.0,<2.3"))
        self.assertFalse(kern.erfuellt("2.3.0", ">=2.0,<2.3"))
        self.assertTrue(kern.erfuellt("6.8.1", ">=6.6,<7"))
        self.assertFalse(kern.erfuellt("7.0", ">=6.6,<7"))
        self.assertTrue(kern.erfuellt("1.0", ""))

    def test_zerlege(self):
        self.assertEqual(kern.zerlege("PySide6>=6.6,<7"), ("pyside6", ">=6.6,<7"))
        self.assertEqual(kern.zerlege("pywin32>=306; sys_platform == 'win32'"), ("pywin32", ">=306"))
        self.assertEqual(kern.zerlege("opencv_python==4.13"), ("opencv-python", "==4.13"))

    def test_quote_schuetzt_umleitung(self):
        self.assertEqual(kern._quote("numpy>=2.0,<2.3"), '"numpy>=2.0,<2.3"')
        self.assertEqual(kern._quote("install"), "install")


class TestKatalog(unittest.TestCase):
    def test_ids_eindeutig_und_vollstaendig(self):
        ids = [k["id"] for k in K.KOMPONENTEN]
        self.assertEqual(len(ids), len(set(ids)))
        gruppen = {g for g, _ in K.GRUPPEN}
        for k in K.KOMPONENTEN:
            self.assertIn(k["gruppe"], gruppen, k["id"])
            self.assertIn(k["art"], ("pip", "aktion", "admin", "pruefung"), k["id"])
            if k["art"] == "pip":
                self.assertTrue(k["pakete"], k["id"])
            else:
                self.assertIn(k["id"], kern.PRUEFUNGEN, k["id"])

    def test_pins_passen_zur_lock_datei(self):
        lock = {}
        for z in kern.LOCK_DATEI.read_text(encoding="utf-8-sig").splitlines():
            if "==" in z:
                n, v = z.split("==", 1)
                lock[kern.normname(n)] = v.strip()
        for k in K.KOMPONENTEN:
            for anf in k.get("pakete", []):
                name, spez = kern.zerlege(anf)
                if name in lock:
                    self.assertTrue(kern.erfuellt(lock[name], spez),
                                    "%s: lock %s passt nicht zu %s" % (k["id"], lock[name], spez))


class MitTempZiel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.venv = Path(self.tmp.name) / "venv"
        self.ziel = kern.Ziel(self.venv, "gpu")
        self.cache = mock.patch.object(kern, "CACHE_DIR", Path(self.tmp.name) / "cache")
        self.cache.start()

    def tearDown(self):
        self.cache.stop()
        self.tmp.cleanup()

    def fake_venv(self):
        (self.venv / "Scripts").mkdir(parents=True)
        (self.venv / "Lib" / "site-packages").mkdir(parents=True)
        (self.venv / "pyvenv.cfg").write_text("home = x\n")
        (self.venv / "Scripts" / "python.exe").write_bytes(b"")

    def befunde(self, **status):
        b = {k["id"]: kern.Befund(kern.FEHLT) for k in K.KOMPONENTEN}
        for kid, st in status.items():
            b[kid] = kern.Befund(st)
        return b


class TestConstraints(MitTempZiel):
    def test_gpu_behaelt_cuda_pin(self):
        text = kern.constraints_datei(self.ziel).read_text(encoding="utf-8")
        self.assertIn("torch==2.11.0+cu128", text)
        self.assertFalse(text.startswith("\ufeff"))

    def test_cpu_ohne_cuda_pin(self):
        self.ziel.build = "cpu"
        text = kern.constraints_datei(self.ziel).read_text(encoding="utf-8")
        self.assertIn("torch==2.11.0\n", text)
        self.assertNotIn("+cu", text)


class TestPlan(MitTempZiel):
    def test_ohne_umgebung_nicht_moeglich(self):
        with self.assertRaises(kern.PlanFehler):
            kern.plane("installieren", ["torch"], self.ziel, self.befunde())

    @mock.patch.object(kern, "finde_python312", return_value=r"C:\Py312\python.exe")
    def test_reihenfolge_und_opencv_zuletzt(self, _m):
        ids = ["opencv", "torch", "venv", "lerobot", "gui", "neurapy"]
        s = kern.plane("installieren", ids, self.ziel, self.befunde())
        kids = [x.kid for x in s]
        self.assertEqual(kids[:2], ["venv", "venv"])
        self.assertEqual(kids[-1], "opencv")
        self.assertLess(kids.index("torch"), kids.index("lerobot"))
        torch = s[kids.index("torch")].cmd
        self.assertIn("-c", torch)
        self.assertIn(K.TORCH_INDEX["gpu"], torch)

    @mock.patch.object(kern, "finde_python312", return_value=r"C:\Py312\python.exe")
    def test_vorhandenes_wird_uebersprungen(self, _m):
        self.fake_venv()
        s = kern.plane("installieren", ["venv", "torch", "gui"], self.ziel,
                       self.befunde(venv=kern.OK, torch=kern.OK))
        self.assertEqual([x.kid for x in s], ["gui"])

    def test_reparieren_installiert_neu(self):
        self.fake_venv()
        s = kern.plane("reparieren", ["gui"], self.ziel, self.befunde(venv=kern.OK, gui=kern.OK))
        self.assertIn("--force-reinstall", s[0].cmd)

    def test_admin_erzeugt_nie_schritte(self):
        self.fake_venv()
        s = kern.plane("installieren", ["nvidia", "vcredist", "galaxy_sdk"], self.ziel,
                       self.befunde(venv=kern.OK))
        self.assertEqual(s, [])

    def test_bc_python_nur_ausserhalb_standardort(self):
        self.fake_venv()
        s = kern.plane("installieren", ["bc_python"], self.ziel, self.befunde(venv=kern.OK))
        self.assertEqual(s[0].cmd[:2], ["setx", "BC_PYTHON"])
        std = kern.Ziel(kern.STANDARD_VENV, "gpu")
        self.assertEqual(kern.plane("installieren", ["bc_python"], std, self.befunde(venv=kern.OK)), [])

    def test_offline_quelle(self):
        self.fake_venv()
        self.ziel.wheelhouse = r"D:\wheels"
        s = kern.plane("installieren", ["gui"], self.ziel, self.befunde(venv=kern.OK))
        self.assertIn("--no-index", s[0].cmd)
        self.assertNotIn("--extra-index-url", s[0].cmd)

    def test_ffmpeg_ohne_zip_erklaert(self):
        self.fake_venv()
        with self.assertRaises(kern.PlanFehler):
            kern.plane("installieren", ["ffmpeg"], self.ziel, self.befunde(venv=kern.OK))

    def test_deinstallieren_umgebung_ersetzt_einzelschritte(self):
        self.fake_venv()
        s = kern.plane("deinstallieren", ["gui", "torch", "venv"], self.ziel, self.befunde(venv=kern.OK))
        self.assertEqual([x.kid for x in s], ["venv"])

    def test_deinstallieren_torch_laesst_numpy(self):
        self.fake_venv()
        s = kern.plane("deinstallieren", ["torch"], self.ziel, self.befunde(venv=kern.OK))
        self.assertNotIn("numpy", s[0].cmd)
        self.assertIn("torch", s[0].cmd)


class TestPipPruefung(MitTempZiel):
    def pruefe(self, kid, pakete):
        self.fake_venv()
        return kern.pruefe(kid, self.ziel, {"pakete": pakete})

    def test_vollstaendig(self):
        b = self.pruefe("video", {"torchcodec": "0.11.1", "av": "15.1.0"})
        self.assertEqual(b.status, kern.OK)

    def test_teilweise(self):
        b = self.pruefe("video", {"av": "15.1.0"})
        self.assertEqual(b.status, kern.FEHLT)
        self.assertIn("torchcodec", b.detail)

    def test_falsche_version(self):
        b = self.pruefe("lerobot", {"lerobot": "0.5.0", "diffusers": "0.39.0", "datasets": "4.8.5"})
        self.assertEqual(b.status, kern.ABWEICHEND)

    def test_cpu_torch_bei_gpu_build(self):
        b = self.pruefe("torch", {"torch": "2.11.0", "torchvision": "0.26.0", "numpy": "2.2.6"})
        self.assertEqual(b.status, kern.ABWEICHEND)
        self.assertIn("CPU-Build", b.detail)


class TestAktionen(MitTempZiel):
    def test_ffmpeg_hin_und_zurueck(self):
        self.fake_venv()
        (self.venv / "Scripts" / "avcodec-61.dll").write_bytes(b"fremd")   # nicht von uns
        z = Path(self.tmp.name) / "ffmpeg.zip"
        with zipfile.ZipFile(str(z), "w") as f:
            f.writestr("ffmpeg-n8.1/bin/ffmpeg.exe", b"exe")
            f.writestr("ffmpeg-n8.1/bin/avformat-61.dll", b"dll")
            f.writestr("ffmpeg-n8.1/bin/avcodec-61.dll", b"neu")
            f.writestr("ffmpeg-n8.1/doc/readme.txt", b"x")
        log = []
        kern.ffmpeg_einspielen(z, self.ziel, log.append)
        sc = self.venv / "Scripts"
        self.assertTrue((sc / "ffmpeg.exe").is_file())
        self.assertTrue((sc / "avformat-61.dll").is_file())
        self.assertFalse((sc / "readme.txt").exists())
        self.assertEqual((sc / "avcodec-61.dll").read_bytes(), b"fremd")
        kern.ffmpeg_entfernen(self.ziel, log.append)
        self.assertFalse((sc / "ffmpeg.exe").exists())
        self.assertTrue((sc / "avcodec-61.dll").exists())       # fremde Datei bleibt
        self.assertTrue((sc / "python.exe").exists())

    def test_loeschen_nur_echte_venv(self):
        self.venv.mkdir()
        (self.venv / "wichtig.txt").write_text("x")
        with self.assertRaises(RuntimeError):
            kern.umgebung_loeschen(self.ziel, lambda t: None)
        self.assertTrue((self.venv / "wichtig.txt").exists())

    def test_loeschen_venv(self):
        self.fake_venv()
        kern.umgebung_loeschen(self.ziel, lambda t: None)
        self.assertFalse(self.venv.exists())

    def test_gxipy_pth(self):
        self.fake_venv()
        sdk = Path(self.tmp.name) / "sdk"
        (sdk / "gxipy").mkdir(parents=True)
        kern.gxipy_einbinden(sdk, self.ziel, lambda t: None)
        with mock.patch.object(kern, "galaxy_sdk_pfad", return_value=sdk):
            self.assertEqual(kern.pruefe("gxipy", self.ziel).status, kern.OK)


class TestLauf(MitTempZiel):
    def test_bricht_bei_fehler_ab_und_loggt(self):
        with mock.patch.object(kern, "LOG_DIR", Path(self.tmp.name) / "logs"):
            ausgabe = []
            lauf = kern.Lauf(ausgabe.append)
            s = [kern.Schritt("a", "gut", [sys.executable, "-c", "print('hallo')"]),
                 kern.Schritt("b", "schlecht", [sys.executable, "-c", "raise SystemExit(3)"]),
                 kern.Schritt("c", "nie", [sys.executable, "-c", "print('nie')"])]
            self.assertFalse(lauf(s))
            text = lauf.log_datei.read_text(encoding="utf-8")
            self.assertIn("hallo", text)
            self.assertIn("Rueckgabewert 3", text)
            self.assertNotIn("[3/3]", text)

    def test_ausgabe_ohne_unicode_stirbt_nicht(self):
        with mock.patch.object(kern, "LOG_DIR", Path(self.tmp.name) / "logs"):
            gesehen = []

            def cp1252(text):
                text.encode("cp1252")          # wirft bei tqdm-Balken wie die echte Konsole
                gesehen.append(text)

            lauf = kern.Lauf(cp1252)
            s = [kern.Schritt("a", "Balken", [sys.executable, "-c", "print('Map: \\u2588\\u2588 100%')"])]
            self.assertTrue(lauf(s))
            self.assertTrue(any("Map:" in g for g in gesehen))
            self.assertIn("█", lauf.log_datei.read_text(encoding="utf-8"))

    def test_tests_duerfen_scheitern(self):
        with mock.patch.object(kern, "LOG_DIR", Path(self.tmp.name) / "logs"):
            lauf = kern.Lauf(lambda t: None)
            s = [kern.Schritt("selbsttest", "Tests", [sys.executable, "-c", "raise SystemExit(1)"],
                              darf_scheitern=True)]
            self.assertFalse(lauf(s))
            self.assertEqual(lauf.ergebnisse["selbsttest"].status, kern.WARNUNG)


class TestCheckliste(MitTempZiel):
    def test_enthaelt_admin_punkte(self):
        b = self.befunde(nvidia=kern.ADMIN, vcredist=kern.OK, galaxy_sdk=kern.ADMIN)
        md = kern.checkliste(self.ziel, b)
        self.assertIn("| [ ] | NVIDIA", md)
        self.assertIn("| [x] | Microsoft Visual C++", md)
        self.assertIn("lerobot==0.6.1", md)


if __name__ == "__main__":
    unittest.main(verbosity=1)
