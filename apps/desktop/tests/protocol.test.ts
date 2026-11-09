import { describe, expect, it } from 'vitest';
import { messageEvent, parseServerEvent } from '../src/protocol';
describe('WebSocket protocol', () => {
  it('encodes a message', () => expect(JSON.parse(messageEvent('你好'))).toEqual({ type: 'message', text: '你好' }));
  it('accepts a reply', () => expect(parseServerEvent('{"type":"reply","text":"ok"}').text).toBe('ok'));
  it('rejects malformed events', () => expect(() => parseServerEvent('{"type":"reply","text":3}')).toThrow());
});
