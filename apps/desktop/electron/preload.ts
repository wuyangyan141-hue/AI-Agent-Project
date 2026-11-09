import { contextBridge, ipcRenderer } from 'electron';
contextBridge.exposeInMainWorld('desktop', {
  platform: process.platform,
  openChat: () => ipcRenderer.send('pet:open-chat'),
  showPet: () => ipcRenderer.send('pet:show'),
  closePet: () => ipcRenderer.send('pet:close'),
});
