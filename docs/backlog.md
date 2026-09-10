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
