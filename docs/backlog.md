# Backlog

Ideen und Anforderungen, die bewusst noch nicht umgesetzt wurden — zur
Berücksichtigung bei der nächsten passenden Erweiterung (Jules-Issue
oder direkter Fix). Kein Roadmap-Dokument mit Reihenfolge/Priorität,
nur eine Merkliste, damit nichts verloren geht.

## Erledigt

- ~~Autorenliste: Autoren ohne Bücher ausblenden~~ — umgesetzt
  2026-09-10 (`db.get_authors()`, Favoriten bleiben sichtbar wegen der
  geplanten Autoren-Tracking-Funktion aus Session 4).
- ~~Einstellungen: Bücherliste-Layout (Spaltenanzahl) pro Gerät~~ —
  umgesetzt 2026-09-10 (Einstellungsdialog, `--lt-books-columns`).
- ~~Serien-Verknüpfung bereits erfasster Bücher~~ — umgesetzt 2026-09-10
  via Jules-PR #11 (Issue #10, v0.6.0): `series_id`/`series_order` auf
  `Books`, Google-Books-`seriesInfo`-Parsing, Serien-Badge/-Filter im
  Frontend. Weiterhin nur Verlinkung bereits selbst erfasster Bücher
  möglich (siehe Einschränkung unten) — Issue #12 (KI-gestützte
  Serien-Vorschläge via `ai_task`, ergänzend) adressiert genau diese
  Lücke, ist aber pausiert bis nach der `panel_custom`-Migration.

## Offen

- **iOS-Kamera-Scanner defekt (Root Cause: iframe-Sandbox)** — HA-Cores
  `ha-panel-iframe.ts` setzt `allow="fullscreen"` ohne `camera` auf dem
  iframe unseres Panels; von der Integration aus nicht änderbar. Fix:
  Migration von iframe-Panel auf `panel_custom` (verifiziert 2026-09-10
  via HA-Dev-Docs + Core-Quellcode: kein Build-Toolchain nötig, reines
  ES2015-Custom-Element via `panel_custom.async_register_panel(...,
  module_url=..., embed_iframe=False)`; behebt nebenbei auch die
  LLAT-Token-pro-Gerät-Friktion, da `hass` dann direkt als Property
  injiziert wird statt über eigenen WebSocket-Client mit Token). Als
  Jules-Issue vorgesehen — wird erst gelabelt, sobald keine andere
  Jules-Session mehr an `index.html`/`app.js` arbeitet.
- **Serien-seriesId-API-Einschränkung** (Ursprungs-Recherche vom
  2026-09-10, weiterhin relevant für Issue #12): kein Google-Books-API-
  Endpunkt, um nach allen Büchern einer `seriesId` zu suchen, keine
  automatische Lückenerkennung fehlender Bände.
- **Regalfoto → KI-Massenerkennung/-Import** (Nutzerwunsch 2026-09-10):
  Foto eines ganzen Bücherregals aufnehmen, KI erkennt einzelne Bücher
  (Titel/Autor anhand Buchrücken) und schlägt sie zum Import vor.
  Technisch grundsätzlich machbar, verifiziert am HA-Core-Quellcode
  (`ai_task/task.py`): `async_generate_data()` akzeptiert einen
  `attachments`-Parameter (Liste von `media_content_id`s, aufgelöst zu
  Kamera-/Image-Entity-Snapshots oder Media-Source-Dateien) — Gemini
  (`ai_task.google_ai_task`) ist multimodal, kann Bilder also
  grundsätzlich verarbeiten. Nutzt dieselbe `ai_task`-Infrastruktur wie
  Issue #12, daher sinnvollerweise **nach** #12 angehen (Fehlerbehandlung
  „kein ai_task-Provider konfiguriert" und das „KI-Vorschlag,
  ungeprüft"-UI-Muster lassen sich wiederverwenden statt neu zu bauen).
  Offene Punkte, die vor einem Issue-Zuschnitt geklärt werden müssen:
  - **Bildquelle**: Datei-Upload aus dem Panel (`<input type="file"
    accept="image/*" capture="environment">`, funktioniert auch als
    iframe-Aufnahme-Dialog, ist also **nicht** vom iOS-Kamera-Bug
    betroffen — anders als der Live-Video-Stream des ISBN-Scanners) vs.
    Ablage in `media_source`, damit `ai_task` per `media_content_id`
    darauf zugreifen kann. Muss noch recherchiert werden, wie ein von
    der Integration selbst hochgeladenes Bild (nicht aus `media_source`)
    am saubersten an `async_generate_data` übergeben wird.
  - **Erkennungsqualität ist eine echte Grenze, kein Implementierungs-
    detail**: Buchrücken-Text ist oft klein, vertikal gedreht oder
    schlecht beleuchtet — realistisch mit falsch erkannten/erfundenen
    Titeln rechnen (Halluzination), nicht nur mit Lücken. Ergebnis daher
    zwingend als ungeprüfte Vorschlagsliste mit Review-Schritt vor dem
    eigentlichen Hinzufügen (kein Auto-Import), idealerweise mit
    anschließendem Abgleich pro Titel über die bestehende Google-Books-
    Suche (echte ISBN/Cover/Metadaten statt reiner KI-Vermutung).
  - **Kostenaspekt**: Mehrere erkannte Bücher pro Foto bedeuten
    potenziell mehrere Folge-Abfragen (KI-Erkennung + je Titel eine
    Google-Books-Suche) — Nutzer sollte das vorher absehen können
    (Rate-Limits/Kosten seines KI-Providers).
