# HA Library Tracker

Custom Home Assistant integration (HACS-kompatibel) zur Verwaltung der
eigenen Buchsammlung: Katalogisieren per ISBN-Scan, Bewertungen,
Wunschliste und automatische Benachrichtigungen bei Neuerscheinungen
favorisierter Autoren.

## Status

**Session 1 (aktuell):** Grundgerüst der Integration + Custom Panel.

- `custom_components/library_tracker/` – die Integration
  (`manifest.json`, `__init__.py`, `config_flow.py`, `const.py`)
- Registrierung eines eigenen Menüpunkts ("Library Tracker") in der
  HA-Seitenleiste, der ein statisches Platzhalter-Frontend lädt
  (`panel/index.html`, `.css`, `.js`) – als schlankes Iframe-Panel ohne
  eigenen JS-Build.
- UI-Config-Flow zur Einrichtung: optionaler Google Books API-Key
  (Fallback: Open Library API), Notify-Service für Alerts, Intervall
  für den Autoren-Check.

Kommende Ausbaustufen (siehe Projekt-Blueprint):

1. Backend-Logik, SQLite-Datenbank (inkl. Bewertungs-Spalte) und
   WebSocket-Commands, Anbindung Google Books / Open Library.
2. Frontend-UI (Material Design), Kamera-basierter ISBN-Scanner,
   interaktive 1–5-Sterne-Bewertung.
3. Asynchroner Hintergrund-Job für Autoren-Tracking und
   HA-Benachrichtigungen bei Neuerscheinungen.

## Installation (Entwicklung)

1. Repo-Ordner `custom_components/library_tracker` nach
   `<config>/custom_components/library_tracker` kopieren bzw. verlinken.
2. Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → Integration hinzufügen →
   "HA Library Tracker" suchen und einrichten.
4. In der Seitenleiste erscheint der Menüpunkt "Library Tracker".

## Hinweis zum Kamera-Scanner (ab Session 3)

Der Barcode-Scanner nutzt `getUserMedia` und benötigt daher einen
"secure context" – also HTTPS (z. B. via Nabu Casa oder eigenes
Zertifikat) oder `localhost`. Über reines HTTP im lokalen Netzwerk wird
der Browser den Kamerazugriff blockieren – bestätigt betroffen: iOS/
Safari (inkl. HA Companion App) bei Zugriff über eine lokale IP ohne
SSL. Das ist unabhängig von der Panel-Architektur (auch nach der
`panel_custom`-Migration ab v0.7.0) und kann nicht von der Integration
aus umgangen werden – nötig ist HTTPS-Zugriff auf Home Assistant selbst,
am einfachsten über [Nabu Casa](https://www.nabucasa.com/). Ein
kostenloses Zertifikat direkt für eine private/lokale IP-Adresse (z. B.
`192.168.x.x`) gibt es nicht – auch Let's Encrypts neue
IP-Zertifikate (seit 2025) gelten nur für öffentliche IPs. Kostenlose
Alternative: eigene (Sub-)Domain (z. B. via DuckDNS) + HAs
Let's-Encrypt-Add-on.

## Entwicklungsprozess mit Jules

Feature-Sessions (siehe oben) werden über GitHub-Issues mit dem Label
`Jules` an den autonomen Coding-Agenten Jules delegiert; kleinere
Korrekturen erledigt Claude direkt. Ablauf, Rollen und gelernte
Regeln (u. a. zur Vermeidung überlappender Sessions) stehen in
[`docs/jules-collaboration-playbook.md`](docs/jules-collaboration-playbook.md).
