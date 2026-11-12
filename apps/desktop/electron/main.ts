import { app, BrowserWindow, globalShortcut, ipcMain, screen } from 'electron';
import fs from 'node:fs';
import path from 'node:path';

let chatWindow: BrowserWindow | null = null;
let petWindow: BrowserWindow | null = null;
let quitting = false;
const preload = path.join(__dirname, 'preload.cjs');
const tabs = new Set(['chat', 'tasks', 'library', 'memory', 'history', 'settings']);
const development = process.argv.includes('--companion-dev');
const PET_WIDTH = 320;
const PET_HEIGHT_COLLAPSED = 360;
/** Soft-restart pet (+ reload chat): Ctrl/⌘ + Shift + R */
const RESTART_ACCELERATOR = 'CommandOrControl+Shift+R';
const positionFile = () => path.join(app.getPath('userData'), 'pet-bounds.json');

type SavedBounds = { x: number; y: number; width?: number; height?: number };

function readSavedBounds(): SavedBounds | null {
  try {
    const raw = JSON.parse(fs.readFileSync(positionFile(), 'utf8')) as SavedBounds;
    if (!Number.isFinite(raw.x) || !Number.isFinite(raw.y)) return null;
    return raw;
  } catch {
    return null;
  }
}

function writeSavedBounds() {
  if (!petWindow || petWindow.isDestroyed()) return;
  const bounds = petWindow.getBounds();
  try {
    fs.writeFileSync(positionFile(), JSON.stringify({ x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height }));
  } catch {
    /* ignore persistence failures */
  }
}

function clampToWorkArea(x: number, y: number, width: number, height: number) {
  const display = screen.getDisplayNearestPoint({ x: Math.round(x + width / 2), y: Math.round(y + height / 2) });
  const area = display.workArea;
  return {
    x: Math.min(Math.max(area.x, Math.round(x)), area.x + area.width - width),
    y: Math.min(Math.max(area.y, Math.round(y)), area.y + area.height - height),
    width,
    height,
  };
}

function focusChat() {
  if (!chatWindow || chatWindow.isDestroyed()) return;
  if (chatWindow.isMinimized()) chatWindow.restore();
  chatWindow.show();
  chatWindow.focus();
  chatWindow.moveTop();
}

function showChat(tab = 'library') {
  if (!tabs.has(tab)) tab = 'library';
  if (chatWindow && !chatWindow.isDestroyed()) {
    chatWindow.webContents.send('panel:navigate', tab);
    focusChat();
    return;
  }
  chatWindow = new BrowserWindow({
    width: 1060,
    height: 790,
    minWidth: 650,
    minHeight: 540,
    title: '豆豆 · 学习伙伴',
    backgroundColor: '#faf8f2',
    show: false,
    webPreferences: { preload, contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  chatWindow.on('close', (event) => {
    if (!quitting) {
      event.preventDefault();
      chatWindow?.hide();
    }
  });
  chatWindow.on('closed', () => {
    chatWindow = null;
  });
  chatWindow.once('ready-to-show', () => focusChat());
  const load = development
    ? chatWindow.loadURL(`http://127.0.0.1:5173/#${tab}`)
    : chatWindow.loadFile(path.join(__dirname, '../dist/index.html'), { hash: tab });
  void load.catch((error) => {
    console.error('Failed to open chat window', error);
    focusChat();
  });
}

function showPet() {
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.show();
    petWindow.focus();
    return;
  }
  const saved = readSavedBounds();
  const { workArea } = screen.getPrimaryDisplay();
  const width = PET_WIDTH;
  const height = PET_HEIGHT_COLLAPSED;
  const initial = clampToWorkArea(
    saved?.x ?? workArea.x + workArea.width - width - 28,
    saved?.y ?? workArea.y + workArea.height - height - 28,
    width,
    height,
  );
  petWindow = new BrowserWindow({
    width: initial.width,
    height: initial.height,
    x: initial.x,
    y: initial.y,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    webPreferences: { preload, contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  petWindow.setAlwaysOnTop(true, 'floating');
  petWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  // Do NOT listen to will-move/moved for drag animation: resizePet/setBounds also fire
  // those events and were cancelling idle clips. Renderer owns drag UX via movePetBy.
  petWindow.on('moved', () => writeSavedBounds());
  petWindow.on('closed', () => {
    writeSavedBounds();
    petWindow = null;
  });
  if (development) petWindow.loadURL('http://127.0.0.1:5173/#pet');
  else petWindow.loadFile(path.join(__dirname, '../dist/index.html'), { hash: 'pet' });
}

/** Keep the bottom edge fixed while height changes (bubble growth expands upward). */
function resizePet(width: number, height: number) {
  if (!petWindow || petWindow.isDestroyed()) return;
  if (!Number.isFinite(width) || !Number.isFinite(height)) return;
  const nextWidth = Math.round(Math.min(360, Math.max(300, width)));
  const nextHeight = Math.round(Math.min(720, Math.max(300, height)));
  const bounds = petWindow.getBounds();
  const next = clampToWorkArea(bounds.x + bounds.width - nextWidth, bounds.y + bounds.height - nextHeight, nextWidth, nextHeight);
  if (next.x === bounds.x && next.y === bounds.y && next.width === bounds.width && next.height === bounds.height) return;
  petWindow.setBounds(next);
  writeSavedBounds();
}

/** Recreate the pet window and hard-reload the chat panel. */
function restartCompanion() {
  writeSavedBounds();
  if (petWindow && !petWindow.isDestroyed()) {
    const old = petWindow;
    petWindow = null;
    old.destroy();
  }
  showPet();
  if (chatWindow && !chatWindow.isDestroyed()) {
    chatWindow.webContents.reloadIgnoringCache();
    chatWindow.show();
  }
}

app.whenReady().then(() => {
  ipcMain.on('pet:open-chat', (_event, tab) => showChat(typeof tab === 'string' ? tab : 'library'));
  ipcMain.on('pet:show', showPet);
  ipcMain.on('pet:close', () => petWindow?.close());
  ipcMain.on('pet:restart', () => restartCompanion());
  ipcMain.on('pet:resize', (event, width, height) => {
    if (event.sender === petWindow?.webContents) resizePet(Number(width), Number(height));
  });
  ipcMain.on('pet:move-by', (event, dx, dy) => {
    if (event.sender !== petWindow?.webContents || petWindow.isDestroyed()) return;
    if (!Number.isFinite(dx) || !Number.isFinite(dy)) return;
    const bounds = petWindow.getBounds();
    const next = clampToWorkArea(bounds.x + Number(dx), bounds.y + Number(dy), bounds.width, bounds.height);
    petWindow.setBounds(next);
  });
  ipcMain.on('pet:click-through', (event, ignore) => {
    if (event.sender === petWindow?.webContents && typeof ignore === 'boolean') {
      petWindow.setIgnoreMouseEvents(ignore, { forward: true });
    }
  });
  ipcMain.on('pet:state', (event, payload) => {
    if (
      event.sender !== chatWindow?.webContents ||
      !payload ||
      typeof payload.text !== 'string' ||
      !['idle', 'thinking', 'searching', 'tool', 'talking', 'success', 'error'].includes(payload.state)
    ) {
      return;
    }
    petWindow?.webContents.send('pet:state-update', payload);
  });
  const registered = globalShortcut.register(RESTART_ACCELERATOR, () => restartCompanion());
  if (!registered) {
    console.warn(`Failed to register restart shortcut: ${RESTART_ACCELERATOR}`);
  }
  showPet();
  app.on('activate', () => {
    showPet();
    showChat('library');
  });
});
app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});
app.on('before-quit', () => {
  quitting = true;
  writeSavedBounds();
});
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
