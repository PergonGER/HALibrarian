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
  Lücke, siehe direkt unten.
- ~~KI-gestützte Serien-Vorschläge~~ — umgesetzt 2026-09-10 via Issue
  #12, v0.10.0. Jules-PR #21 hatte einen echten Bug (`ai_task.
  async_generate_data()` gibt ein `GenDataTaskResult`-Objekt zurück,
  kein dict — `isinstance(result, dict)`-Check griff nie, Funktion
  landete immer im leeren Fallback); Jules hat auf das
  `REQUEST_CHANGES`-Review mit einem inhaltsleeren Commit reagiert
  (identischer Tree-Hash, bekanntes Muster). Auf Nutzer-Autorisierung
  hin selbst gefixt (`result.data` statt `result`) und über PR #22
  gemergt. **Live gegen echten `ai_task`-Provider (Gemini) auf iOS
  bestätigt funktionierend** (2026-09-11).
- ~~Buch hinzufügen: Teilangaben reichen, Rest wird automatisch
  ergänzt~~ — umgesetzt 2026-09-10 via Jules-PR #19 (Issue #17,
  v0.8.0): Google-Books-Freitextsuche im Buch-hinzufügen-Dialog,
  Pflichtfelder entfernt, Trefferliste zur Auswahl. Bewusst kein
  Gemini/`ai_task`-Fallback (Nutzer-Entscheidung).
- ~~Bücherliste: Klick auf Bucheintrag öffnet Detail-Popup~~ —
  umgesetzt 2026-09-10 via Jules-PR #20 (Issue #18, v0.9.0): Karten
  kompakt (Cover/Titel/Autor), Detail-Popup mit allen Infos+Aktionen.
- ~~iOS-Kamera-Scanner defekt (Root Cause: iframe-Sandbox)~~ —
  umgesetzt 2026-09-10 via Migration auf `panel_custom` (Issue #13,
  PR #16, v0.7.0) plus Nachfixes für Asset-Pfade/Dialoge/Banner (v0.7.1
  bis v0.7.3, siehe Commit-Historie). Verbleibende Blockade bei dir war
  keine Code-Ursache mehr, sondern die `getUserMedia`-Secure-Context-
  Anforderung (HTTPS) — gelöst durch Einrichtung von Nabu Casa auf
  deiner Seite. README enthält den Hintergrund für künftige Nutzer mit
  demselben Problem. **Kamera-Scanner auf iOS bestätigt funktionierend**
  (2026-09-11).
- ~~Buchkarten-Klick öffnete Detail-Popup nicht in der HA Companion
  App (Android)~~ — umgesetzt 2026-09-11 (v0.10.2): Karte war ein
  `<div>` mit nur `addEventListener("click", ...)`, kein natives
  interaktives Element — manche Android-WebViews liefern synthetische
  Klick-Events darauf unzuverlässig. Fix: Karte ist jetzt ein echtes
  `<button type="button">`. Funktionierte bereits vorher im normalen
  mobilen Browser, nur die App-WebView war betroffen. Bestätigt
  funktionierend (2026-09-14).
- ~~Design: kantige Elemente, moderneres/weicheres Erscheinungsbild
  gewünscht~~ — umgesetzt 2026-09-11 (v0.11.0): einheitliche
  Radius-Skala (`--lt-radius-sm/md/lg`, 8/12/18px) statt verstreuter
  2–8px-Einzelwerte, weichere zweischichtige Schatten statt harter
  Einzelschatten, in hellem und dunklem Theme konsistent. Bestätigt
  gefallen (2026-09-14).

## Offen

- **Serien-seriesId-API-Einschränkung** (Ursprungs-Recherche vom
  2026-09-10, weiterhin relevant für Issue #12): kein Google-Books-API-
  Endpunkt, um nach allen Büchern einer `seriesId` zu suchen, keine
  automatische Lückenerkennung fehlender Bände.
- **Regalfoto → KI-Massenerkennung/-Import** — **auf Eis gelegt**
  (Nutzer-Entscheidung 2026-09-14, kein Zeitplan). Nutzerwunsch vom
  2026-09-10: Foto eines ganzen Bücherregals aufnehmen, KI erkennt einzelne Bücher
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
