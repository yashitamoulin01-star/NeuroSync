"""
Concrete server-side capture adapters.

RTSP and Virtual Camera are pulled by the backend itself (cv2 opens the stream).
Browser and Desktop sources push INTO the backend over the existing
/ws/session/{id} protocol — the extension and desktop agent are the producers, so
there is no separate server adapter for them; they reuse the live ingestion path.
"""
