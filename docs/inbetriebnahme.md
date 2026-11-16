# Inbetriebnahme der Anlage

Schritt-für-Schritt-Anleitung, um die Anlage (Roboter, Greifer, Kameras, GUI) in Betrieb zu nehmen.

> Bilder liegen unter `docs/img/inbetriebnahme/` und werden an den markierten Stellen eingefügt.

---

## 1. Hardware anschließen

Alle Komponenten verbinden: Roboter, Greifer usw.
Kameras und Roboter-Ethernet werden **noch nicht** angesteckt, siehe Schritt 6.

<!-- ![Verkabelung](img/inbetriebnahme/01_verkabelung.jpg) -->

## 2. Robotersteuerung einschalten

Die Robotersteuerung einschalten.

<!-- ![Hauptschalter Steuerung](img/inbetriebnahme/02_steuerung_ein.jpg) -->

## 3. Touchpad einschalten und anmelden

1. Das Touchpad (Teach-Pendant) einschalten.
2. **Bei schwarzem Bildschirm:** Kabel des Touchpads abziehen und wieder einstecken.
3. Anmelden.

<!-- ![Touchpad Anmeldung](img/inbetriebnahme/03_touchpad_login.jpg) -->

## 4. Roboter einschalten (Power On)

1. Auf **Real** umschalten.
2. Den **weißen Knopf** an der Steuerung drücken → **Power On**.

<!-- ![Real-Modus](img/inbetriebnahme/04_real_modus.jpg) -->
<!-- ![Weißer Knopf](img/inbetriebnahme/04_weisser_knopf.jpg) -->

## 5. Greifer-Ausgang setzen

1. **Settings → IO Settings** öffnen.
2. **Output 1.3** auf **1** setzen.
3. **Alle anderen Outputs müssen auf 0 stehen.**

<!-- ![IO Settings](img/inbetriebnahme/05_io_settings.jpg) -->

## 6. Kameras und Ethernet anstecken

1. Kameras an den Rechner anstecken.
2. Ethernet-Kabel des Roboters an den Rechner anstecken.

<!-- ![Kameras und Ethernet](img/inbetriebnahme/06_kameras_ethernet.jpg) -->

## 7. GUI starten

Die GUI auf dem Rechner starten.

```bash
# TODO: Startbefehl eintragen
```

<!-- ![GUI](img/inbetriebnahme/07_gui.png) -->

---

## Checkliste

- [ ] Roboter, Greifer usw. angesteckt
- [ ] Robotersteuerung eingeschaltet
- [ ] Touchpad an (bei Blackscreen: Kabel ab- und wieder anstecken), angemeldet
- [ ] Auf Real geschaltet, weißer Knopf → Power On
- [ ] Settings/IO Settings: Output 1.3 = 1, alle anderen = 0
- [ ] Kameras angesteckt
- [ ] Roboter-Ethernet angesteckt
- [ ] GUI gestartet

## Fehlerbehebung

| Problem | Lösung |
|---|---|
| Touchpad bleibt schwarz | Kabel abziehen und wieder einstecken |
| _TODO_ | _TODO_ |
