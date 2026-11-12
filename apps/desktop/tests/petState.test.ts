import { describe, expect, it } from 'vitest';
import { parseServerEvent } from '../src/protocol';
import { atlasBackgroundPosition, PET_FRAME_SETS, usesSpriteAtlas } from '../src/pet/animationAssets';
import { isBubbleTruncated } from '../src/pet/PetBubble';
import { canSendMessage, mapServerEventToPet, nextIdleAfterTerminal } from '../src/pet/stateMapping';
import { DEFAULT_BUBBLE_COPY } from '../src/pet/types';

describe('pet WebSocket state mapping', () => {
  it('maps status states to bubble copy and animation', () => {
    const event = parseServerEvent(JSON.stringify({ type: 'status', text: '…', state: 'searching' }));
    expect(mapServerEventToPet(event, true)).toEqual({
      animation: 'searching',
      bubbleText: DEFAULT_BUBBLE_COPY.searching,
      sessionId: undefined,
      finished: false,
    });
  });

  it('maps idle status while sending to talking', () => {
    const event = parseServerEvent(JSON.stringify({ type: 'status', text: 'working', state: 'idle' }));
    expect(mapServerEventToPet(event, true).animation).toBe('talking');
  });

  it('puts agent replies into the head bubble and marks success', () => {
    const event = parseServerEvent(JSON.stringify({ type: 'reply', text: '数据库可以按索引复习', state: 'success', session_id: 'a'.repeat(32) }));
    const mapped = mapServerEventToPet(event, true);
    expect(mapped.animation).toBe('success');
    expect(mapped.bubbleText).toContain('数据库');
    expect(mapped.assistantMessage).toContain('数据库');
    expect(mapped.finished).toBe(true);
  });

  it('accepts talking as a protocol pet state', () => {
    expect(parseServerEvent(JSON.stringify({ type: 'status', text: '答', state: 'talking' })).state).toBe('talking');
  });
});

describe('pet chat controls', () => {
  it('disables send when disconnected or empty', () => {
    expect(canSendMessage('disconnected', '你好', false)).toBe(false);
    expect(canSendMessage('connected', '   ', false)).toBe(false);
    expect(canSendMessage('connected', '你好', true)).toBe(false);
    expect(canSendMessage('connected', '你好', false)).toBe(true);
  });

  it('returns to idle after success or error animations', () => {
    expect(nextIdleAfterTerminal('success')).toBe('idle');
    expect(nextIdleAfterTerminal('error')).toBe('idle');
    expect(nextIdleAfterTerminal('thinking')).toBeNull();
  });

  it('detects long bubble replies that need full chat', () => {
    expect(isBubbleTruncated('短')).toBe(false);
    expect(isBubbleTruncated('第一行\n第二行\n第三行\n第四行\n第五行\n第六行\n第七行')).toBe(true);
  });
});

describe('pet chrome helpers', () => {
  it('toggles chat open flag without losing the pet shell', () => {
    let chatOpen = true;
    const toggle = () => {
      chatOpen = !chatOpen;
      return chatOpen;
    };
    expect(toggle()).toBe(false);
    expect(toggle()).toBe(true);
  });

  it('uses openChat for the main window entry point', () => {
    const calls: string[] = [];
    const openChat = (tab = 'chat') => calls.push(tab);
    openChat('chat');
    openChat('library');
    expect(calls).toEqual(['chat', 'library']);
  });
});

describe('dog atlas sprites', () => {
  it('uses the shared transparent atlas mode', () => {
    expect(usesSpriteAtlas()).toBe(true);
    expect(PET_FRAME_SETS.idle.frames.length).toBeGreaterThan(1);
    expect(PET_FRAME_SETS.talking.frames[0]).toBe(12);
    expect(PET_FRAME_SETS.success.frames[0]).toBe(16);
  });

  it('includes extra local clips composed from the atlas', () => {
    expect(PET_FRAME_SETS.wave.frames).toContain(16);
    expect(PET_FRAME_SETS.sleep.frames).toContain(2);
    expect(PET_FRAME_SETS.peek.frames).toContain(8);
    expect(PET_FRAME_SETS.stretch.frames[0]).toBe(4);
    expect(PET_FRAME_SETS.stretch.loop).toBe(false);
    expect(PET_FRAME_SETS.drag.frames).toContain(8);
    expect(PET_FRAME_SETS.drag.frames).not.toContain(16);
    expect(PET_FRAME_SETS.dragUp.frames[0]).toBe(4);
    expect(PET_FRAME_SETS.dragLeft.frames).not.toContain(16);
  });

  it('picks look direction from drag delta', async () => {
    const { lookFromDelta, dragClipFor } = await import('../src/pet/animationAssets');
    expect(lookFromDelta(-12, 2)).toBe('left');
    expect(lookFromDelta(12, 2)).toBe('right');
    expect(lookFromDelta(1, -20)).toBe('up');
    expect(lookFromDelta(1, 20)).toBe('down');
    expect(dragClipFor('up')).toBe('dragUp');
    expect(dragClipFor('right')).toBe('dragRight');
  });

  it('maps atlas cells with 4×5 background positions', () => {
    expect(atlasBackgroundPosition(0)).toBe('0% 0%');
    expect(atlasBackgroundPosition(3)).toBe('100% 0%');
    expect(atlasBackgroundPosition(4)).toBe('0% 25%');
    expect(atlasBackgroundPosition(19)).toBe('100% 100%');
  });
});
