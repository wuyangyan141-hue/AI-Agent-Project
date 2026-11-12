export type PanelTab = 'chat' | 'tasks' | 'library' | 'memory' | 'history' | 'settings';
export type PetDragDirection = 'left' | 'right' | 'up' | 'down';
export type PetDragPayload = boolean | { dragging: boolean; direction?: PetDragDirection };

declare global {
  interface Window {
    desktop?: {
      platform: string;
      openChat(tab?: PanelTab): void;
      showPet(): void;
      closePet(): void;
      restartPet?(): void;
      resizePet(width: number, height: number): void;
      movePetBy?(dx: number, dy: number): void;
      restartShortcut?: string;
      setPetClickThrough(ignore: boolean): void;
      publishState(event: unknown): void;
      onPetState(callback: (event: unknown) => void): () => void;
      onNavigate(callback: (tab: PanelTab) => void): () => void;
      onPetDrag(callback: (payload: PetDragPayload) => void): () => void;
    };
  }
}
