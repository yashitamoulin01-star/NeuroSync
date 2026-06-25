// Preload — exposes a minimal, safe bridge to the renderer. No Node APIs leak
// into the page; the renderer can only list sources and read config.

const { contextBridge, ipcRenderer } = require('electron');
const config = require('./config');

contextBridge.exposeInMainWorld('neurosync', {
  listSources: () => ipcRenderer.invoke('list-sources'),
  config,
});
