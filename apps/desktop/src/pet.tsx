import React from 'react';
import { createRoot } from 'react-dom/client';
import './desktop';
import { PetWindow } from './pet/PetWindow';

createRoot(document.getElementById('root')!).render(<PetWindow />);
