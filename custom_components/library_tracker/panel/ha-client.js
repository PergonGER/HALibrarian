// Minimal Home Assistant WebSocket client for use inside this panel's
// iframe.
//
// Home Assistant does NOT inject a `hass` object into an iframe panel's
// page (neither into the iframe's own window nor as a global on the
// parent window) - that only happens for `panel_custom` web-component
// panels. This iframe panel therefore connects on its own, directly to
// HA's WebSocket API on the same origin, authenticated with a
// Long-Lived Access Token the user supplies once (see index.html).
//
// No external library dependency (e.g. home-assistant-js-websocket) is
// used here on purpose, to keep this panel buildless/CDN-free - the
// protocol itself (auth handshake + id-correlated request/response) is
// small enough to implement directly.
(function (global) {
  "use strict";

  const TOKEN_KEY = "library_tracker_llat";

  function getStoredToken() {
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch (err) {
      return null;
    }
  }

  function storeToken(token) {
    try {
      window.localStorage.setItem(TOKEN_KEY, token);
    } catch (err) {
      // localStorage unavailable (private browsing etc.) - the current
      // connection still works, it just won't be remembered next time.
    }
  }

  function clearStoredToken() {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
    } catch (err) {
      /* ignore */
    }
  }

  function wsUrl() {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/api/websocket`;
  }

  /**
   * Connect to Home Assistant's WebSocket API and authenticate.
   * Resolves with a client exposing callWS(), rejects on auth failure
   * or a connection error before authentication completed.
   */
  function connect(token) {
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(wsUrl());
      let nextId = 1;
      const pending = new Map();
      let authSettled = false;

      socket.addEventListener("message", (event) => {
        let msg;
        try {
          msg = JSON.parse(event.data);
        } catch (err) {
          return;
        }

        if (msg.type === "auth_required") {
          socket.send(JSON.stringify({ type: "auth", access_token: token }));
          return;
        }

        if (msg.type === "auth_ok") {
          authSettled = true;
          resolve({
            callWS(command) {
              return new Promise((res, rej) => {
                const id = nextId++;
                pending.set(id, { resolve: res, reject: rej });
                socket.send(JSON.stringify(Object.assign({}, command, { id })));
              });
            },
            close() {
              socket.close();
            },
          });
          return;
        }

        if (msg.type === "auth_invalid") {
          authSettled = true;
          reject(new Error(msg.message || "Ungültiges Access Token."));
          socket.close();
          return;
        }

        if (msg.type === "result" && pending.has(msg.id)) {
          const { resolve: res, reject: rej } = pending.get(msg.id);
          pending.delete(msg.id);
          if (msg.success) {
            res(msg.result);
          } else {
            rej(msg.error || { message: "Unbekannter Fehler" });
          }
        }
      });

      socket.addEventListener("error", () => {
        if (!authSettled) {
          authSettled = true;
          reject(new Error("WebSocket-Verbindung zu Home Assistant fehlgeschlagen."));
        }
      });

      socket.addEventListener("close", () => {
        if (!authSettled) {
          authSettled = true;
          reject(
            new Error(
              "Verbindung wurde geschlossen, bevor die Authentifizierung abgeschlossen war."
            )
          );
        }
      });
    });
  }

  global.LibraryTrackerHA = { connect, getStoredToken, storeToken, clearStoredToken };
})(window);
