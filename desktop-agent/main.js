// NeuroSync Desktop Agent — Electron main process.
//
// Behaves like OBS / screen-recording software: it enumerates OS capture sources
// (windows + screens) via Electron's desktopCapturer and lets the user pick one.
// It NEVER injects into, reads memory from, or modifies another application — it
// only uses operating-system capture APIs with explicit user selection.

const { app, BrowserWindow, ipcMain, desktopCapturer, session } = require('electron');
const path = require('path');

let win = null;

function createWindow() {
  win = new BrowserWindow({
    width: 460,
    height: 620,
    resizable: false,
    title: 'NeuroSync Desktop Agent',
    backgroundColor: '#0b0b14',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.removeMenu();
  win.loadFile('index.html');
}

// Detect supported meeting apps among capturable windows (informational only).
function detectMeetingApp(name) {
  const n = (name || '').toLowerCase();
  if (n.includes('zoom')) return 'Zoom';
  if (n.includes('teams')) return 'Microsoft Teams';
  if (n.includes('webex')) return 'Webex';
  if (n.includes('slack')) return 'Slack';
  if (n.includes('meet')) return 'Google Meet';
  return null;
}

// Renderer asks for the list of capturable sources.
ipcMain.handle('list-sources', async () => {
  const sources = await desktopCapturer.getSources({
    types: ['window', 'screen'],
    thumbnailSize: { width: 320, height: 180 },
  });
  return sources.map((s) => ({
    id: s.id,
    name: s.name,
    kind: s.id.startsWith('screen') ? 'screen' : 'window',
    meetingApp: detectMeetingApp(s.name),
    thumbnail: s.thumbnail ? s.thumbnail.toDataURL() : null,
  }));
});

app.whenReady().then(() => {
  // Auto-approve getUserMedia for our own renderer (the user already chose a
  // source in our UI). No other origin runs in this app.
  session.defaultSession.setPermissionRequestHandler((_wc, _perm, cb) => cb(true));
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
