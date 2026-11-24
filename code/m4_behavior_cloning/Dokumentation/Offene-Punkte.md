# Offene Punkte (Sammelliste)

Notizen für später. Kommt evtl. als Abschnitt „Offene Punkte“ in die Bedienanleitung (Dokument C).

## Anlage und Bedienung

- **Tischpunkte in ein eigenes Koordinatensystem:** Alle Tischpunkte (ID0–ID8, IGNORE …) relativ
  zu einem Tisch-/Werkobjekt-Koordinatensystem neu teachen. Wird der Tisch verschoben, muss dann
  nur dieses Koordinatensystem neu eingemessen werden statt aller Punkte einzeln.

## Aus der Dokumentation gesammelt (Stand 19.11.2026)

- Höhe des Übergabepunkts PRE_PLACE über der Prüfvorrichtung vereinheitlichen
  (Hindernismodell 7 cm, Orchestrator ~9 cm).
- Greifer-Totzeit (0,5 s) per Video bestätigen.
- Override 0,5 mit dem Betreuer abstimmen.
- Achsgrenzen gegen Datenblatt/Pendant abgleichen (`JOINT_LIMITS_VERIFIED`).
- Ablauf der Gruppe (`m4_grasper.py`) auf „Policy greift, Planer transportiert“
  (`--transport-geplant`) umstellen, dann Doku A und C nachziehen.
- Standardwerte im Reiter Aufnahme in der Bedienanleitung nachtragen.
- Objektiv der Handgelenkkamera ist seit der ersten Aufnahme 3,6 mm F8.0 (kaum Verzeichnung),
  nicht Fisheye 1,85 mm: `bc/config.py` (Kommentar WRIST_CAMERA), `Requierments/requierments.md`
  und `Dokumentation/Kamera-Inbetriebnahme.md` korrigieren.
