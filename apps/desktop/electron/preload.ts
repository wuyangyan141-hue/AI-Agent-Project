import { contextBridge, ipcRenderer } from 'electron';

type PetDragPayload = boolean | { dragging: boolean; direction?: 'left' | 'right' | 'up' | 'down' };

contextBridge.exposeInMainWorld('desktop', {
  platform: process.platform,
  openChat: (tab?: string) => ipcRenderer.send('pet:open-chat', tab),
  showPet: () => ipcRenderer.send('pet:show'),
  closePet: () => ipcRenderer.send('pet:close'),
  restartPet: () => ipcRenderer.send('pet:restart'),
  resizePet: (width: number, height: number) => ipcRenderer.send('pet:resize', width, height),
  movePetBy: (dx: number, dy: number) => ipcRenderer.send('pet:move-by', dx, dy),
  restartShortcut: process.platform === 'darwin' ? '⌘⇧R' : 'Ctrl+Shift+R',
  setPetClickThrough: (ignore: boolean) => ipcRenderer.send('pet:click-through', ignore),
  publishState: (event: unknown) => ipcRenderer.send('pet:state', event),
  onPetState: (callback: (event: unknown) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, value: unknown) => callback(value);
    ipcRenderer.on('pet:state-update', listener);
    return () => ipcRenderer.removeListener('pet:state-update', listener);
  },
  onNavigate: (callback: (tab: string) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, tab: string) => callback(tab);
    ipcRenderer.on('panel:navigate', listener);
    return () => ipcRenderer.removeListener('panel:navigate', listener);
  },
  onPetDrag: (callback: (payload: PetDragPayload) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, payload: unknown) => {
      if (payload === true || payload === false) {
        callback(payload);
        return;
      }
      if (payload && typeof payload === 'object' && 'dragging' in payload) {
        const data = payload as { dragging: unknown; direction?: unknown };
        const direction =
          data.direction === 'left' || data.direction === 'right' || data.direction === 'up' || data.direction === 'down'
            ? data.direction
            : undefined;
        callback({ dragging: data.dragging === true, direction });
      }
    };
    ipcRenderer.on('pet:drag', listener);
    return () => ipcRenderer.removeListener('pet:drag', listener);
  },
});
