// HA Library Tracker – Panel JS (Session 2)
// Calls WebSocket API endpoints for testing

console.info("[library_tracker] Panel loaded with WebSocket test console.");

function getHass() {
  if (window.parent && window.parent.hass) {
    return window.parent.hass;
  }
  if (window.hass) {
    return window.hass;
  }
  return null;
}

function logOutput(data) {
  const outputEl = document.getElementById("ws-output");
  if (outputEl) {
    outputEl.textContent = typeof data === "object" ? JSON.stringify(data, null, 2) : String(data);
  }
}

async function callWS(msg) {
  const hass = getHass();
  if (!hass) {
    logOutput("Fehler: kein Home Assistant Object (parent.hass) gefunden. Panel läuft außerhalb von Home Assistant Dashboard.");
    return;
  }
  try {
    logOutput("Sende Command: " + JSON.stringify(msg));
    const result = await hass.callWS(msg);
    logOutput(result);
  } catch (err) {
    logOutput({ error: err });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // 1. ISBN Lookup
  const btnLookup = document.getElementById("btn-lookup");
  if (btnLookup) {
    btnLookup.addEventListener("click", () => {
      const isbn = document.getElementById("isbn-input").value.trim();
      if (!isbn) {
        logOutput("Bitte eine ISBN eingeben.");
        return;
      }
      callWS({ type: "library_tracker/lookup_isbn", isbn });
    });
  }

  // 2. Books List
  ["all", "gelesen", "ungelesen", "wunschliste"].forEach((status) => {
    const btn = document.getElementById(`btn-list-${status}`);
    if (btn) {
      btn.addEventListener("click", () => {
        const msg = { type: "library_tracker/books/list" };
        if (status !== "all") {
          msg.status = status;
        }
        callWS(msg);
      });
    }
  });

  // 3. Add Book
  const btnAdd = document.getElementById("btn-add-book");
  if (btnAdd) {
    btnAdd.addEventListener("click", () => {
      const isbn = document.getElementById("add-isbn").value.trim();
      const title = document.getElementById("add-title").value.trim();
      const author = document.getElementById("add-author").value.trim();
      const status = document.getElementById("add-status").value;
      const ratingVal = document.getElementById("add-rating").value.trim();

      if (!isbn || !title || !author) {
        logOutput("ISBN, Titel und Autor sind erforderlich.");
        return;
      }

      const msg = {
        type: "library_tracker/books/add",
        isbn,
        title,
        author,
        status,
      };
      if (ratingVal) {
        msg.rating = parseInt(ratingVal, 10);
      }

      callWS(msg);
    });
  }

  // 4. Authors List
  const btnAuthors = document.getElementById("btn-list-authors");
  if (btnAuthors) {
    btnAuthors.addEventListener("click", () => {
      callWS({ type: "library_tracker/authors/list" });
    });
  }
});
