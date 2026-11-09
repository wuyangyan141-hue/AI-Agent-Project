import { describe, expect, it } from 'vitest';
import { messageEvent, parseServerEvent } from '../src/protocol';
describe('WebSocket protocol', () => {
  it('encodes a message', () => expect(JSON.parse(messageEvent('你好'))).toEqual({ type: 'message', text: '你好' }));
  it('accepts a reply and pet state', () => expect(parseServerEvent('{"type":"reply","text":"ok","state":"success"}').state).toBe('success'));
  it('rejects malformed events', () => expect(() => parseServerEvent('{"type":"reply","text":3,"state":"success"}')).toThrow());
});
