# Backlog

Ideen und Anforderungen, die bewusst noch nicht umgesetzt wurden — zur
Berücksichtigung bei der nächsten passenden Erweiterung (Jules-Issue
oder direkter Fix). Kein Roadmap-Dokument mit Reihenfolge/Priorität,
nur eine Merkliste, damit nichts verloren geht.

- **Autorenliste: Autoren ohne Bücher ausblenden.** Sobald ein Autor
  keine Bücher mehr in der Bibliothek hat (letztes zugehöriges Buch
  gelöscht), soll er nicht mehr in der Autorenliste angezeigt werden.
  Betrifft `db.get_authors()` (Filter auf Autoren mit ≥1 Buch, z. B.
  über einen `JOIN`/`EXISTS` gegen `Books`) und ggf. `renderAuthors()`
  im Panel. Nicht sofort umsetzen, erst bei der nächsten inhaltlichen
  Erweiterung der Autoren-Funktionen mit aufnehmen. (Hinzugefügt:
  2026-09-10)

- **Einstellungen: Bücherliste-Layout (Spaltenanzahl) pro Gerät.**
  Nutzer soll wählen können, wie viele Bücher pro Reihe in der
  Bücherliste (`.lt-books-grid`) angezeigt werden (z. B. 1, 2, 3 oder
  automatisch/aktuelles Verhalten). Gehört in den bestehenden
  Einstellungsdialog (Zahnrad-Icon, siehe `settings-dialog` in
  `index.html`/`app.js`) und wird wie Titel/Farbschema pro Gerät in
  `localStorage` gespeichert (kein Backend-Command nötig) — z. B. über
  eine CSS-Variable, die `grid-template-columns` steuert, statt
  `repeat(auto-fill, minmax(280px, 1fr))` fest vorzugeben. (Hinzugefügt:
  2026-09-10)

- **Hinweis auf andere Bände derselben Buchreihe (z. B. "Herr der
  Ringe" Teil 1 → Verweis auf Teil 2/3).** Recherchiert am 2026-09-10,
  **mit wichtiger Einschränkung**: Google Books liefert bei manchen
  Büchern `volumeInfo.seriesInfo.volumeSeries[].seriesId` +
  `orderNumber`, aber es gibt **keinen API-Endpunkt, um nach allen
  Büchern einer `seriesId` zu suchen** — das Feld lässt sich nur bei
  bereits bekannten Büchern auslesen, nicht zum Finden fehlender Bände
  nutzen. Abdeckung außerdem lückenhaft (v. a. bei deutschen/älteren
  Ausgaben oft nicht gesetzt). Realistischer Umsetzungsweg:
  1. Zuverlässig, kein zusätzlicher Aufwand: bereits vorhandene
     Autor-Klick-Filterung (zeigt alle Bücher desselben Autors in der
     eigenen Bibliothek) als Serien-Ersatz kommunizieren/hervorheben.
  2. Optional, unsicher: `seriesId` beim ISBN-Lookup mitspeichern
     (neue Spalte `Books.series_id`, `Books.series_order`) und in der
     eigenen Bibliothek Bücher mit gleicher `seriesId` verlinken — hilft
     nur, wenn Google das Feld für die jeweilige Ausgabe überhaupt
     füllt, und findet nie automatisch fehlende Bände, die man noch
     nicht erfasst hat. Vor Umsetzung mit Nutzer klären, ob dieser
     eingeschränkte Nutzen die Komplexität rechtfertigt. (Hinzugefügt:
     2026-09-10)
