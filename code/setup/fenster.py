"""Fenster des M4-Setup-Programms (tkinter, Standardbibliothek).

Zeigt jede Komponente mit Haekchen und Status, nach Gruppen sortiert.
Admin-Komponenten haben kein Haekchen, sie werden nur geprueft. Die Arbeit
macht kern.py in einem eigenen Thread; das Fenster zeigt das Log live.
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import kern
import komponenten as K

FARBEN = {
    kern.OK: "#2e7d32", kern.NICHT_NOETIG: "#6b6b6b", kern.FEHLT: "#6b6b6b",
    kern.ABWEICHEND: "#b26a00", kern.ADMIN: "#b26a00", kern.WARTET: "#6b6b6b",
    kern.OFFEN: "#6b6b6b", kern.WARNUNG: "#c62828",
}


class Tooltip(object):
    def __init__(self, widget, text):
        self.widget, self.text, self.fenster = widget, text, None
        widget.bind("<Enter>", self.zeige)
        widget.bind("<Leave>", self.weg)

    def zeige(self, _e=None):
        if not self.text or self.fenster:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        self.fenster = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        tk.Label(tw, text=self.text, justify="left", background="#ffffe0", relief="solid",
                 borderwidth=1, wraplength=480, padx=6, pady=4).pack()

    def weg(self, _e=None):
        if self.fenster:
            self.fenster.destroy()
            self.fenster = None


class SetupFenster(object):
    def __init__(self, wurzel, ziel):
        self.w = wurzel
        self.ziel = ziel
        self.befunde = {}
        self.test_ergebnisse = {}
        self.haken = {}          # kid -> BooleanVar
        self.status_labels = {}  # kid -> (Label status, Label detail)
        self.lauf = None
        self.q = queue.Queue()

        wurzel.title("M4 Setup - Behavior Cloning")
        f = wurzel.winfo_fpixels("1i") / 96.0          # Windows-Skalierung (DPI)
        b = min(int(1040 * f), wurzel.winfo_screenwidth() - 40)
        h = min(int(860 * f), wurzel.winfo_screenheight() - 140)
        wurzel.geometry("%dx%d+20+20" % (b, h))
        self._oben()
        self._liste()
        self._knoepfe()
        self._log()
        self.w.after(100, self._queue_leeren)
        self.neu_pruefen()

    # -- Aufbau -------------------------------------------------------------
    def _oben(self):
        f = ttk.Frame(self.w, padding=(10, 8))
        f.pack(fill="x")
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="Zielordner").grid(row=0, column=0, sticky="w")
        self.v_ziel = tk.StringVar(value=str(self.ziel.venv))
        ttk.Entry(f, textvariable=self.v_ziel).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(f, text="...", width=3, command=self._waehle_ziel).grid(row=0, column=2)
        ttk.Button(f, text="Standard", command=lambda: self._setze_ziel(str(kern.STANDARD_VENV))
                   ).grid(row=0, column=3, padx=(4, 0))

        ttk.Label(f, text="Basis-Python").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.v_basis = tk.StringVar(value=self.ziel.basis_python or "")
        e = ttk.Entry(f, textvariable=self.v_basis)
        e.grid(row=1, column=1, sticky="ew", padx=6, pady=(4, 0))
        Tooltip(e, "Leer = automatisch suchen (py -3.12, uebliche Orte). "
                   "Nur noetig, wenn Python 3.12 an einem ungewoehnlichen Ort liegt.")
        ttk.Button(f, text="...", width=3, command=self._waehle_basis).grid(row=1, column=2, pady=(4, 0))

        ttk.Label(f, text="Paketquelle").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.v_wheel = tk.StringVar(value=self.ziel.wheelhouse or "")
        e = ttk.Entry(f, textvariable=self.v_wheel)
        e.grid(row=2, column=1, sticky="ew", padx=6, pady=(4, 0))
        Tooltip(e, "Leer = Internet (pypi.org, download.pytorch.org). "
                   "Ordner = offline aus vorher heruntergeladenen Paketen "
                   "(m4_setup.py --wheelhouse-befehle).")
        ttk.Button(f, text="...", width=3, command=self._waehle_wheel).grid(row=2, column=2, pady=(4, 0))

        ttk.Label(f, text="FFmpeg-ZIP").grid(row=3, column=0, sticky="w", pady=(4, 0))
        self.v_ffmpeg = tk.StringVar(value=self.ziel.ffmpeg_zip or "")
        ttk.Entry(f, textvariable=self.v_ffmpeg).grid(row=3, column=1, sticky="ew", padx=6, pady=(4, 0))
        ttk.Button(f, text="...", width=3, command=self._waehle_ffmpeg).grid(row=3, column=2, pady=(4, 0))

        b = ttk.Frame(f)
        b.grid(row=0, column=4, rowspan=4, sticky="ne", padx=(16, 0))
        ttk.Label(b, text="PyTorch-Build").pack(anchor="w")
        self.v_build = tk.StringVar(value=self.ziel.build)
        ttk.Radiobutton(b, text="GPU (CUDA 12.8)", value="gpu", variable=self.v_build,
                        command=self.neu_pruefen).pack(anchor="w")
        ttk.Radiobutton(b, text="CPU (ohne Training)", value="cpu", variable=self.v_build,
                        command=self.neu_pruefen).pack(anchor="w")

    def _liste(self):
        rahmen = ttk.Frame(self.w, padding=(10, 0))
        rahmen.pack(fill="both", expand=True)
        canvas = tk.Canvas(rahmen, highlightthickness=0, background=self._bg())
        sb = ttk.Scrollbar(rahmen, orient="vertical", command=canvas.yview)
        innen = ttk.Frame(canvas)
        innen.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        fid = canvas.create_window((0, 0), window=innen, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(fid, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        innen.columnconfigure(1, weight=1)
        innen.columnconfigure(3, weight=1)

        zeile = 0
        for gid, gtitel in K.GRUPPEN:
            ttk.Label(innen, text=gtitel, font=("Segoe UI", 10, "bold")).grid(
                row=zeile, column=0, columnspan=5, sticky="w", pady=(10, 2))
            zeile += 1
            for k in K.KOMPONENTEN:
                if k["gruppe"] != gid:
                    continue
                kid = k["id"]
                if k["art"] == "admin" or kid in K.NUR_PRUEFEN:
                    sym = "Admin" if k["art"] == "admin" else "Pruefen"
                    ttk.Label(innen, text=sym, foreground="#6b6b6b", width=8).grid(row=zeile, column=0, sticky="w")
                else:
                    v = tk.BooleanVar(value=False)
                    self.haken[kid] = v
                    ttk.Checkbutton(innen, variable=v).grid(row=zeile, column=0, sticky="w")
                titel = ttk.Label(innen, text=k["titel"])
                titel.grid(row=zeile, column=1, sticky="w")
                tip = k.get("info", "")
                if k.get("anleitung"):
                    tip += ("\n\nVon Hand: " if tip else "Von Hand: ") + k["anleitung"]
                Tooltip(titel, tip)
                ttk.Label(innen, text=k.get("groesse", ""), foreground="#6b6b6b", width=18).grid(
                    row=zeile, column=2, sticky="e", padx=6)
                st = tk.Label(innen, text="...", width=14, anchor="w", background=self._bg())
                st.grid(row=zeile, column=3, sticky="w")
                det = ttk.Label(innen, text="", foreground="#6b6b6b")
                det.grid(row=zeile + 1, column=1, columnspan=4, sticky="w", padx=(0, 0))
                self.status_labels[kid] = (st, det)
                zeile += 2

    def _knoepfe(self):
        f = ttk.Frame(self.w, padding=(10, 6, 10, 2))
        f.pack(fill="x")
        links = ttk.Frame(f)
        links.pack(side="left")
        f2 = ttk.Frame(self.w, padding=(10, 2, 10, 6))
        f2.pack(fill="x")
        ttk.Button(links, text="Neu pruefen", command=self.neu_pruefen).pack(side="left")
        ttk.Button(links, text="Fehlende waehlen", command=self.fehlende_waehlen).pack(side="left", padx=4)
        ttk.Button(links, text="Keine", command=lambda: [v.set(False) for v in self.haken.values()]
                   ).pack(side="left")
        ttk.Button(links, text="Befehle anzeigen", command=self.befehle_anzeigen).pack(side="left", padx=(12, 4))
        ttk.Button(links, text="Checkliste Betreuer", command=self.checkliste).pack(side="left")

        rechts = ttk.Frame(f2)
        rechts.pack(side="right")
        self.b_abbruch = ttk.Button(rechts, text="Abbrechen", command=self.abbrechen, state="disabled")
        self.b_abbruch.pack(side="right")
        self.b_aktion = []
        for text, aktion in (("Auswahl installieren", "installieren"),
                             ("Reparieren", "reparieren"),
                             ("Deinstallieren", "deinstallieren")):
            b = ttk.Button(rechts, text=text, command=lambda a=aktion: self.starte(a))
            b.pack(side="right", padx=4)
            self.b_aktion.append(b)
        b = ttk.Button(rechts, text="Umgebung loeschen", command=self.umgebung_loeschen)
        b.pack(side="right", padx=(0, 12))
        self.b_aktion.append(b)

    def _log(self):
        f = ttk.Frame(self.w, padding=(10, 0, 10, 10))
        f.pack(fill="both")
        self.log = ScrolledText(f, height=8, font=("Consolas", 9), state="disabled", wrap="none")
        self.log.pack(fill="both", expand=True)

    def _bg(self):
        return ttk.Style().lookup("TFrame", "background") or "SystemButtonFace"

    # -- Einstellungen --------------------------------------------------------
    def _uebernehme(self):
        self.ziel.venv = kern.Path(self.v_ziel.get().strip() or str(kern.STANDARD_VENV))
        self.ziel.build = self.v_build.get()
        self.ziel.basis_python = self.v_basis.get().strip() or None
        self.ziel.wheelhouse = self.v_wheel.get().strip() or None
        self.ziel.ffmpeg_zip = self.v_ffmpeg.get().strip() or None
        kern.speichere_einstellungen(self.ziel)

    def _setze_ziel(self, pfad):
        self.v_ziel.set(pfad)
        self.neu_pruefen()

    def _waehle_ziel(self):
        d = filedialog.askdirectory(title="Ordner fuer die Umgebung (wird angelegt)")
        if d:
            self._setze_ziel(os.path.normpath(d))

    def _waehle_basis(self):
        d = filedialog.askopenfilename(title="python.exe (3.12)", filetypes=[("python.exe", "python.exe")])
        if d:
            self.v_basis.set(os.path.normpath(d))
            self.neu_pruefen()

    def _waehle_wheel(self):
        d = filedialog.askdirectory(title="Ordner mit heruntergeladenen Paketen")
        if d:
            self.v_wheel.set(os.path.normpath(d))

    def _waehle_ffmpeg(self):
        d = filedialog.askopenfilename(title="FFmpeg-Build (ZIP)", filetypes=[("ZIP", "*.zip")])
        if d:
            self.v_ffmpeg.set(os.path.normpath(d))
            if "ffmpeg" in self.haken:
                self.haken["ffmpeg"].set(True)

    # -- Pruefen --------------------------------------------------------------
    def neu_pruefen(self, auswahl_setzen=True):
        if self.lauf:
            return
        self._uebernehme()
        for st, det in self.status_labels.values():
            st.configure(text="...", foreground="#6b6b6b")
        ziel = self.ziel
        ctx = {"tests": dict(self.test_ergebnisse)}

        def arbeit():
            befunde = kern.pruefe_alle(ziel, ctx)
            self.q.put(("befunde", (befunde, auswahl_setzen)))

        threading.Thread(target=arbeit, daemon=True).start()

    def _zeige_befunde(self, befunde, auswahl_setzen):
        self.befunde = befunde
        for kid, (st, det) in self.status_labels.items():
            b = befunde[kid]
            st.configure(text=kern.STATUS_TEXT[b.status], foreground=FARBEN.get(b.status, "black"))
            det.configure(text=b.detail[:140])
        if auswahl_setzen:
            self.fehlende_waehlen()

    def fehlende_waehlen(self):
        wahl = set(kern.vorauswahl(self.befunde))
        for kid, v in self.haken.items():
            v.set(kid in wahl)

    def _gewaehlt(self):
        return [kid for kid, v in self.haken.items() if v.get()]

    # -- Aktionen -------------------------------------------------------------
    def _plan(self, aktion, ids):
        self._uebernehme()
        if not ids:
            messagebox.showinfo("M4 Setup", "Nichts ausgewaehlt.")
            return None
        try:
            return kern.plane(aktion, ids, self.ziel, self.befunde or None)
        except kern.PlanFehler as exc:
            messagebox.showwarning("M4 Setup", str(exc))
            return None

    def befehle_anzeigen(self):
        schritte = self._plan("installieren", self._gewaehlt())
        if schritte is None:
            return
        text = "\n".join(s.als_text() for s in schritte) or "rem Nichts zu tun."
        top = tk.Toplevel(self.w)
        top.title("Geplante Befehle (zum Kopieren / Handinstallation)")
        top.geometry("900x420")
        t = ScrolledText(top, font=("Consolas", 9), wrap="none")
        t.pack(fill="both", expand=True)
        t.insert("1.0", "rem Ziel: %s   Build: %s\n%s\n" % (self.ziel.venv, self.ziel.build.upper(), text))

        def speichern():
            d = filedialog.asksaveasfilename(parent=top, defaultextension=".bat",
                                             initialfile="m4_installieren_von_hand.bat",
                                             filetypes=[("Batch", "*.bat"), ("Text", "*.txt")])
            if d:
                with open(d, "w", encoding="utf-8") as f:
                    f.write("@echo off\n" + t.get("1.0", "end"))

        ttk.Button(top, text="Als Datei speichern", command=speichern).pack(pady=4)

    def checkliste(self):
        if not self.befunde:
            messagebox.showinfo("M4 Setup", "Die Pruefung laeuft noch -- gleich noch einmal klicken.")
            return
        datei = kern.SETUP_DIR / "Checkliste_Laborbetreuer.md"
        try:
            datei.write_text(kern.checkliste(self.ziel, self.befunde), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("M4 Setup", "Checkliste nicht geschrieben:\n%s: %s" % (type(exc).__name__, exc))
            return
        self._schreibe("Checkliste geschrieben: %s" % datei)
        oeffne_datei(datei, self._schreibe)
        messagebox.showinfo("M4 Setup", "Checkliste geschrieben und geoeffnet:\n\n%s\n\n"
                            "(Oeffnet sich kein Fenster, liegt sie evtl. als Tab in VS Code.)" % datei)

    def umgebung_loeschen(self):
        self._uebernehme()
        if not self.ziel.venv.exists():
            messagebox.showinfo("M4 Setup", "%s existiert nicht." % self.ziel.venv)
            return
        if not messagebox.askyesno("Umgebung loeschen",
                                   "Den Ordner\n\n%s\n\nkomplett loeschen?\n\nAlle darin installierten "
                                   "Pakete sind danach weg (Datensaetze und Code liegen woanders "
                                   "und bleiben)." % self.ziel.venv, icon="warning"):
            return
        self._ausfuehren(kern.plane("deinstallieren", ["venv", "bc_python"], self.ziel, self.befunde))

    def starte(self, aktion):
        schritte = self._plan(aktion, self._gewaehlt())
        if schritte is None:
            return
        if not schritte:
            messagebox.showinfo("M4 Setup", "Nichts zu tun: alles Ausgewaehlte ist schon vorhanden.")
            return
        liste = "\n".join("  - " + s.text for s in schritte)
        frage = {"installieren": "Installieren", "reparieren": "Neu installieren (ohne Abhaengigkeiten)",
                 "deinstallieren": "Entfernen"}[aktion]
        if not messagebox.askyesno("M4 Setup", "%s nach\n%s:\n\n%s\n\nDetails: 'Befehle anzeigen'."
                                   % (frage, self.ziel.venv, liste)):
            return
        self._ausfuehren(schritte)

    def _ausfuehren(self, schritte):
        self._sperren(True)
        self.lauf = kern.Lauf(lambda text: self.q.put(("log", text)))
        lauf = self.lauf

        def arbeit():
            ok = lauf(schritte)
            self.q.put(("fertig", (ok, lauf)))

        threading.Thread(target=arbeit, daemon=True).start()

    def abbrechen(self):
        if self.lauf:
            self.lauf.abbrechen()

    def _sperren(self, an):
        for b in self.b_aktion:
            b.configure(state="disabled" if an else "normal")
        self.b_abbruch.configure(state="normal" if an else "disabled")

    # -- Ausgabe ----------------------------------------------------------------
    def _schreibe(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _queue_leeren(self):
        try:
            while True:
                art, wert = self.q.get_nowait()
                if art == "log":
                    self._schreibe(wert)
                elif art == "befunde":
                    self._zeige_befunde(*wert)
                elif art == "fertig":
                    ok, lauf = wert
                    self.test_ergebnisse.update(lauf.ergebnisse)
                    self.lauf = None
                    self._sperren(False)
                    self.neu_pruefen(auswahl_setzen=False)
                    if ok:
                        messagebox.showinfo("M4 Setup", "Fertig.\n\nLog: %s" % lauf.log_datei)
                    else:
                        messagebox.showwarning("M4 Setup", "Mit Fehlern beendet.\n\nLog: %s" % lauf.log_datei)
        except queue.Empty:
            pass
        self.w.after(100, self._queue_leeren)


def oeffne_datei(datei, log):
    """Mit dem zugeordneten Programm oeffnen; ist fuer .md keins hinterlegt
    (Windows-Standard), mit dem Editor. Scheitert beides, steht der Pfad im Log."""
    try:
        os.startfile(str(datei))
        return
    except OSError:
        pass
    try:
        import subprocess
        subprocess.Popen(["notepad.exe", str(datei)])
    except OSError as exc:
        log("Konnte die Datei nicht oeffnen (%s). Pfad: %s" % (exc, datei))
        messagebox.showinfo("M4 Setup", "Checkliste geschrieben:\n\n%s" % datei)


def starte(ziel):
    try:                                   # scharfe Schrift bei Windows-Skalierung > 100 %
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    wurzel = tk.Tk()
    SetupFenster(wurzel, ziel)
    wurzel.mainloop()
    return 0
