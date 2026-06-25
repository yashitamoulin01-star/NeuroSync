// NeuroSync backend endpoints. Change these if the backend runs elsewhere.
const NEUROSYNC = {
  API_BASE: 'http://localhost:8000',
  WS_BASE:  'ws://localhost:8000',
  FRAME_INTERVAL_MS: 500,   // matches the backend analytics window
  FRAME_QUALITY: 0.6,       // JPEG quality for streamed frames
  AUDIO_SAMPLE_RATE: 16000, // backend expects 16 kHz int16 PCM
};

// Map a meeting URL to a provider label.
function detectProvider(url) {
  if (!url) return null;
  if (url.includes('meet.google.com'))    return { id: 'google_meet',     name: 'Google Meet' };
  if (url.includes('zoom.us'))            return { id: 'zoom',            name: 'Zoom' };
  if (url.includes('teams.microsoft.com'))return { id: 'microsoft_teams', name: 'Microsoft Teams' };
  if (url.includes('webex.com'))          return { id: 'webex',           name: 'Cisco Webex' };
  return null;
}

if (typeof module !== 'undefined') module.exports = { NEUROSYNC, detectProvider };
