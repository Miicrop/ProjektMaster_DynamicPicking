// Farb-Tokens und Schriften. Farbe ist Information: Lila nur für das Bauteil (wie der echte Druck),
// je Modul ein gedämpfter Akzent, Signalrot für Schlechtteil/Fehler/STOPP, Grün nur für den GUT-Stempel.
import * as THREE from 'three';
import titleFont from '@fontsource/space-grotesk/files/space-grotesk-latin-600-normal.woff?url';
import titleFontLight from '@fontsource/space-grotesk/files/space-grotesk-latin-400-normal.woff?url';
import sansFont from '@fontsource/ibm-plex-sans/files/ibm-plex-sans-latin-400-normal.woff?url';
import sansFontMedium from '@fontsource/ibm-plex-sans/files/ibm-plex-sans-latin-500-normal.woff?url';
import monoFont from '@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff?url';
import monoFontMedium from '@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-500-normal.woff?url';

export const T = {
  paper: '#F4F1EA',
  paperDeep: '#E9E3D6', // Flächen ohne Bedeutung (Tisch, Gehäuse)
  grid: '#CFC6B4',
  ink: '#1E2328',
  inkSoft: '#6B6F73',
  inkFaint: '#A8A49A',
  signal: '#D64933', // Schlechtteil / Fehler / STOPP (Rotstift)
  good: '#3C8A4E', // nur GUT-Stempel und Gut-Ablage
  detect: '#2FE05F', // Bildverarbeitungs-Overlay auf Fotos (klassisches OpenCV-Grün)
  part: '#7B4FA0', // das Bauteil (lila 3D-Druck)
  board: '#3A3F45', // dunkle Platte im Arbeitsbereich
};

// Modulfarben: Blöcke im Architekturbild, Kopflinie der Modulakte, Datenkarten. Kein Rot, kein Lila.
export const MODULE_COLOR = { M1: '#3F6F94', M2: '#B07A2A', M3: '#2F7F7A', M4: '#9A5A2E', ORCH: '#1E2328' };
export const moduleColor = (key) => MODULE_COLOR[key] ?? T.inkSoft;

export const FONTS = {
  title: titleFont,
  titleLight: titleFontLight,
  sans: sansFont,
  sansMedium: sansFontMedium,
  mono: monoFont,
  monoMedium: monoFontMedium,
};

export const color = (hex) => new THREE.Color(hex);

/** Millimeter mit deutschem Komma: 197.5 → „197,5 mm“. */
export const fmtMm = (v, digits = 1) => `${v.toFixed(digits).replace('.', ',')} mm`;

export const EASE = { cam: 'power3.inOut', appear: 'expo.out', move: 'power2.inOut' };
