// Library Tracker – Custom Panel Web Component
// Communicates directly with Home Assistant WebSocket API via this.hass.callWS(...)

class LibraryTrackerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._initialized = false;

    this._currentFilter = "all";
    this._currentSearchQuery = "";
    this._currentSeriesFilterId = null;
    this._html5QrCode = null;
    this._currentBooksRaw = [];
    this._currentBooks = [];
    this._currentAuthors = [];

    this._SETTINGS_STORAGE_KEY = "library_tracker_settings";
  }

  set hass(hass) {
    const isFirst = !this._hass;
    this._hass = hass;
    if (isFirst && this.isConnected && !this._initialized) {
      this._init();
    }
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this._patchGetElementById();
    if (this._hass && !this._initialized) {
      this._init();
    }
  }

  disconnectedCallback() {
    this._stopScanner();
  }

  _patchGetElementById() {
    if (document.getElementById.__lt_patched) return;
    const origGet = document.getElementById.bind(document);
    const self = this;
    document.getElementById = function (id) {
      const el = origGet(id);
      if (el) return el;
      if (self && self.shadowRoot) {
        return self.shadowRoot.getElementById(id);
      }
      return null;
    };
    document.getElementById.__lt_patched = true;
  }

  $(selector) {
    return this.shadowRoot ? this.shadowRoot.querySelector(selector) : null;
  }

  $$(selector) {
    return this.shadowRoot ? this.shadowRoot.querySelectorAll(selector) : [];
  }

  _init() {
    if (this._initialized) return;
    this._initialized = true;

    this.shadowRoot.innerHTML = `
      <link rel="stylesheet" href="/api/library_tracker/panel/style.css" />
      <header class="lt-header">
        <div class="lt-header__left">
          <span class="lt-header__icon">📚</span>
          <h1 class="lt-header__title">Library Tracker</h1>
        </div>
        <nav class="lt-nav" id="main-nav">
          <button class="lt-nav__btn lt-nav__btn--active" data-tab="tab-books">📚 Bücher</button>
          <button class="lt-nav__btn" data-tab="tab-authors">✍️ Autoren</button>
          <button class="lt-nav__btn" data-tab="tab-scanner">📷 ISBN-Scanner</button>
        </nav>
        <span class="lt-version-badge" id="version-badge" hidden></span>
        <button id="btn-open-settings" class="lt-icon-btn" title="Einstellungen" aria-label="Einstellungen">⚙️</button>
      </header>

      <main class="lt-main">
        <div id="dashboard-container">
          <!-- TAB 1: BOOKS -->
          <section id="tab-books" class="lt-tab-content">
            <div class="lt-toolbar">
              <div class="lt-filter-chips">
                <button class="lt-chip lt-chip--active" data-filter="all">Alle</button>
                <button class="lt-chip" data-filter="gelesen">Gelesen</button>
                <button class="lt-chip" data-filter="ungelesen">Ungelesen</button>
                <button class="lt-chip" data-filter="wunschliste">Wunschliste</button>
              </div>
              <button id="btn-open-add-dialog" class="lt-btn lt-btn--primary">+ Buch hinzufügen</button>
            </div>

            <div id="series-filter-banner" class="lt-alert lt-alert--info" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;" hidden>
              <span>📚 Filter: Bücher derselben Buchreihe</span>
              <button id="btn-clear-series-filter" class="lt-btn lt-btn--secondary lt-btn--sm">Filter aufheben</button>
            </div>

            <div class="lt-search-box" style="margin-bottom: 16px;">
              <input type="text" id="books-search-input" placeholder="Suche nach Titel, Autor, ISBN, Erscheinungsjahr …" />
            </div>

            <div id="books-list" class="lt-books-grid">
              <!-- Books cards rendered dynamically -->
            </div>
          </section>

          <!-- TAB 2: AUTHORS -->
          <section id="tab-authors" class="lt-tab-content" hidden>
            <div class="lt-card">
              <h2>Autoren &amp; Favoriten</h2>
              <p>Favorisierte Autoren werden für Benachrichtigungen bei Neuerscheinungen überwacht.</p>
              <div id="authors-list" class="lt-authors-list">
                <!-- Authors rendered dynamically -->
              </div>
            </div>
          </section>

          <!-- TAB 3: SCANNER & MANUAL LOOKUP -->
          <section id="tab-scanner" class="lt-tab-content" hidden>
            <div class="lt-card">
              <h2>ISBN-Barcode scannen</h2>
              <p>Richte die Kamera auf den Barcode eines Buchs. Alternativ steht unten die manuelle Suche zur Verfügung.</p>

              <div class="lt-scanner-controls">
                <button id="btn-start-scanner" class="lt-btn lt-btn--primary">Kamera starten</button>
                <button id="btn-stop-scanner" class="lt-btn lt-btn--secondary" disabled>Kamera stoppen</button>
              </div>

              <div id="scanner-error" class="lt-alert lt-alert--error" hidden></div>

              <div id="qr-reader" class="lt-scanner-viewport"></div>
            </div>

            <div class="lt-card" style="margin-top: 1rem;">
              <h2>Manuelle ISBN-Suche</h2>
              <p>ISBN direkt eingeben (z. B. 9783453318113):</p>
              <div class="lt-search-box">
                <input type="text" id="manual-isbn-input" placeholder="ISBN-10 oder ISBN-13" />
                <button id="btn-manual-lookup" class="lt-btn lt-btn--primary">ISBN suchen</button>
              </div>
            </div>
          </section>
        </div>
      </main>

      <!-- MODAL / DIALOG: Add & Edit Book -->
      <dialog id="book-dialog" class="lt-dialog">
        <div class="lt-dialog__content">
          <div class="lt-dialog__header">
            <h3 id="dialog-title">Buch hinzufügen</h3>
            <button id="btn-close-dialog" class="lt-dialog__close">&times;</button>
          </div>
          <form id="book-form" class="lt-form">
            <input type="hidden" id="form-book-id" value="" />
            <input type="hidden" id="form-series-id" value="" />
            <input type="hidden" id="form-series-order" value="" />

            <div class="lt-form__group">
              <label for="form-isbn">ISBN *</label>
              <input type="text" id="form-isbn" required placeholder="z. B. 9783453318113" />
            </div>

            <div class="lt-form__group">
              <label for="form-title">Titel *</label>
              <input type="text" id="form-title" required placeholder="Buchtitel" />
            </div>

            <div class="lt-form__group">
              <label for="form-author">Autor *</label>
              <input type="text" id="form-author" required placeholder="Autor Name" />
            </div>

            <div class="lt-form__group">
              <label for="form-published-date">Erscheinungsjahr / -datum</label>
              <input type="text" id="form-published-date" placeholder="z. B. 2021" />
            </div>

            <div class="lt-form__group">
              <label for="form-cover-url">Cover-URL</label>
              <input type="url" id="form-cover-url" placeholder="https://..." />
            </div>

            <div class="lt-form__group">
              <label for="form-status">Status *</label>
              <select id="form-status" required>
                <option value="ungelesen">ungelesen</option>
                <option value="gelesen">gelesen</option>
                <option value="wunschliste">wunschliste</option>
              </select>
            </div>

            <div class="lt-form__group">
              <label>Bewertung (1-5 Sterne)</label>
              <div id="form-rating-stars" class="lt-stars lt-stars--interactive" data-rating="0"></div>
              <input type="hidden" id="form-rating-val" value="" />
            </div>

            <div class="lt-form__actions">
              <button type="button" id="btn-cancel-dialog" class="lt-btn lt-btn--secondary">Abbrechen</button>
              <button type="submit" id="btn-save-book" class="lt-btn lt-btn--primary">Speichern</button>
            </div>
          </form>
        </div>
      </dialog>

      <!-- CONFIRM DIALOG -->
      <dialog id="confirm-dialog" class="lt-dialog">
        <div class="lt-dialog__content">
          <div class="lt-dialog__header">
            <h3 id="confirm-dialog-title">Bestätigen</h3>
          </div>
          <p id="confirm-dialog-message"></p>
          <div class="lt-form__actions">
            <button type="button" id="btn-confirm-cancel" class="lt-btn lt-btn--secondary">Abbrechen</button>
            <button type="button" id="btn-confirm-ok" class="lt-btn lt-btn--danger">Löschen</button>
          </div>
        </div>
      </dialog>

      <!-- SETTINGS DIALOG -->
      <dialog id="settings-dialog" class="lt-dialog">
        <div class="lt-dialog__content">
          <div class="lt-dialog__header">
            <h3>Einstellungen</h3>
            <button id="btn-close-settings" class="lt-dialog__close">&times;</button>
          </div>
          <form id="settings-form" class="lt-form">
            <div class="lt-form__group">
              <label for="settings-title">Panel-Titel</label>
              <input type="text" id="settings-title" placeholder="Library Tracker" maxlength="60" />
            </div>

            <div class="lt-form__group">
              <label for="settings-theme">Farbschema</label>
              <select id="settings-theme">
                <option value="system">Systemeinstellung folgen</option>
                <option value="light">Hell</option>
                <option value="dark">Dunkel</option>
              </select>
            </div>

            <div class="lt-form__group">
              <label for="settings-columns">Bücher pro Reihe</label>
              <select id="settings-columns">
                <option value="auto">Automatisch (je nach Fensterbreite)</option>
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3">3</option>
                <option value="4">4</option>
              </select>
            </div>

            <p class="lt-status-msg">Diese Einstellungen gelten nur für dieses Gerät/diesen Browser.</p>

            <div class="lt-form__actions">
              <button type="button" id="btn-settings-reset" class="lt-btn lt-btn--secondary">Zurücksetzen</button>
              <button type="submit" class="lt-btn lt-btn--primary">Speichern</button>
            </div>
          </form>
        </div>
      </dialog>

      <!-- TOAST NOTIFICATIONS -->
      <div id="toast-container" class="lt-toast-container"></div>
    `;

    this._applySettings(this._loadSettings());
    this._attachEventListeners();

    this._loadBooks();
    this._loadAuthors();
    this._loadVersion();
  }

  _loadSettings() {
    try {
      const raw = window.localStorage.getItem(this._SETTINGS_STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (err) {
      return {};
    }
  }

  _saveSettings(settings) {
    try {
      window.localStorage.setItem(this._SETTINGS_STORAGE_KEY, JSON.stringify(settings));
    } catch (err) {
      console.warn("[library_tracker] Could not persist settings:", err);
    }
  }

  _applySettings(settings) {
    const titleEl = this.$(".lt-header__title");
    if (titleEl) {
      titleEl.textContent = settings.title && settings.title.trim() ? settings.title.trim() : "Library Tracker";
    }

    if (settings.theme === "light" || settings.theme === "dark") {
      this.dataset.theme = settings.theme;
      document.documentElement.dataset.theme = settings.theme;
    } else {
      delete this.dataset.theme;
      delete document.documentElement.dataset.theme;
    }

    const booksGrid = this.$("#books-list");
    if (booksGrid) {
      const cols = parseInt(settings.columns, 10);
      if (cols >= 1 && cols <= 4) {
        booksGrid.style.setProperty("--lt-books-columns", `repeat(${cols}, 1fr)`);
      } else {
        booksGrid.style.removeProperty("--lt-books-columns");
      }
    }
  }

  _showToast(message, isError = false) {
    const container = this.$("#toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `lt-toast ${isError ? "lt-toast--error" : ""}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      toast.style.transition = "opacity 0.3s, transform 0.3s";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  _createStarRatingComponent(rating, onRatingChange, interactive = true) {
    const container = document.createElement("div");
    container.className = `lt-stars ${interactive ? "lt-stars--interactive" : ""}`;
    let currentVal = rating || 0;

    for (let i = 1; i <= 5; i++) {
      const star = document.createElement("span");
      star.className = `lt-star ${i <= currentVal ? "lt-star--filled" : ""}`;
      star.innerHTML = "★";
      star.dataset.value = i;

      if (interactive) {
        star.addEventListener("click", () => {
          const newVal = currentVal === i ? null : i;
          currentVal = newVal || 0;
          this._updateStars(container, currentVal);
          if (onRatingChange) onRatingChange(newVal);
        });

        star.addEventListener("mouseenter", () => {
          this._updateStars(container, i);
        });

        container.addEventListener("mouseleave", () => {
          this._updateStars(container, currentVal);
        });
      }

      container.appendChild(star);
    }

    return container;
  }

  _updateStars(container, val) {
    const stars = container.querySelectorAll(".lt-star");
    stars.forEach((star, idx) => {
      if (idx < val) {
        star.classList.add("lt-star--filled");
      } else {
        star.classList.remove("lt-star--filled");
      }
    });
  }

  async _loadBooks() {
    if (!this._hass) return;
    try {
      const banner = this.$("#series-filter-banner");
      if (this._currentSeriesFilterId) {
        if (banner) banner.hidden = false;
        const msg = {
          type: "library_tracker/books/list_by_series",
          series_id: this._currentSeriesFilterId,
        };
        this._currentBooksRaw = await this._hass.callWS(msg);
      } else {
        if (banner) banner.hidden = true;
        const msg = { type: "library_tracker/books/list" };
        if (this._currentFilter !== "all") {
          msg.status = this._currentFilter;
        }
        this._currentBooksRaw = await this._hass.callWS(msg);
      }
      this._applySearchFilterAndRender();
    } catch (err) {
      this._showToast("Fehler beim Laden der Bücher: " + (err.message || err), true);
    }
  }

  _applySearchFilterAndRender() {
    const query = this._currentSearchQuery.trim().toLowerCase();
    const filtered = !query
      ? this._currentBooksRaw
      : this._currentBooksRaw.filter((book) => {
          const haystack = [
            book.title,
            book.author,
            book.isbn,
            book.published_date,
            book.status,
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();
          return haystack.includes(query);
        });
    this._currentBooks = filtered;
    this._renderBooks(filtered);
  }

  _renderBooks(books) {
    const container = this.$("#books-list");
    if (!container) return;
    container.innerHTML = "";

    if (!books || books.length === 0) {
      container.innerHTML = `<div class="lt-card" style="grid-column: 1 / -1; text-align: center; color: var(--lt-text-secondary);">Keine Bücher in dieser Ansicht vorhanden.</div>`;
      return;
    }

    books.forEach((book) => {
      const card = document.createElement("div");
      card.className = "lt-book-card";

      let coverHtml;
      if (book.cover_url) {
        coverHtml = `<img src="${this._escapeHtml(book.cover_url)}" class="lt-book-card__cover" alt="Cover" />`;
      } else {
        coverHtml = `<div class="lt-book-card__cover">📖</div>`;
      }

      const starsEl = this._createStarRatingComponent(book.rating, async (newRating) => {
        const prevRating = book.rating;
        book.rating = newRating;
        try {
          await this._hass.callWS({
            type: "library_tracker/books/update",
            book_id: book.id,
            rating: newRating,
          });
          this._showToast("Bewertung aktualisiert.");
        } catch (err) {
          book.rating = prevRating;
          this._renderBooks(this._currentBooks);
          this._showToast("Fehler beim Aktualisieren der Bewertung: " + (err.message || err), true);
        }
      });

      let seriesBadgeHtml = "";
      if (book.series_id) {
        const label = book.series_order
          ? `Teil ${this._escapeHtml(book.series_order)} der Reihe`
          : "Teil einer Reihe";
        seriesBadgeHtml = `<div><span class="lt-badge lt-badge--series btn-series-link" title="Alle Bücher dieser Reihe anzeigen">📚 ${label}</span></div>`;
      }

      card.innerHTML = `
        ${coverHtml}
        <div class="lt-book-card__content">
          <div>
            <h4 class="lt-book-card__title" title="${this._escapeHtml(book.title)}">${this._escapeHtml(book.title)}</h4>
            <p class="lt-book-card__author">${this._escapeHtml(book.author)}</p>
            <p class="lt-book-card__meta">
              <span class="lt-badge lt-badge--${this._escapeHtml(book.status)}">${this._escapeHtml(book.status)}</span>
              ${book.published_date ? ` • ${this._escapeHtml(book.published_date)}` : ""}
            </p>
            ${seriesBadgeHtml}
          </div>
          <div class="lt-book-card__rating-container"></div>
          <div class="lt-book-card__actions">
            ${book.status !== "gelesen" ? `<button class="lt-btn lt-btn--secondary lt-btn--sm btn-mark-read">✓ Gelesen</button>` : ""}
            <button class="lt-btn lt-btn--secondary lt-btn--sm btn-edit-book">Bearbeiten</button>
            <button class="lt-btn lt-btn--danger lt-btn--sm btn-delete-book">Löschen</button>
          </div>
        </div>
      `;

      const seriesLink = card.querySelector(".btn-series-link");
      if (seriesLink) {
        seriesLink.addEventListener("click", () => {
          this._currentSeriesFilterId = book.series_id;
          this._loadBooks();
        });
      }

      card.querySelector(".lt-book-card__rating-container").appendChild(starsEl);

      const markReadBtn = card.querySelector(".btn-mark-read");
      if (markReadBtn) {
        markReadBtn.addEventListener("click", async () => {
          try {
            await this._hass.callWS({
              type: "library_tracker/books/update",
              book_id: book.id,
              status: "gelesen",
            });
            this._showToast(`"${book.title}" als gelesen markiert.`);
            this._loadBooks();
          } catch (err) {
            this._showToast("Fehler beim Aktualisieren: " + (err.message || err), true);
          }
        });
      }

      card.querySelector(".btn-edit-book").addEventListener("click", () => {
        this._openBookDialog(book);
      });

      card.querySelector(".btn-delete-book").addEventListener("click", async () => {
        const confirmed = await this._showConfirmDialog(`Soll "${book.title}" wirklich gelöscht werden?`);
        if (confirmed) {
          try {
            await this._hass.callWS({
              type: "library_tracker/books/delete",
              book_id: book.id,
            });
            this._showToast("Buch gelöscht.");
            this._loadBooks();
            this._loadAuthors();
          } catch (err) {
            this._showToast("Fehler beim Löschen: " + (err.message || err), true);
          }
        }
      });

      container.appendChild(card);
    });
  }

  async _loadAuthors() {
    if (!this._hass) return;
    try {
      const authors = await this._hass.callWS({ type: "library_tracker/authors/list" });
      this._currentAuthors = authors;
      this._renderAuthors(authors);
    } catch (err) {
      this._showToast("Fehler beim Laden der Autoren: " + (err.message || err), true);
    }
  }

  async _loadVersion() {
    if (!this._hass) return;
    const badge = this.$("#version-badge");
    if (!badge) return;
    try {
      const result = await this._hass.callWS({ type: "library_tracker/version" });
      badge.textContent = `v${result.version}`;
      badge.hidden = false;
    } catch (err) {
      console.warn("[library_tracker] Could not load version:", err);
    }
  }

  _renderAuthors(authors) {
    const container = this.$("#authors-list");
    if (!container) return;
    container.innerHTML = "";

    if (!authors || authors.length === 0) {
      container.innerHTML = `<p style="color: var(--lt-text-secondary);">Noch keine Autoren erfasst.</p>`;
      return;
    }

    authors.forEach((author) => {
      const item = document.createElement("div");
      item.className = "lt-author-item";

      const starsEl = this._createStarRatingComponent(author.rating, async (newRating) => {
        const prevRating = author.rating;
        author.rating = newRating;
        try {
          await this._hass.callWS({
            type: "library_tracker/authors/set_rating",
            author_id: author.id,
            rating: newRating,
          });
          this._showToast("Autoren-Bewertung aktualisiert.");
        } catch (err) {
          author.rating = prevRating;
          this._renderAuthors(this._currentAuthors);
          this._showToast("Fehler beim Aktualisieren der Autoren-Bewertung: " + (err.message || err), true);
        }
      });

      item.innerHTML = `
        <span class="lt-author-item__name lt-author-item__name--clickable" title="Bücher von ${this._escapeHtml(author.name)} anzeigen">${this._escapeHtml(author.name)}</span>
        <div class="lt-author-item__actions">
          <div class="lt-author-item__rating"></div>
          <button class="lt-fav-btn" title="Lieblingsautor umschalten">
            ${author.is_favorite ? "⭐" : "☆"}
          </button>
        </div>
      `;

      item.querySelector(".lt-author-item__rating").appendChild(starsEl);

      item.querySelector(".lt-author-item__name").addEventListener("click", () => {
        this._switchToTab("tab-books");

        this.$$(".lt-chip").forEach((chip) => {
          chip.classList.toggle("lt-chip--active", chip.dataset.filter === "all");
        });
        this._currentFilter = "all";

        const searchInput = this.$("#books-search-input");
        if (searchInput) {
          searchInput.value = author.name;
        }
        this._currentSearchQuery = author.name;

        this._loadBooks();
      });

      item.querySelector(".lt-fav-btn").addEventListener("click", async () => {
        const newFav = !author.is_favorite;
        try {
          await this._hass.callWS({
            type: "library_tracker/authors/set_favorite",
            author_id: author.id,
            is_favorite: newFav,
          });
          this._showToast(newFav ? `${author.name} als Lieblingsautor markiert.` : `${author.name} nicht mehr als Lieblingsautor markiert.`);
          this._loadAuthors();
        } catch (err) {
          this._showToast("Fehler beim Ändern des Favoritenstatus: " + (err.message || err), true);
        }
      });

      container.appendChild(item);
    });
  }

  _openBookDialog(book = null) {
    const dialog = this.$("#book-dialog");
    const form = this.$("#book-form");
    const titleEl = this.$("#dialog-title");

    form.reset();

    const starsContainer = this.$("#form-rating-stars");
    starsContainer.innerHTML = "";
    const ratingValInput = this.$("#form-rating-val");

    let initialRating = book && book.rating ? book.rating : 0;
    ratingValInput.value = initialRating ? String(initialRating) : "";

    const interactiveStars = this._createStarRatingComponent(initialRating, (val) => {
      ratingValInput.value = val ? String(val) : "";
    }, true);
    starsContainer.appendChild(interactiveStars);

    const isbnInput = this.$("#form-isbn");

    if (book) {
      titleEl.textContent = "Buch bearbeiten";
      this.$("#form-book-id").value = book.id;
      this.$("#form-series-id").value = book.series_id || "";
      this.$("#form-series-order").value = book.series_order != null ? book.series_order : "";
      isbnInput.value = book.isbn || "";
      isbnInput.readOnly = true;
      this.$("#form-title").value = book.title || "";
      this.$("#form-author").value = book.author || "";
      this.$("#form-published-date").value = book.published_date || "";
      this.$("#form-cover-url").value = book.cover_url || "";
      this.$("#form-status").value = book.status || "ungelesen";
    } else {
      titleEl.textContent = "Buch hinzufügen";
      this.$("#form-book-id").value = "";
      this.$("#form-series-id").value = "";
      this.$("#form-series-order").value = "";
      isbnInput.readOnly = false;
      this.$("#form-status").value = "ungelesen";
    }

    dialog.showModal();
  }

  _closeBookDialog() {
    const dialog = this.$("#book-dialog");
    dialog.close();
  }

  _showConfirmDialog(message) {
    return new Promise((resolve) => {
      const dialog = this.$("#confirm-dialog");
      this.$("#confirm-dialog-message").textContent = message;

      const btnOk = this.$("#btn-confirm-ok");
      const btnCancel = this.$("#btn-confirm-cancel");

      const cleanup = (result) => {
        btnOk.removeEventListener("click", onOk);
        btnCancel.removeEventListener("click", onCancel);
        dialog.close();
        resolve(result);
      };
      const onOk = () => cleanup(true);
      const onCancel = () => cleanup(false);

      btnOk.addEventListener("click", onOk);
      btnCancel.addEventListener("click", onCancel);
      dialog.showModal();
    });
  }

  async _handleIsbnLookup(isbn) {
    if (!isbn) {
      this._showToast("Bitte eine ISBN eingeben.", true);
      return;
    }
    this._showToast("Suche Buch-Metadaten …");
    try {
      const meta = await this._hass.callWS({
        type: "library_tracker/lookup_isbn",
        isbn: isbn,
      });

      this._openBookDialog();
      this.$("#form-isbn").value = meta.isbn || isbn;
      this.$("#form-title").value = meta.title || "";
      this.$("#form-author").value = meta.author || "";
      this.$("#form-published-date").value = meta.published_date || "";
      this.$("#form-cover-url").value = meta.cover_url || "";
      this.$("#form-series-id").value = meta.series_id || "";
      this.$("#form-series-order").value = meta.series_order != null ? meta.series_order : "";
      this._showToast("Buchmetadaten gefunden!");
    } catch (err) {
      this._showToast("Keine Buchmetadaten gefunden: " + (err.message || err), true);
      this._openBookDialog();
      this.$("#form-isbn").value = isbn;
    }
  }

  _loadHtml5QrcodeScript() {
    if (window.Html5Qrcode) {
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "/api/library_tracker/panel/html5-qrcode.min.js";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Fehler beim Laden von html5-qrcode.min.js"));
      document.head.appendChild(script);
    });
  }

  async _startScanner() {
    const errorEl = this.$("#scanner-error");
    errorEl.hidden = true;
    errorEl.textContent = "";

    try {
      await this._loadHtml5QrcodeScript();
    } catch (err) {
      errorEl.textContent = "Scanner-Bibliothek nicht geladen.";
      errorEl.hidden = false;
      return;
    }

    if (!this._html5QrCode) {
      this._html5QrCode = new window.Html5Qrcode("qr-reader");
    }

    const config = { fps: 10, qrbox: { width: 250, height: 150 } };

    this._html5QrCode
      .start(
        { facingMode: "environment" },
        config,
        (decodedText) => {
          this._showToast(`Barcode erkannt: ${decodedText}`);
          this._handleIsbnLookup(decodedText.trim());
          setTimeout(() => this._stopScanner(), 0);
        },
        () => {}
      )
      .then(() => {
        this.$("#btn-start-scanner").disabled = true;
        this.$("#btn-stop-scanner").disabled = false;
      })
      .catch((err) => {
        let msg = "Kamerazugriff fehlgeschlagen.";
        if (err && err.toString().includes("NotAllowedError")) {
          msg = "Kamerazugriff wurde im Browser verweigert. Bitte Berechtigung erteilen.";
        } else if (err && err.toString().includes("NotFoundError")) {
          msg = "Keine geeignete Kamera gefunden.";
        } else if (err) {
          msg += " (" + err + ")";
        }
        errorEl.textContent = msg;
        errorEl.hidden = false;
      });
  }

  _stopScanner() {
    if (this._html5QrCode && this._html5QrCode.isScanning) {
      try {
        this._html5QrCode
          .stop()
          .then(() => {
            if (this.$("#btn-start-scanner")) {
              this.$("#btn-start-scanner").disabled = false;
            }
            if (this.$("#btn-stop-scanner")) {
              this.$("#btn-stop-scanner").disabled = true;
            }
          })
          .catch((err) => console.error("Error stopping scanner", err));
      } catch (err) {
        console.error("Error stopping scanner (sync)", err);
      }
    }
  }

  _escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  _switchToTab(tabId) {
    this.$$(".lt-nav__btn").forEach((b) => {
      b.classList.toggle("lt-nav__btn--active", b.dataset.tab === tabId);
    });
    this.$$(".lt-tab-content").forEach((tab) => {
      tab.hidden = tab.id !== tabId;
    });
    if (tabId !== "tab-scanner") {
      this._stopScanner();
    }
  }

  _attachEventListeners() {
    // Settings Dialog
    const settingsDialog = this.$("#settings-dialog");
    const btnOpenSettings = this.$("#btn-open-settings");
    if (btnOpenSettings) {
      btnOpenSettings.addEventListener("click", () => {
        const settings = this._loadSettings();
        this.$("#settings-title").value = settings.title || "";
        this.$("#settings-theme").value = settings.theme || "system";
        this.$("#settings-columns").value = settings.columns || "auto";
        settingsDialog.showModal();
      });
    }

    const btnCloseSettings = this.$("#btn-close-settings");
    if (btnCloseSettings) {
      btnCloseSettings.addEventListener("click", () => settingsDialog.close());
    }

    const settingsForm = this.$("#settings-form");
    if (settingsForm) {
      settingsForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const settings = {
          title: this.$("#settings-title").value.trim(),
          theme: this.$("#settings-theme").value,
          columns: this.$("#settings-columns").value,
        };
        this._saveSettings(settings);
        this._applySettings(settings);
        settingsDialog.close();
        this._showToast("Einstellungen gespeichert.");
      });
    }

    const btnSettingsReset = this.$("#btn-settings-reset");
    if (btnSettingsReset) {
      btnSettingsReset.addEventListener("click", () => {
        this._saveSettings({});
        this._applySettings({});
        this.$("#settings-title").value = "";
        this.$("#settings-theme").value = "system";
        this.$("#settings-columns").value = "auto";
        this._showToast("Einstellungen zurückgesetzt.");
      });
    }

    // Navigation Tabs
    const navBtns = this.$$(".lt-nav__btn");
    navBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        this._switchToTab(btn.dataset.tab);
      });
    });

    // Filter Chips
    const filterChips = this.$$(".lt-chip");
    filterChips.forEach((chip) => {
      chip.addEventListener("click", () => {
        filterChips.forEach((c) => c.classList.remove("lt-chip--active"));
        chip.classList.add("lt-chip--active");
        this._currentFilter = chip.dataset.filter;
        this._currentSeriesFilterId = null;
        this._loadBooks();
      });
    });

    // Clear Series Filter Button
    const btnClearSeriesFilter = this.$("#btn-clear-series-filter");
    if (btnClearSeriesFilter) {
      btnClearSeriesFilter.addEventListener("click", () => {
        this._currentSeriesFilterId = null;
        this._loadBooks();
      });
    }

    // Free-text Search
    const searchInput = this.$("#books-search-input");
    if (searchInput) {
      searchInput.addEventListener("input", () => {
        this._currentSearchQuery = searchInput.value;
        this._applySearchFilterAndRender();
      });
    }

    // Dialog Trigger & Actions
    this.$("#btn-open-add-dialog").addEventListener("click", () => this._openBookDialog());
    this.$("#btn-close-dialog").addEventListener("click", () => this._closeBookDialog());
    this.$("#btn-cancel-dialog").addEventListener("click", () => this._closeBookDialog());

    // Form Submission (Add or Edit)
    this.$("#book-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const bookId = this.$("#form-book-id").value;
      const isbn = this.$("#form-isbn").value.trim();
      const title = this.$("#form-title").value.trim();
      const author = this.$("#form-author").value.trim();
      const publishedDate = this.$("#form-published-date").value.trim();
      const coverUrl = this.$("#form-cover-url").value.trim();
      const status = this.$("#form-status").value;
      const ratingStr = this.$("#form-rating-val").value;
      const rating = ratingStr ? parseInt(ratingStr, 10) : null;
      const seriesId = this.$("#form-series-id").value.trim() || null;
      const seriesOrderStr = this.$("#form-series-order").value.trim();
      const seriesOrder = seriesOrderStr ? parseInt(seriesOrderStr, 10) : null;

      if (!title || !author || (!bookId && !isbn)) {
        this._showToast("Titel, Autor und ISBN dürfen nicht leer sein.", true);
        return;
      }

      try {
        if (bookId) {
          const msg = {
            type: "library_tracker/books/update",
            book_id: parseInt(bookId, 10),
            title,
            author,
            published_date: publishedDate,
            cover_url: coverUrl,
            status,
            rating: rating,
          };
          await this._hass.callWS(msg);
          this._showToast("Buch aktualisiert.");
        } else {
          const msg = {
            type: "library_tracker/books/add",
            isbn,
            title,
            author,
            published_date: publishedDate,
            cover_url: coverUrl,
            status,
            rating: rating,
            series_id: seriesId,
            series_order: seriesOrder,
          };
          await this._hass.callWS(msg);
          this._showToast("Buch hinzugefügt.");
        }
        this._closeBookDialog();
        this._loadBooks();
        this._loadAuthors();
      } catch (err) {
        this._showToast("Fehler beim Speichern: " + (err.message || err), true);
      }
    });

    // Scanner Controls
    this.$("#btn-start-scanner").addEventListener("click", () => this._startScanner());
    this.$("#btn-stop-scanner").addEventListener("click", () => this._stopScanner());

    // Manual ISBN Lookup
    this.$("#btn-manual-lookup").addEventListener("click", () => {
      const isbn = this.$("#manual-isbn-input").value.trim();
      this._handleIsbnLookup(isbn);
    });
  }
}

customElements.define("library-tracker-panel", LibraryTrackerPanel);
