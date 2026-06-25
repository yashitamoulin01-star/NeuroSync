// Content script — runs on supported meeting pages. Its only job is to detect
// the meeting platform and surface a small, non-intrusive badge. It NEVER reads,
// modifies, or injects into the meeting application's own code or DOM logic.

(function () {
  function provider() {
    const h = location.hostname;
    if (h.includes('meet.google.com')) return 'Google Meet';
    if (h.includes('zoom.us')) return 'Zoom';
    if (h.includes('teams.microsoft.com')) return 'Microsoft Teams';
    if (h.includes('webex.com')) return 'Cisco Webex';
    return null;
  }

  const name = provider();
  if (!name) return;

  // Report detection to the extension so the popup can show "ready".
  try {
    chrome.runtime.sendMessage({ type: 'meeting_detected', provider: name, url: location.href });
  } catch (_) { /* extension context may be reloading */ }

  // Lightweight, dismissible badge — purely informational.
  if (document.getElementById('neurosync-badge')) return;
  const badge = document.createElement('div');
  badge.id = 'neurosync-badge';
  badge.textContent = 'NeuroSync ready · click the extension to Start Analysis';
  Object.assign(badge.style, {
    position: 'fixed', bottom: '16px', right: '16px', zIndex: 2147483647,
    background: 'rgba(20,20,32,0.92)', color: '#c7d2fe', font: '12px system-ui',
    padding: '8px 12px', borderRadius: '10px', border: '1px solid rgba(129,140,248,0.4)',
    boxShadow: '0 4px 16px rgba(0,0,0,0.4)', cursor: 'default', pointerEvents: 'auto',
  });
  badge.addEventListener('click', () => badge.remove());
  document.documentElement.appendChild(badge);
  setTimeout(() => badge.remove(), 8000);
})();
