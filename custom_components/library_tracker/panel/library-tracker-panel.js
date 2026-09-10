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
    if (this._hass && !this._initialized) {
      this._init();
    }
  }

  disconnectedCallback() {
    this._stopScanner();
  }

  // html5-qrcode looks up its target element via the *global*
  // document.getElementById("qr-reader") internally and cannot see into
  // our shadow root. Rather than permanently replacing
  // document.getElementById for the whole HA frontend (which would risk
  // silently redirecting unrelated lookups from other panels/cards into
  // our shadow root), patch it only transiently, only for that one exact
  // id, and only while an html5-qrcode call is actually running.
  _withPatchedGetElementById(fn) {
    const origGet = document.getElementById.bind(document);
    const self = this;
    document.getElementById = function (id) {
      if (id === "qr-reader" && self.shadowRoot) {
        const el = self.shadowRoot.getElementById(id);
        if (el) return el;
      }
      return origGet(id);
    };
    const restore = () => {
      document.getElementById = origGet;
    };
    try {
      const result = fn();
      if (result && typeof result.finally === "function") {
        return result.finally(restore);
      }
      restore();
      return result;
    } catch (err) {
      restore();
      throw err;
    }
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
      <link rel="stylesheet" href="/library_tracker_panel/style.css" />
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

            <div id="series-filter-banner" class="lt-alert lt-alert--info lt-series-filter-banner" hidden>
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

      <!-- BOOK DETAIL DIALOG -->
      <div id="book-detail-dialog" class="lt-dialog-overlay" hidden>
        <div class="lt-dialog__content lt-book-detail">
          <div class="lt-dialog__header">
            <h3>Buch-Details</h3>
            <button id="btn-close-detail-dialog" class="lt-dialog__close">&times;</button>
          </div>
          <div class="lt-book-detail__body">
            <div id="detail-cover-container" class="lt-book-detail__cover-wrapper"></div>
            <div class="lt-book-detail__info">
              <h3 id="detail-title" class="lt-book-detail__title"></h3>
              <p id="detail-author" class="lt-book-detail__author"></p>
              <div class="lt-book-detail__meta">
                <span id="detail-status" class="lt-badge"></span>
                <span id="detail-published-date"></span>
              </div>
              <div id="detail-series-container"></div>
              <div class="lt-book-detail__rating">
                <span class="lt-book-detail__label">Bewertung:</span>
                <div id="detail-rating-stars"></div>
              </div>
            </div>
          </div>
          <div class="lt-book-detail__actions">
            <button id="btn-detail-mark-read" class="lt-btn lt-btn--secondary">✓ Gelesen</button>
            <button id="btn-detail-edit" class="lt-btn lt-btn--primary">Bearbeiten</button>
            <button id="btn-detail-delete" class="lt-btn lt-btn--danger">Löschen</button>
          </div>
        </div>
      </div>

      <!-- MODAL / DIALOG: Add & Edit Book
           Plain <div> + [hidden], not <dialog>/showModal(): <dialog> inside
           a shadow root has real, documented cross-browser bugs (Chromium
           #3601/#827397) where ::backdrop and top-layer promotion don't
           render — confirmed on Android WebView (HA Companion App), where
           the dialog rendered inline with no backdrop instead of as a
           centered modal. A manually positioned overlay works identically
           everywhere. -->
      <div id="book-dialog" class="lt-dialog-overlay" hidden>
        <div class="lt-dialog__content">
          <div class="lt-dialog__header">
            <h3 id="dialog-title">Buch hinzufügen</h3>
            <button id="btn-close-dialog" class="lt-dialog__close">&times;</button>
          </div>
          <form id="book-form" class="lt-form">
            <input type="hidden" id="form-book-id" value="" />
            <input type="hidden" id="form-series-id" value="" />
            <input type="hidden" id="form-series-order" value="" />

            <div class="lt-form__group" id="form-text-search-group">
              <label for="form-text-search">Freitextsuche (Google Books)</label>
              <div class="lt-search-box" style="max-width: 100%;">
                <input type="text" id="form-text-search" placeholder="Titel und/oder Autor eingeben" />
                <button type="button" id="btn-text-search" class="lt-btn lt-btn--primary">Suchen</button>
              </div>
            </div>

            <div id="text-search-results" class="lt-search-results" hidden></div>

            <div class="lt-form__group">
              <label for="form-isbn">ISBN *</label>
              <input type="text" id="form-isbn" placeholder="z. B. 9783453318113" />
            </div>

            <div class="lt-form__group">
              <label for="form-title">Titel *</label>
              <input type="text" id="form-title" placeholder="Buchtitel" />
            </div>

            <div class="lt-form__group">
              <label for="form-author">Autor *</label>
              <input type="text" id="form-author" placeholder="Autor Name" />
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
              <select id="form-status">
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
      </div>

      <!-- CONFIRM DIALOG -->
      <div id="confirm-dialog" class="lt-dialog-overlay" hidden>
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
      </div>

      <!-- SETTINGS DIALOG -->
      <div id="settings-dialog" class="lt-dialog-overlay" hidden>
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
      </div>

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

    // Scoped to :host only — this used to also mirror onto
    // document.documentElement when the panel ran inside its own iframe
    // document. Now that the panel is a web component in HA's real
    // top-level document, that would leak our private per-device theme
    // setting onto HA's actual <html> element. :host[data-theme=...] in
    // style.css already covers the shadow-scoped styling.
    if (settings.theme === "light" || settings.theme === "dark") {
      this.dataset.theme = settings.theme;
    } else {
      delete this.dataset.theme;
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

      card.innerHTML = `
        ${coverHtml}
        <div class="lt-book-card__content">
          <h4 class="lt-book-card__title" title="${this._escapeHtml(book.title)}">${this._escapeHtml(book.title)}</h4>
          <p class="lt-book-card__author">${this._escapeHtml(book.author)}</p>
        </div>
      `;

      card.addEventListener("click", () => {
        this._openBookDetailDialog(book);
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

  _openBookDetailDialog(book) {
    const dialog = this.$("#book-detail-dialog");
    if (!dialog) return;

    const coverContainer = this.$("#detail-cover-container");
    if (coverContainer) {
      if (book.cover_url) {
        coverContainer.innerHTML = `<img src="${this._escapeHtml(book.cover_url)}" class="lt-book-detail__cover-img" alt="Cover" />`;
      } else {
        coverContainer.innerHTML = `<div class="lt-book-detail__cover-placeholder">📖</div>`;
      }
    }

    const titleEl = this.$("#detail-title");
    if (titleEl) titleEl.textContent = book.title || "";

    const authorEl = this.$("#detail-author");
    if (authorEl) authorEl.textContent = book.author || "";

    const statusEl = this.$("#detail-status");
    if (statusEl) {
      statusEl.className = `lt-badge lt-badge--${this._escapeHtml(book.status || "")}`;
      statusEl.textContent = book.status || "";
    }

    const pubDateEl = this.$("#detail-published-date");
    if (pubDateEl) {
      pubDateEl.textContent = book.published_date ? ` • ${book.published_date}` : "";
    }

    const seriesContainer = this.$("#detail-series-container");
    if (seriesContainer) {
      seriesContainer.innerHTML = "";
      if (book.series_id) {
        const label = book.series_order
          ? `Teil ${this._escapeHtml(book.series_order)} der Reihe`
          : "Teil einer Reihe";
        const seriesBadge = document.createElement("span");
        seriesBadge.className = "lt-badge lt-badge--series btn-series-link";
        seriesBadge.title = "Alle Bücher dieser Reihe anzeigen";
        seriesBadge.textContent = `📚 ${label}`;
        seriesBadge.addEventListener("click", () => {
          this._currentSeriesFilterId = book.series_id;
          this._closeBookDetailDialog();
          this._loadBooks();
        });
        seriesContainer.appendChild(seriesBadge);
      } else {
        const btnAi = document.createElement("button");
        btnAi.id = "btn-ai-series-lookup";
        btnAi.className = "lt-btn lt-btn--secondary lt-btn--sm";
        btnAi.textContent = "✨ KI-Serienvorschlag";

        const aiResultContainer = document.createElement("div");
        aiResultContainer.id = "detail-ai-series-result";

        btnAi.addEventListener("click", async () => {
          btnAi.disabled = true;
          btnAi.textContent = "Analysiere Buchreihe mit KI…";
          aiResultContainer.className = "lt-ai-series-result";
          aiResultContainer.innerHTML = `<div class="lt-ai-series-loading">🤖 KI analysiert Serienzugehörigkeit…</div>`;

          try {
            const res = await this._hass.callWS({
              type: "library_tracker/books/ai_series_lookup",
              book_id: book.id,
            });

            btnAi.textContent = "✨ KI-Serienvorschlag";
            btnAi.disabled = false;

            let html = `<div class="lt-badge lt-badge--ai">✨ KI-Vorschlag, ungeprüft</div>`;

            if (!res || !res.is_series || !res.books || res.books.length === 0) {
              html += `<p class="lt-ai-series-info">Keine Serienzugehörigkeit von KI erkannt.</p>`;
            } else {
              if (res.series_name) {
                html += `<div class="lt-ai-series-title">Reihe: ${this._escapeHtml(res.series_name)}</div>`;
              }
              html += `<ul class="lt-ai-series-list">`;
              res.books.forEach((b) => {
                const bTitle = b.title || "Unbekannter Titel";
                const bOrder = b.order != null ? `${b.order}. ` : "";
                const inLib = this._currentBooksRaw.some((cb) => {
                  const t1 = (cb.title || "").toLowerCase().trim();
                  const t2 = bTitle.toLowerCase().trim();
                  return t1 === t2 || (t1.length > 3 && t2.length > 3 && (t1.includes(t2) || t2.includes(t1)));
                });

                const badgeHtml = inLib
                  ? `<span class="lt-ai-in-lib-tag">✓ bereits in der Bibliothek</span>`
                  : "";

                html += `<li><span class="lt-ai-book-item">${this._escapeHtml(bOrder)}${this._escapeHtml(bTitle)}</span> ${badgeHtml}</li>`;
              });
              html += `</ul>`;
            }

            aiResultContainer.innerHTML = html;
          } catch (err) {
            btnAi.textContent = "✨ KI-Serienvorschlag";
            btnAi.disabled = false;
            aiResultContainer.innerHTML = `<div class="lt-alert lt-alert--error" style="margin-top: 8px; font-size: 12px;">Kein KI-Anbieter konfiguriert oder KI-Anfrage fehlgeschlagen (${this._escapeHtml(err.message || err)}).</div>`;
          }
        });

        seriesContainer.appendChild(btnAi);
        seriesContainer.appendChild(aiResultContainer);
      }
    }

    const starsContainer = this.$("#detail-rating-stars");
    if (starsContainer) {
      starsContainer.innerHTML = "";
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
          this._openBookDetailDialog(book);
          this._showToast("Fehler beim Aktualisieren der Bewertung: " + (err.message || err), true);
        }
      });
      starsContainer.appendChild(starsEl);
    }

    const btnMarkRead = this.$("#btn-detail-mark-read");
    if (btnMarkRead) {
      btnMarkRead.hidden = book.status === "gelesen";
      btnMarkRead.onclick = async () => {
        try {
          await this._hass.callWS({
            type: "library_tracker/books/update",
            book_id: book.id,
            status: "gelesen",
          });
          this._showToast(`"${book.title}" als gelesen markiert.`);
          this._closeBookDetailDialog();
          this._loadBooks();
        } catch (err) {
          this._showToast("Fehler beim Aktualisieren: " + (err.message || err), true);
        }
      };
    }

    const btnEdit = this.$("#btn-detail-edit");
    if (btnEdit) {
      btnEdit.onclick = () => {
        this._closeBookDetailDialog();
        this._openBookDialog(book);
      };
    }

    const btnDelete = this.$("#btn-detail-delete");
    if (btnDelete) {
      btnDelete.onclick = async () => {
        const confirmed = await this._showConfirmDialog(`Soll "${book.title}" wirklich gelöscht werden?`);
        if (confirmed) {
          try {
            await this._hass.callWS({
              type: "library_tracker/books/delete",
              book_id: book.id,
            });
            this._showToast("Buch gelöscht.");
            this._closeBookDetailDialog();
            this._loadBooks();
            this._loadAuthors();
          } catch (err) {
            this._showToast("Fehler beim Löschen: " + (err.message || err), true);
          }
        }
      };
    }

    dialog.hidden = false;
  }

  _closeBookDetailDialog() {
    const dialog = this.$("#book-detail-dialog");
    if (dialog) {
      dialog.hidden = true;
    }
  }

  _openBookDialog(book = null) {
    const dialog = this.$("#book-dialog");
    const form = this.$("#book-form");
    const titleEl = this.$("#dialog-title");

    form.reset();

    const textSearchInput = this.$("#form-text-search");
    if (textSearchInput) textSearchInput.value = "";

    const resultsContainer = this.$("#text-search-results");
    if (resultsContainer) {
      resultsContainer.hidden = true;
      resultsContainer.innerHTML = "";
    }

    const textSearchGroup = this.$("#form-text-search-group");
    if (textSearchGroup) {
      textSearchGroup.hidden = !!book;
    }

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

    dialog.hidden = false;
  }

  _closeBookDialog() {
    const dialog = this.$("#book-dialog");
    const textSearchInput = this.$("#form-text-search");
    if (textSearchInput) textSearchInput.value = "";

    const resultsContainer = this.$("#text-search-results");
    if (resultsContainer) {
      resultsContainer.hidden = true;
      resultsContainer.innerHTML = "";
    }

    dialog.hidden = true;
  }

  async _handleTextSearch() {
    const searchInput = this.$("#form-text-search");
    const resultsContainer = this.$("#text-search-results");
    if (!searchInput || !resultsContainer) return;

    const query = searchInput.value.trim();
    if (!query) {
      this._showToast("Bitte einen Suchbegriff eingeben.", true);
      return;
    }

    resultsContainer.innerHTML = '<div class="lt-search-results__empty">Suche nach Treffern …</div>';
    resultsContainer.hidden = false;

    try {
      const results = await this._hass.callWS({
        type: "library_tracker/books/search_text",
        query: query,
      });

      resultsContainer.innerHTML = "";
      if (!results || results.length === 0) {
        resultsContainer.innerHTML = '<div class="lt-search-results__empty">Keine Treffer gefunden, bitte manuell eingeben</div>';
        return;
      }

      results.forEach((item) => {
        const itemEl = document.createElement("div");
        itemEl.className = "lt-search-result-item";

        let coverHtml = item.cover_url
          ? `<img src="${this._escapeHtml(item.cover_url)}" class="lt-search-result-item__cover" alt="Cover" />`
          : `<div class="lt-search-result-item__cover">📖</div>`;

        let dateHtml = item.published_date
          ? `<span class="lt-search-result-item__date"> (${this._escapeHtml(item.published_date)})</span>`
          : "";

        itemEl.innerHTML = `
          ${coverHtml}
          <div class="lt-search-result-item__info">
            <div class="lt-search-result-item__title">${this._escapeHtml(item.title)}${dateHtml}</div>
            <div class="lt-search-result-item__author">${this._escapeHtml(item.author)}</div>
            ${item.isbn ? `<div class="lt-search-result-item__isbn">ISBN: ${this._escapeHtml(item.isbn)}</div>` : ""}
          </div>
          <button type="button" class="lt-btn lt-btn--secondary lt-btn--sm btn-select-result">Auswählen</button>
        `;

        itemEl.querySelector(".btn-select-result").addEventListener("click", () => {
          this.$("#form-title").value = item.title || "";
          this.$("#form-author").value = item.author || "";
          this.$("#form-isbn").value = item.isbn || "";
          this.$("#form-published-date").value = item.published_date || "";
          this.$("#form-cover-url").value = item.cover_url || "";
          this.$("#form-series-id").value = item.series_id || "";
          this.$("#form-series-order").value = item.series_order != null ? item.series_order : "";

          resultsContainer.hidden = true;
          resultsContainer.innerHTML = "";
          this._showToast("Metadaten übernommen.");
        });

        resultsContainer.appendChild(itemEl);
      });
    } catch (err) {
      resultsContainer.innerHTML = `<div class="lt-search-results__empty">Fehler bei der Suche: ${this._escapeHtml(err.message || err)}</div>`;
    }
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
        dialog.hidden = true;
        resolve(result);
      };
      const onOk = () => cleanup(true);
      const onCancel = () => cleanup(false);

      btnOk.addEventListener("click", onOk);
      btnCancel.addEventListener("click", onCancel);
      dialog.hidden = false;
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
      script.src = "/library_tracker_panel/html5-qrcode.min.js";
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
      this._withPatchedGetElementById(() => {
        this._html5QrCode = new window.Html5Qrcode("qr-reader");
      });
    }

    const config = { fps: 10, qrbox: { width: 250, height: 150 } };

    this._withPatchedGetElementById(() =>
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
        })
    );
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
        settingsDialog.hidden = false;
      });
    }

    const btnCloseSettings = this.$("#btn-close-settings");
    if (btnCloseSettings) {
      btnCloseSettings.addEventListener("click", () => { settingsDialog.hidden = true; });
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
        settingsDialog.hidden = true;
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

    // Detail Dialog Trigger & Actions
    const btnCloseDetail = this.$("#btn-close-detail-dialog");
    if (btnCloseDetail) {
      btnCloseDetail.addEventListener("click", () => this._closeBookDetailDialog());
    }

    // Dialog Trigger & Actions
    this.$("#btn-open-add-dialog").addEventListener("click", () => this._openBookDialog());
    this.$("#btn-close-dialog").addEventListener("click", () => this._closeBookDialog());
    this.$("#btn-cancel-dialog").addEventListener("click", () => this._closeBookDialog());

    const btnTextSearch = this.$("#btn-text-search");
    if (btnTextSearch) {
      btnTextSearch.addEventListener("click", () => this._handleTextSearch());
    }

    const textSearchInput = this.$("#form-text-search");
    if (textSearchInput) {
      textSearchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this._handleTextSearch();
        }
      });
    }

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
