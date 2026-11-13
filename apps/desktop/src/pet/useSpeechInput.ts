import { useEffect, useRef, useState } from 'react';

export type SpeechPhase = 'unsupported' | 'idle' | 'listening' | 'error';

function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

/** Hold-to-talk wrapper around the browser / Electron Web Speech API. */
export function useSpeechInput(onTranscript: (text: string, isFinal: boolean) => void) {
  const [phase, setPhase] = useState<SpeechPhase>(() => (getSpeechRecognition() ? 'idle' : 'unsupported'));
  const [error, setError] = useState('');
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const active = useRef(false);
  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;

  useEffect(() => {
    const Ctor = getSpeechRecognition();
    if (!Ctor) {
      setPhase('unsupported');
      return;
    }
    const engine = new Ctor();
    engine.lang = 'zh-CN';
    engine.continuous = true;
    engine.interimResults = true;
    engine.maxAlternatives = 1;
    engine.onstart = () => {
      if (!active.current) return;
      setPhase('listening');
      setError('');
    };
    engine.onresult = (event) => {
      let finalText = '';
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const piece = event.results[i][0]?.transcript?.trim() || '';
        if (!piece) continue;
        if (event.results[i].isFinal) finalText = `${finalText} ${piece}`.trim();
        else interim = `${interim} ${piece}`.trim();
      }
      if (finalText) onTranscriptRef.current(finalText, true);
      else if (interim) onTranscriptRef.current(interim, false);
    };
    engine.onerror = (event) => {
      if (event.error === 'aborted' || event.error === 'no-speech') return;
      setError(event.error === 'not-allowed' ? '请允许使用麦克风' : '语音识别失败，请再试');
      setPhase('error');
      active.current = false;
    };
    engine.onend = () => {
      if (active.current) {
        // Chromium sometimes ends early while the user still holds the button.
        try {
          engine.start();
          return;
        } catch {
          active.current = false;
        }
      }
      setPhase((prev) => (prev === 'unsupported' ? prev : 'idle'));
    };
    recognition.current = engine;
    setPhase('idle');
    return () => {
      active.current = false;
      try {
        engine.abort();
      } catch {
        /* ignore */
      }
      recognition.current = null;
    };
  }, []);

  function start() {
    const engine = recognition.current;
    if (!engine || active.current) return false;
    active.current = true;
    setError('');
    try {
      engine.start();
      setPhase('listening');
      return true;
    } catch {
      active.current = false;
      setPhase('error');
      setError('无法启动麦克风');
      return false;
    }
  }

  function stop() {
    const engine = recognition.current;
    active.current = false;
    if (!engine) return;
    try {
      engine.stop();
    } catch {
      /* ignore */
    }
    setPhase((prev) => (prev === 'unsupported' ? prev : 'idle'));
  }

  return {
    supported: phase !== 'unsupported',
    listening: phase === 'listening',
    phase,
    error,
    start,
    stop,
  };
}
