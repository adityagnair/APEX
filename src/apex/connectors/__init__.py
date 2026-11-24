"""Data source connectors for Deep Research."""

from apex.connectors._stubs import (
    Attachment,
    BaseConnector,
    Document,
    SyncStatus,
)
from apex.connectors.store import KnowledgeStore

__all__ = ["Attachment", "BaseConnector", "Document", "KnowledgeStore", "SyncStatus"]

# Auto-register built-in connectors
import apex.connectors.obsidian  # noqa: F401

try:
    import apex.connectors.gmail  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.gmail_imap  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.gdrive  # noqa: F401
except ImportError:
    pass  # httpx may not be installed

try:
    import apex.connectors.notion  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.granola  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.gcontacts  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.imessage  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.apple_notes  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.apple_music  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.apple_contacts  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.apple_calendar  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.slack_connector  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.outlook  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.imap  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.gcalendar  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.dropbox  # noqa: F401
except ImportError:
    pass  # httpx may not be installed

try:
    import apex.connectors.whatsapp  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.oura  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.apple_health  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.strava  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.spotify  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.google_tasks  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.weather  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.github_notifications  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.hackernews  # noqa: F401
except ImportError:
    pass

try:
    import apex.connectors.news_rss  # noqa: F401
except ImportError:
    pass

