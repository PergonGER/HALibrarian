// Library Tracker – Frontend Application (Session 3)
// Communicates with HA WebSocket API via ha-client.js

console.info("[library_tracker] Loading panel application...");

let haClient = null;
let currentFilter = "all";
let currentSearchQuery = "";
let html5QrCode = null;
let currentBooksRaw = []; // status-filtered books as returned by the backend
let currentBooks = []; // currentBooksRaw further filtered by the search box, i.e. what's actually rendered
let currentAuthors = [];

// Local (per-device) Settings: panel title override + theme, stored in
// localStorage - not synced across devices/users, same scope as the
// access token. Deliberately applied outside of any HA-connection flow
// so the title/theme are correct even before the user logs in.
const SETTINGS_STORAGE_KEY = "library_tracker_settings";

function loadSettings() {
  try {
    const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (err) {
    return {};
  }
}

function saveSettings(settings) {
  try {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
  } catch (err) {
    console.warn("[library_tracker] Could not persist settings:", err);
  }
}

function applySettings(settings) {
  const titleEl = document.querySelector(".lt-header__title");
  if (titleEl) {
    titleEl.textContent = settings.title && settings.title.trim() ? settings.title.trim() : "Library Tracker";
  }

  if (settings.theme === "light" || settings.theme === "dark") {
    document.documentElement.dataset.theme = settings.theme;
  } else {
    delete document.documentElement.dataset.theme;
  }
}

// Toast Notifications
function showToast(message, isError = false) {
  const container = document.getElementById("toast-container");
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

// Interactive Star Component Generator
function createStarRatingComponent(rating, onRatingChange, interactive = true) {
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
        const newVal = currentVal === i ? null : i; // toggle off if clicking same rating
        currentVal = newVal || 0;
        updateStars(container, currentVal);
        if (onRatingChange) onRatingChange(newVal);
      });

      star.addEventListener("mouseenter", () => {
        updateStars(container, i);
      });

      container.addEventListener("mouseleave", () => {
        updateStars(container, currentVal);
      });
    }

    container.appendChild(star);
  }

  return container;
}

function updateStars(container, val) {
  const stars = container.querySelectorAll(".lt-star");
  stars.forEach((star, idx) => {
    if (idx < val) {
      star.classList.add("lt-star--filled");
    } else {
      star.classList.remove("lt-star--filled");
    }
  });
}

// Connection Management
function setConnectionStatus(text, ok) {
  const el = document.getElementById("connection-status");
  if (el) {
    el.textContent = text;
    el.style.color = ok ? "var(--lt-success)" : "var(--lt-error)";
  }
}

async function connectWithToken(token) {
  setConnectionStatus("Verbinde mit Home Assistant …", true);
  try {
    haClient = await window.LibraryTrackerHA.connect(token);
    window.LibraryTrackerHA.storeToken(token);
    setConnectionStatus("Verbunden.", true);

    document.getElementById("auth-section").hidden = true;
    document.getElementById("main-nav").hidden = false;
    document.getElementById("dashboard-container").hidden = false;

    // Initial Data Fetch
    loadBooks();
    loadAuthors();
    loadVersion();
  } catch (err) {
    haClient = null;
    window.LibraryTrackerHA.clearStoredToken();
    setConnectionStatus("Verbindung fehlgeschlagen: " + (err.message || err), false);
  }
}

// Data Fetching & Rendering
async function loadBooks() {
  if (!haClient) return;
  try {
    const msg = { type: "library_tracker/books/list" };
    if (currentFilter !== "all") {
      msg.status = currentFilter;
    }
    currentBooksRaw = await haClient.callWS(msg);
    applySearchFilterAndRender();
  } catch (err) {
    showToast("Fehler beim Laden der Bücher: " + (err.message || err), true);
  }
}

// Free-text search across all displayed fields, applied client-side on top
// of the status filter already applied by the backend query above - avoids
// a WS round-trip on every keystroke.
function applySearchFilterAndRender() {
  const query = currentSearchQuery.trim().toLowerCase();
  const filtered = !query
    ? currentBooksRaw
    : currentBooksRaw.filter((book) => {
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
  currentBooks = filtered;
  renderBooks(filtered);
}

function renderBooks(books) {
  const container = document.getElementById("books-list");
  if (!container) return;
  container.innerHTML = "";

  if (!books || books.length === 0) {
    container.innerHTML = `<div class="lt-card" style="grid-column: 1 / -1; text-align: center; color: var(--lt-text-secondary);">Keine Bücher in dieser Ansicht vorhanden.</div>`;
    return;
  }

  books.forEach((book) => {
    const card = document.createElement("div");
    card.className = "lt-book-card";

    // Cover
    let coverHtml;
    if (book.cover_url) {
      coverHtml = `<img src="${escapeHtml(book.cover_url)}" class="lt-book-card__cover" alt="Cover" />`;
    } else {
      coverHtml = `<div class="lt-book-card__cover">📖</div>`;
    }

    // Interactive Star Rating for Card
    const starsEl = createStarRatingComponent(book.rating, async (newRating) => {
      // Optimistic UI update & rollback on error
      const prevRating = book.rating;
      book.rating = newRating;
      try {
        await haClient.callWS({
          type: "library_tracker/books/update",
          book_id: book.id,
          rating: newRating,
        });
        showToast("Bewertung aktualisiert.");
      } catch (err) {
        book.rating = prevRating;
        renderBooks(currentBooks); // rollback
        showToast("Fehler beim Aktualisieren der Bewertung: " + (err.message || err), true);
      }
    });

    card.innerHTML = `
      ${coverHtml}
      <div class="lt-book-card__content">
        <div>
          <h4 class="lt-book-card__title" title="${escapeHtml(book.title)}">${escapeHtml(book.title)}</h4>
          <p class="lt-book-card__author">${escapeHtml(book.author)}</p>
          <p class="lt-book-card__meta">
            <span class="lt-badge lt-badge--${escapeHtml(book.status)}">${escapeHtml(book.status)}</span>
            ${book.published_date ? ` • ${escapeHtml(book.published_date)}` : ""}
          </p>
        </div>
        <div class="lt-book-card__rating-container"></div>
        <div class="lt-book-card__actions">
          ${book.status !== "gelesen" ? `<button class="lt-btn lt-btn--secondary lt-btn--sm btn-mark-read">✓ Gelesen</button>` : ""}
          <button class="lt-btn lt-btn--secondary lt-btn--sm btn-edit-book">Bearbeiten</button>
          <button class="lt-btn lt-btn--danger lt-btn--sm btn-delete-book">Löschen</button>
        </div>
      </div>
    `;

    card.querySelector(".lt-book-card__rating-container").appendChild(starsEl);

    // Mark as read (quick status toggle, skips the edit dialog)
    const markReadBtn = card.querySelector(".btn-mark-read");
    if (markReadBtn) {
      markReadBtn.addEventListener("click", async () => {
        try {
          await haClient.callWS({
            type: "library_tracker/books/update",
            book_id: book.id,
            status: "gelesen",
          });
          showToast(`"${book.title}" als gelesen markiert.`);
          loadBooks();
        } catch (err) {
          showToast("Fehler beim Aktualisieren: " + (err.message || err), true);
        }
      });
    }

    // Edit Event
    card.querySelector(".btn-edit-book").addEventListener("click", () => {
      openBookDialog(book);
    });

    // Delete Event
    card.querySelector(".btn-delete-book").addEventListener("click", async () => {
      const confirmed = await showConfirmDialog(`Soll "${book.title}" wirklich gelöscht werden?`);
      if (confirmed) {
        try {
          await haClient.callWS({
            type: "library_tracker/books/delete",
            book_id: book.id,
          });
          showToast("Buch gelöscht.");
          loadBooks();
          loadAuthors();
        } catch (err) {
          showToast("Fehler beim Löschen: " + (err.message || err), true);
        }
      }
    });

    container.appendChild(card);
  });
}

async function loadAuthors() {
  if (!haClient) return;
  try {
    const authors = await haClient.callWS({ type: "library_tracker/authors/list" });
    currentAuthors = authors;
    renderAuthors(authors);
  } catch (err) {
    showToast("Fehler beim Laden der Autoren: " + (err.message || err), true);
  }
}

// Shows the installed integration version (read from manifest.json on the
// backend) in the header, so it's obvious at a glance which version is
// running - useful since HACS updates aren't always picked up instantly.
async function loadVersion() {
  if (!haClient) return;
  const badge = document.getElementById("version-badge");
  if (!badge) return;
  try {
    const result = await haClient.callWS({ type: "library_tracker/version" });
    badge.textContent = `v${result.version}`;
    badge.hidden = false;
  } catch (err) {
    // Non-critical - just don't show the badge.
    console.warn("[library_tracker] Could not load version:", err);
  }
}

function renderAuthors(authors) {
  const container = document.getElementById("authors-list");
  if (!container) return;
  container.innerHTML = "";

  if (!authors || authors.length === 0) {
    container.innerHTML = `<p style="color: var(--lt-text-secondary);">Noch keine Autoren erfasst.</p>`;
    return;
  }

  authors.forEach((author) => {
    const item = document.createElement("div");
    item.className = "lt-author-item";

    const starsEl = createStarRatingComponent(author.rating, async (newRating) => {
      const prevRating = author.rating;
      author.rating = newRating;
      try {
        await haClient.callWS({
          type: "library_tracker/authors/set_rating",
          author_id: author.id,
          rating: newRating,
        });
        showToast("Autoren-Bewertung aktualisiert.");
      } catch (err) {
        author.rating = prevRating;
        renderAuthors(currentAuthors); // rollback
        showToast("Fehler beim Aktualisieren der Autoren-Bewertung: " + (err.message || err), true);
      }
    });

    item.innerHTML = `
      <span class="lt-author-item__name lt-author-item__name--clickable" title="Bücher von ${escapeHtml(author.name)} anzeigen">${escapeHtml(author.name)}</span>
      <div class="lt-author-item__actions">
        <div class="lt-author-item__rating"></div>
        <button class="lt-fav-btn" title="Lieblingsautor umschalten">
          ${author.is_favorite ? "⭐" : "☆"}
        </button>
      </div>
    `;

    item.querySelector(".lt-author-item__rating").appendChild(starsEl);

    // Clicking the name jumps to the Bücher tab, filtered to this author
    // (reuses the existing free-text search, reset to "Alle" status so
    // every book of theirs shows regardless of read status).
    item.querySelector(".lt-author-item__name").addEventListener("click", () => {
      switchToTab("tab-books");

      document.querySelectorAll(".lt-chip").forEach((chip) => {
        chip.classList.toggle("lt-chip--active", chip.dataset.filter === "all");
      });
      currentFilter = "all";

      const searchInput = document.getElementById("books-search-input");
      if (searchInput) {
        searchInput.value = author.name;
      }
      currentSearchQuery = author.name;

      loadBooks();
    });

    item.querySelector(".lt-fav-btn").addEventListener("click", async () => {
      const newFav = !author.is_favorite;
      try {
        await haClient.callWS({
          type: "library_tracker/authors/set_favorite",
          author_id: author.id,
          is_favorite: newFav,
        });
        showToast(newFav ? `${author.name} als Lieblingsautor markiert.` : `${author.name} nicht mehr als Lieblingsautor markiert.`);
        loadAuthors();
      } catch (err) {
        showToast("Fehler beim Ändern des Favoritenstatus: " + (err.message || err), true);
      }
    });

    container.appendChild(item);
  });
}

// Dialog / Form Functions
function openBookDialog(book = null) {
  const dialog = document.getElementById("book-dialog");
  const form = document.getElementById("book-form");
  const titleEl = document.getElementById("dialog-title");

  form.reset();

  // Setup Form Interactive Stars
  const starsContainer = document.getElementById("form-rating-stars");
  starsContainer.innerHTML = "";
  const ratingValInput = document.getElementById("form-rating-val");

  let initialRating = book && book.rating ? book.rating : 0;
  ratingValInput.value = initialRating ? String(initialRating) : "";

  const interactiveStars = createStarRatingComponent(initialRating, (val) => {
    ratingValInput.value = val ? String(val) : "";
  }, true);
  starsContainer.appendChild(interactiveStars);

  const isbnInput = document.getElementById("form-isbn");

  if (book) {
    titleEl.textContent = "Buch bearbeiten";
    document.getElementById("form-book-id").value = book.id;
    isbnInput.value = book.isbn || "";
    // ISBN is immutable once a book exists - library_tracker/books/update
    // doesn't accept an isbn field, so editing it here would silently be
    // discarded. Disable it rather than imply the change would save.
    isbnInput.readOnly = true;
    document.getElementById("form-title").value = book.title || "";
    document.getElementById("form-author").value = book.author || "";
    document.getElementById("form-published-date").value = book.published_date || "";
    document.getElementById("form-cover-url").value = book.cover_url || "";
    document.getElementById("form-status").value = book.status || "ungelesen";
  } else {
    titleEl.textContent = "Buch hinzufügen";
    document.getElementById("form-book-id").value = "";
    isbnInput.readOnly = false;
    document.getElementById("form-status").value = "ungelesen";
  }

  dialog.showModal();
}

function closeBookDialog() {
  const dialog = document.getElementById("book-dialog");
  dialog.close();
}

// In-app replacement for window.confirm(): the HA Companion App's WebView
// does not implement JS dialogs (confirm/alert/prompt) unless the host app
// explicitly adds a handler for them, which it doesn't here - confirm()
// silently does nothing there. This uses the same <dialog> element pattern
// as the book-edit dialog instead, which works everywhere.
function showConfirmDialog(message) {
  return new Promise((resolve) => {
    const dialog = document.getElementById("confirm-dialog");
    document.getElementById("confirm-dialog-message").textContent = message;

    const btnOk = document.getElementById("btn-confirm-ok");
    const btnCancel = document.getElementById("btn-confirm-cancel");

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

// ISBN Lookup & Autofill
async function handleIsbnLookup(isbn) {
  if (!isbn) {
    showToast("Bitte eine ISBN eingeben.", true);
    return;
  }
  showToast("Suche Buch-Metadaten …");
  try {
    const meta = await haClient.callWS({
      type: "library_tracker/lookup_isbn",
      isbn: isbn,
    });

    // Open add dialog prefilled with metadata
    openBookDialog();
    document.getElementById("form-isbn").value = meta.isbn || isbn;
    document.getElementById("form-title").value = meta.title || "";
    document.getElementById("form-author").value = meta.author || "";
    document.getElementById("form-published-date").value = meta.published_date || "";
    document.getElementById("form-cover-url").value = meta.cover_url || "";
    showToast("Buchmetadaten gefunden!");
  } catch (err) {
    showToast("Keine Buchmetadaten gefunden: " + (err.message || err), true);
    // Still open dialog with ISBN filled so user can manually enter title/author
    openBookDialog();
    document.getElementById("form-isbn").value = isbn;
  }
}

// Camera Scanner Setup
function startScanner() {
  const errorEl = document.getElementById("scanner-error");
  errorEl.hidden = true;
  errorEl.textContent = "";

  if (!window.Html5Qrcode) {
    errorEl.textContent = "Scanner-Bibliothek nicht geladen.";
    errorEl.hidden = false;
    return;
  }

  if (!html5QrCode) {
    html5QrCode = new window.Html5Qrcode("qr-reader");
  }

  const config = { fps: 10, qrbox: { width: 250, height: 150 } };

  html5QrCode
    .start(
      { facingMode: "environment" },
      config,
      (decodedText) => {
        // Successful scan. html5-qrcode throws if stop() is called
        // synchronously from inside this callback (it's still mid-frame) -
        // that exception aborted the callback before handleIsbnLookup ever
        // ran. Do the lookup first, defer stopping the scanner.
        showToast(`Barcode erkannt: ${decodedText}`);
        handleIsbnLookup(decodedText.trim());
        setTimeout(() => stopScanner(), 0);
      },
      (errorMessage) => {
        // parse errors occur constantly per frame, ignore
      }
    )
    .then(() => {
      document.getElementById("btn-start-scanner").disabled = true;
      document.getElementById("btn-stop-scanner").disabled = false;
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

function stopScanner() {
  if (html5QrCode && html5QrCode.isScanning) {
    try {
      html5QrCode
        .stop()
        .then(() => {
          document.getElementById("btn-start-scanner").disabled = false;
          document.getElementById("btn-stop-scanner").disabled = true;
        })
        .catch((err) => console.error("Error stopping scanner", err));
    } catch (err) {
      // html5-qrcode can throw synchronously (not just reject) if called
      // while the scanner is mid-transition - see mebjas/html5-qrcode#715.
      console.error("Error stopping scanner (sync)", err);
    }
  }
}

// Utility
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Switches the visible tab (also usable from outside the nav click
// handlers, e.g. clicking an author name to jump to their books).
function switchToTab(tabId) {
  document.querySelectorAll(".lt-nav__btn").forEach((b) => {
    b.classList.toggle("lt-nav__btn--active", b.dataset.tab === tabId);
  });
  document.querySelectorAll(".lt-tab-content").forEach((tab) => {
    tab.hidden = tab.id !== tabId;
  });
  if (tabId !== "tab-scanner") {
    stopScanner();
  }
}

// DOM Event Listeners Initialization
document.addEventListener("DOMContentLoaded", () => {
  // Apply saved title/theme immediately, independent of HA login state.
  applySettings(loadSettings());

  // Settings Dialog
  const settingsDialog = document.getElementById("settings-dialog");
  const btnOpenSettings = document.getElementById("btn-open-settings");
  if (btnOpenSettings) {
    btnOpenSettings.addEventListener("click", () => {
      const settings = loadSettings();
      document.getElementById("settings-title").value = settings.title || "";
      document.getElementById("settings-theme").value = settings.theme || "system";
      settingsDialog.showModal();
    });
  }

  const btnCloseSettings = document.getElementById("btn-close-settings");
  if (btnCloseSettings) {
    btnCloseSettings.addEventListener("click", () => settingsDialog.close());
  }

  const settingsForm = document.getElementById("settings-form");
  if (settingsForm) {
    settingsForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const settings = {
        title: document.getElementById("settings-title").value.trim(),
        theme: document.getElementById("settings-theme").value,
      };
      saveSettings(settings);
      applySettings(settings);
      settingsDialog.close();
      showToast("Einstellungen gespeichert.");
    });
  }

  const btnSettingsReset = document.getElementById("btn-settings-reset");
  if (btnSettingsReset) {
    btnSettingsReset.addEventListener("click", () => {
      saveSettings({});
      applySettings({});
      document.getElementById("settings-title").value = "";
      document.getElementById("settings-theme").value = "system";
      showToast("Einstellungen zurückgesetzt.");
    });
  }

  // Navigation Tabs
  const navBtns = document.querySelectorAll(".lt-nav__btn");
  navBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      switchToTab(btn.dataset.tab);
    });
  });

  // Filter Chips
  const filterChips = document.querySelectorAll(".lt-chip");
  filterChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      filterChips.forEach((c) => c.classList.remove("lt-chip--active"));
      chip.classList.add("lt-chip--active");
      currentFilter = chip.dataset.filter;
      loadBooks();
    });
  });

  // Free-text Search
  const searchInput = document.getElementById("books-search-input");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      currentSearchQuery = searchInput.value;
      applySearchFilterAndRender();
    });
  }

  // Auth Connect
  const btnConnect = document.getElementById("btn-connect");
  if (btnConnect) {
    btnConnect.addEventListener("click", () => {
      const token = document.getElementById("token-input").value.trim();
      if (!token) {
        setConnectionStatus("Bitte ein Access Token eingeben.", false);
        return;
      }
      connectWithToken(token);
    });
  }

  // Check stored token
  const storedToken = window.LibraryTrackerHA.getStoredToken();
  if (storedToken) {
    connectWithToken(storedToken);
  }

  // Dialog Trigger & Actions
  document.getElementById("btn-open-add-dialog").addEventListener("click", () => openBookDialog());
  document.getElementById("btn-close-dialog").addEventListener("click", closeBookDialog);
  document.getElementById("btn-cancel-dialog").addEventListener("click", closeBookDialog);

  // Form Submission (Add or Edit)
  document.getElementById("book-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const bookId = document.getElementById("form-book-id").value;
    const isbn = document.getElementById("form-isbn").value.trim();
    const title = document.getElementById("form-title").value.trim();
    const author = document.getElementById("form-author").value.trim();
    const publishedDate = document.getElementById("form-published-date").value.trim();
    const coverUrl = document.getElementById("form-cover-url").value.trim();
    const status = document.getElementById("form-status").value;
    const ratingStr = document.getElementById("form-rating-val").value;
    const rating = ratingStr ? parseInt(ratingStr, 10) : null;

    if (!title || !author || (!bookId && !isbn)) {
      showToast("Titel, Autor und ISBN dürfen nicht leer sein.", true);
      return;
    }

    try {
      if (bookId) {
        // Edit existing book
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
        await haClient.callWS(msg);
        showToast("Buch aktualisiert.");
      } else {
        // Add new book
        const msg = {
          type: "library_tracker/books/add",
          isbn,
          title,
          author,
          published_date: publishedDate,
          cover_url: coverUrl,
          status,
          rating: rating,
        };
        await haClient.callWS(msg);
        showToast("Buch hinzugefügt.");
      }
      closeBookDialog();
      loadBooks();
      loadAuthors();
    } catch (err) {
      showToast("Fehler beim Speichern: " + (err.message || err), true);
    }
  });

  // Scanner Controls
  document.getElementById("btn-start-scanner").addEventListener("click", startScanner);
  document.getElementById("btn-stop-scanner").addEventListener("click", stopScanner);

  // Manual ISBN Lookup
  document.getElementById("btn-manual-lookup").addEventListener("click", () => {
    const isbn = document.getElementById("manual-isbn-input").value.trim();
    handleIsbnLookup(isbn);
  });
});
