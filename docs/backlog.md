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
