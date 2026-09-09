// HA Library Tracker – Panel JS (Session 2)
// Calls WebSocket API endpoints for testing.
//
// Connection to Home Assistant is handled by ha-client.js (this is an
// iframe panel, so no `hass` object is available here - see that file
// and the auth section in index.html for why).

console.info("[library_tracker] Panel loaded with WebSocket test console.");

let haClient = null;

function logOutput(data) {
  const outputEl = document.getElementById("ws-output");
  if (outputEl) {
    outputEl.textContent = typeof data === "object" ? JSON.stringify(data, null, 2) : String(data);
  }
}

function setConnectionStatus(text, ok) {
  const el = document.getElementById("connection-status");
  if (el) {
    el.textContent = text;
    el.style.color = ok ? "var(--lt-success)" : "#c62828";
  }
}

async function connectWithToken(token) {
  setConnectionStatus("Verbinde …", true);
  try {
    haClient = await window.LibraryTrackerHA.connect(token);
    window.LibraryTrackerHA.storeToken(token);
    setConnectionStatus("Verbunden.", true);
    document.getElementById("auth-section").hidden = true;
    document.getElementById("ws-console").hidden = false;
  } catch (err) {
    haClient = null;
    window.LibraryTrackerHA.clearStoredToken();
    setConnectionStatus("Verbindung fehlgeschlagen: " + (err.message || err), false);
  }
}

async function callWS(msg) {
  if (!haClient) {
    logOutput("Fehler: nicht mit Home Assistant verbunden. Bitte zuerst Access Token eingeben.");
    return;
  }
  try {
    logOutput("Sende Command: " + JSON.stringify(msg));
    const result = await haClient.callWS(msg);
    logOutput(result);
  } catch (err) {
    logOutput({ error: err });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const tokenInput = document.getElementById("token-input");
  const btnConnect = document.getElementById("btn-connect");

  if (btnConnect) {
    btnConnect.addEventListener("click", () => {
      const token = tokenInput.value.trim();
      if (!token) {
        setConnectionStatus("Bitte ein Access Token eingeben.", false);
        return;
      }
      connectWithToken(token);
    });
  }

  const storedToken = window.LibraryTrackerHA.getStoredToken();
  if (storedToken) {
    connectWithToken(storedToken);
  }

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
