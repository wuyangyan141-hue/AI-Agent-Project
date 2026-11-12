import React from 'react';
import { PetCharacter } from './pet/PetCharacter';
import type { PetState } from './protocol';
import { asPetAnimationState } from './pet/types';
import './pet/pet-character.css';

/** Compact avatar used by the main panel; reuses the pet character animation contract. */
export function DogAvatar({ state = 'idle', className = '' }: { state?: PetState; className?: string }) {
  return <PetCharacter state={asPetAnimationState(state)} className={`panel-dog ${className}`.trim()} />;
}
