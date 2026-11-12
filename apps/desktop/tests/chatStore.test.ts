import { describe, it, expect } from 'vitest';
import { createConversationStore, scopeFields } from '../src/chatStore';
import type { ServerEvent } from '../src/protocol';

function windows() {
  type Port = Parameters<typeof createConversationStore>[0];
  const ports: NonNullable<Port>[] = [];
  function port() {
    const p: NonNullable<Port> = { onmessage: null, close() {}, postMessage(data) { for(const other of ports)if(other!==p)other.onmessage?.(new MessageEvent('message',{data:structuredClone(data)})); } };
    ports.push(p);return p;
  }
  return [createConversationStore(port()),createConversationStore(port())] as const;
}
const source={id:'S1',document_id:'doc1',chunk_id:'c1',filename:'lecture.pdf',page:7,section:null,snippet:'Actual course evidence.',score:.8};
const reply=(id:string):ServerEvent=>({type:'reply',text:'Answer [S1]',state:'success',request_id:id,session_id:'session1',sources:[source],answer_mode:'extractive',warning:'原文模式',context:{document_ids:['doc1'],topic:'range queries'}});

describe('two-window conversation state',()=>{
  it('keeps sources, warnings, scope and history when the other window opens',()=>{
    const [main,pet]=windows();const id=main.begin('范围查询','doc1')!;
    expect(pet.getSnapshot().pending?.id).toBe(id);
    expect(pet.getSnapshot().status?.state).toBe('thinking');
    expect(pet.begin('another question')).toBeNull();
    main.receive(reply(id));
    expect(pet.getSnapshot().messages[1].metadata?.sources?.[0]).toEqual(source);
    expect(pet.getSnapshot().messages[1].metadata?.warning).toBe('原文模式');
    expect(pet.getSnapshot().scope).toBe('doc1');
    const later=createConversationStore(undefined,{getItem:()=>JSON.stringify(pet.getSnapshot()),setItem(){}});
    expect(later.getSnapshot().messages[1].metadata?.sources?.[0].page).toBe(7);
  });
  it('synchronizes new conversations and ignores replies from old requests',()=>{
    const [main,pet]=windows();const id=pet.begin('old question','doc1')!;
    main.newChat();expect(pet.getSnapshot().sessionId).toBeNull();expect(pet.getSnapshot().messages).toEqual([]);
    expect(pet.receive(reply(id))).toBe(false);expect(main.getSnapshot().scope).toBe('auto');
  });
  it('restores a historical conversation with citations in both windows',()=>{
    const [main,pet]=windows();main.open('history1',[{id:'m1',role:'assistant',content:'old [S1]',metadata:{sources:[source]}}],'doc1');
    expect(pet.getSnapshot().sessionId).toBe('history1');expect(pet.getSnapshot().messages[0].metadata?.sources).toEqual([source]);
  });
  it('retains plan drafts produced from the pet',()=>{
    const [main,pet]=windows();const id=pet.begin('制定学习计划')!;
    pet.receive({...reply(id),type:'plan_draft',draft:{id:4,steps:[{day:1,title:'Read material',minutes:30}]},kind:'plan'});
    expect(main.getSnapshot().messages[1].metadata?.draft?.id).toBe(4);
    expect(main.getSnapshot().status?.state).toBe('success');
  });
  it('unlocks timed-out turns and rejects late results',()=>{
    const [main,pet]=windows();const id=main.begin('question')!;
    main.expire(Date.now()+91000);expect(pet.getSnapshot().pending).toBeNull();expect(main.receive(reply(id))).toBe(false);
  });
  it('keeps general chat explicitly outside document retrieval',()=>{
    expect(scopeFields('chat')).toEqual({general:true,knowledge:false,document_ids:null});
    expect(scopeFields('doc1')).toEqual({general:false,knowledge:true,document_ids:['doc1']});
  });
});
