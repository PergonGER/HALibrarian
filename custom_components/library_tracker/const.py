"""Constants for the HA Library Tracker integration."""

DOMAIN = "library_tracker"

# Config entry / options keys
CONF_GOOGLE_BOOKS_API_KEY = "google_books_api_key"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_AUTHOR_CHECK_INTERVAL = "author_check_interval_hours"

DEFAULT_AUTHOR_CHECK_INTERVAL = 24  # hours

# Panel
PANEL_URL_PATH = "library-tracker"
PANEL_TITLE = "Library Tracker"
PANEL_ICON = "mdi:bookshelf"
STATIC_URL_BASE = "/library_tracker_panel"

# Database
DB_FILENAME = "library_tracker.db"
