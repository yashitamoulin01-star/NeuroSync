"""
Connector Framework — secure, pluggable integration with external meeting
providers (Google Workspace, Microsoft 365, Zoom, Webex, Slack).

See CONNECTOR_FRAMEWORK.md for the full design. A new provider is one file in
providers/ that subclasses BaseConnector and calls @register — no other change.
"""

# Importing the providers package triggers @register for every built-in connector.
from backend.connectors import providers  # noqa: F401
