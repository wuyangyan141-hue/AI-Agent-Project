import { app, BrowserWindow, ipcMain, screen } from 'electron';
import path from 'node:path';

let chatWindow: BrowserWindow | null = null;
let petWindow: BrowserWindow | null = null;
const preload = path.join(__dirname, 'preload.cjs');

function showChat() {
  if (chatWindow && !chatWindow.isDestroyed()) { chatWindow.show(); chatWindow.focus(); return; }
  chatWindow = new BrowserWindow({
    width: 900, height: 650, minWidth: 480, minHeight: 400,
    webPreferences: { preload, contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  chatWindow.on('closed', () => { chatWindow = null; });
  if (!app.isPackaged) chatWindow.loadURL('http://127.0.0.1:5173');
  else chatWindow.loadFile(path.join(__dirname, '../dist/index.html'));
}

function showPet() {
  if (petWindow && !petWindow.isDestroyed()) return;
  const { workArea } = screen.getPrimaryDisplay();
  petWindow = new BrowserWindow({
    width: 190, height: 220,
    x: workArea.x + workArea.width - 220, y: workArea.y + workArea.height - 250,
    frame: false, transparent: true, alwaysOnTop: true, resizable: false,
    skipTaskbar: true, hasShadow: false,
    webPreferences: { preload, contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  petWindow.setAlwaysOnTop(true, 'floating');
  petWindow.on('closed', () => { petWindow = null; });
  if (!app.isPackaged) petWindow.loadURL('http://127.0.0.1:5173/#pet');
  else petWindow.loadFile(path.join(__dirname, '../dist/index.html'), { hash: 'pet' });
}
app.whenReady().then(() => {
  ipcMain.on('pet:open-chat', showChat);
  ipcMain.on('pet:show', showPet);
  ipcMain.on('pet:close', () => petWindow?.close());
  showChat(); showPet();
  app.on('activate', () => { showChat(); showPet(); });
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
