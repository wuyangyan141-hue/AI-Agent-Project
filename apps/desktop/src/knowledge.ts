export const api=import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
export type DocumentOutlineItem={title:string;page:number|null;preview:string;chunk_id?:string};
export type KnowledgeDocument={id:string;filename:string;size:number;status:string;chunk_count:number;error:string|null;needs_reindex:boolean;created_at:string;keywords?:string[];outline?:DocumentOutlineItem[];summary?:string|null};
export type LearningNextStep={stage:string;action:string;title:string;suggestion:string;prompt:string;placeholder?:string;status?:{streak?:{current_streak?:number;achievements?:string[]}}};
export type Source={id:string;document_id:string;chunk_id:string;filename:string;page:number|null;section:string|null;snippet:string;score:number};
export type SavedMemory={id:string;key:string;content:string;tags:string[]};
export type ChatMessage={id:string;role:'user'|'assistant';content:string;metadata?:{sources?:Source[];mode?:string;warning?:string;draft?:unknown}};
export type Conversation={id:string;title:string;updated_at:string};
export async function request<T>(path:string,options:RequestInit={}):Promise<T>{
  const response=await fetch(api+path,{...options,headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...options.headers}});
  if(!response.ok){const body=await response.json().catch(()=>({}));throw Error(typeof body.detail==='string'?body.detail:'请求失败，请检查服务或输入内容。');}
  return response.status===204?undefined as T:response.json();
}
export function sourcePosition(source:Source){return source.page?`第 ${source.page} 页`:source.section || '正文片段';}
