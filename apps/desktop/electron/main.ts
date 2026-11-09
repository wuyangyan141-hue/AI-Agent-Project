import { app, BrowserWindow } from 'electron';
import path from 'node:path';

function createWindow() {
  const window = new BrowserWindow({
    width: 900, height: 650, minWidth: 480, minHeight: 400,
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  if (!app.isPackaged) window.loadURL('http://127.0.0.1:5173');
  else window.loadFile(path.join(__dirname, '../dist/index.html'));
}
app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
