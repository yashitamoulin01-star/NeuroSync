"""
Built-in connectors. Importing this package registers every provider via
@register. Add a new provider by importing its module here.
"""

from backend.connectors.providers import google_meet         # noqa: F401
from backend.connectors.providers import microsoft_teams     # noqa: F401
from backend.connectors.providers import zoom                # noqa: F401
from backend.connectors.providers import webex               # noqa: F401
from backend.connectors.providers import slack               # noqa: F401
from backend.connectors.providers import google_calendar     # noqa: F401
from backend.connectors.providers import microsoft_calendar  # noqa: F401
