import { useEffect, useState } from 'react';
import atlas from './assets/dog-atlas.webp';
import type { PetState } from './protocol';

const frames: Record<PetState | 'talking', number[]> = {
  idle: [0, 0, 1, 2, 1, 0, 3, 0],
  thinking: [4, 5, 6, 7],
  searching: [8, 9, 10, 11],
  tool: [4, 5, 6, 7],
  talking: [12, 13, 14, 15],
  success: [16, 17, 18, 19],
  error: [4, 4, 7, 7],
};

export function PetCharacter({ state, talking, onClick }: { state: PetState; talking: boolean; onClick: () => void }) {
  const animation = talking ? 'talking' : state;
  const [index, setIndex] = useState(0);
  const [reduced, setReduced] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const query = matchMedia('(prefers-reduced-motion: reduce)');
    const change = () => setReduced(query.matches);
    query.addEventListener('change', change);
    return () => query.removeEventListener('change', change);
  }, []);
  useEffect(() => {
    setIndex(0);
    if (reduced) return;
    const timer = window.setInterval(() => setIndex(current => {
      const next = current + 1;
      return animation === 'success' ? Math.min(next, frames[animation].length - 1) : next % frames[animation].length;
    }), animation === 'idle' ? 500 : 240);
    return () => window.clearInterval(timer);
  }, [animation, reduced]);
  const frame = frames[animation][reduced ? 0 : index] ?? frames[animation][0];
  return <button className="pet-character" aria-label="打开聊天" onClick={onClick} title="点击打开聊天">
    <span className="pet-sprite" style={{ backgroundImage: `url(${atlas})`, backgroundPosition: `${(frame % 4) * 100 / 3}% ${Math.floor(frame / 4) * 25}%` }} />
  </button>;
}
