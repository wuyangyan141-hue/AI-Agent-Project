"""Member 1 endpoints mounted on the existing FastAPI application."""
import re
from typing import Annotated
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from .integration import get_knowledge
from .service import KnowledgeService, UNSET

router = APIRouter(prefix='/knowledge', tags=['knowledge and memory'])
Service = Annotated[KnowledgeService, Depends(get_knowledge)]


def user_id(x_user_id: Annotated[str, Header()] = 'local-user'):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', x_user_id):
        raise HTTPException(400, '无效的本地用户空间。')
    return x_user_id

User = Annotated[str, Depends(user_id)]


class Query(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    document_ids: list[str] | None = Field(default=None, max_length=100)
    k: int = Field(default=4, ge=1, le=10)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    document_ids: list[str] | None = Field(default=None, max_length=100)

    @field_validator('question')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('问题不能为空。')
        return value.strip()


class Preferences(BaseModel):
    values: dict[str, str]

    @field_validator('values')
    @classmethod
    def bounded(cls, value):
        if len(value) > 20 or any(not k.strip() or len(k) > 64 or len(v) > 1000 for k,v in value.items()):
            raise ValueError('偏好最多20项，键最长64字符，值最长1000字符。')
        return value


class Memory(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator('key','content')
    @classmethod
    def nonempty(cls,value):
        if not value.strip():
            raise ValueError('标题和内容不能为空。')
        return value.strip()

    @field_validator('tags')
    @classmethod
    def bounded(cls,value):
        if any(len(item)>100 for item in value):
            raise ValueError('标签过长。')
        return value


@router.get('/health')
def status(service: Service):
    return service.status()

@router.get('/documents')
def documents(service: Service, user: User):
    return service.list_documents(user)

@router.post('/documents', status_code=201)
async def upload(service: Service, user: User, file: UploadFile = File(...)):
    data=bytearray()
    try:
        while chunk := await file.read(1024*1024):
            data.extend(chunk)
            if len(data)>service.settings.max_upload_mb*1024*1024:
                raise HTTPException(413, f'文件不能超过 {service.settings.max_upload_mb} MB。')
    finally:
        await file.close()
    return await run_in_threadpool(service.upload,user,file.filename or 'document.txt',bytes(data))

@router.delete('/documents/{document_id}',status_code=204)
def delete_document(document_id: str,service: Service,user: User):
    service.delete_document(user,document_id)

@router.post('/documents/{document_id}/reindex')
def reindex(document_id: str,service: Service,user: User):
    return service.reindex(user,document_id)

@router.get('/documents/{document_id}/chunks')
def chunks(document_id: str,service: Service,user: User):
    return service.document_chunks(user,document_id)

@router.get('/documents/{document_id}/overview')
def overview(document_id: str,service: Service,user: User):
    return service.document_overview(user,document_id)

@router.get('/documents/{document_id}/source')
def original(document_id: str,service: Service,user: User):
    doc=service.get_document(user,document_id)
    path=service.db.document_path(doc)
    if not path.exists():
        raise HTTPException(404,'原文件已不存在。')
    return FileResponse(path,filename=doc['filename'])


class CompareBody(BaseModel):
    document_ids: list[str] = Field(min_length=2, max_length=4)
    query: str = Field(default='', max_length=400)
    session_id: str | None = None


class BookmarkBody(BaseModel):
    document_id: str = Field(min_length=1, max_length=64)
    chunk_id: str | None = None
    note: str = Field(default='', max_length=500)


@router.post('/compare')
def compare(body: CompareBody, service: Service, user: User):
    try:
        result=service.compare_documents(user,body.document_ids,body.query)
        session_id=body.session_id or service.ensure_session(user,'比较资料')
        service.set_context(user,session_id,body.document_ids,topic=body.query or '比较所选资料')
        return service.record_exchange(user,body.query or '比较所选资料',result['answer'],session_id,result)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get('/bookmarks')
def bookmarks(service: Service, user: User):
    return service.list_bookmarks(user)


@router.post('/bookmarks', status_code=201)
def create_bookmark(body: BookmarkBody, service: Service, user: User):
    return service.add_bookmark(user, body.document_id, body.chunk_id, body.note)


@router.delete('/bookmarks/{bookmark_id}', status_code=204)
def remove_bookmark(bookmark_id: str, service: Service, user: User):
    service.delete_bookmark(user, bookmark_id)

@router.post('/search')
def search(body: Query,service: Service,user: User):
    return {'sources':service.search(user,body.query,body.document_ids,body.k)}

@router.post('/chat')
def chat(body: Question,service: Service,user: User):
    return service.answer(user,body.question,body.session_id,body.document_ids if 'document_ids' in body.model_fields_set else UNSET)

@router.get('/sessions')
def sessions(service: Service,user: User):
    return service.list_sessions(user)

@router.get('/sessions/{session_id}/messages')
def messages(session_id: str,service: Service,user: User):
    service.get_session(user,session_id)
    return service.db.messages(user,session_id)

@router.delete('/sessions/{session_id}',status_code=204)
def delete_session(session_id: str,service: Service,user: User):
    service.delete_session(user,session_id)

@router.get('/preferences')
def preferences(service: Service,user: User):
    return service.preferences(user)

@router.put('/preferences')
def save_preferences(body: Preferences,service: Service,user: User):
    return service.save_preferences(user,body.values)

@router.get('/memories')
def memories(service: Service,user: User):
    return service.memories(user)

@router.post('/memories',status_code=201)
def save_memory(body: Memory,service: Service,user: User):
    return service.remember(user,body.key,body.content,body.tags)

@router.delete('/memories/{memory_id}',status_code=204)
def forget(memory_id: str,service: Service,user: User):
    service.delete_memory(user,memory_id)

@router.post('/memories/search')
def search_memories(body: Query,service: Service,user: User):
    return service.search_memories(user,body.query,body.k)


class SessionContextUpdate(BaseModel):
    document_ids: list[str] | None = Field(default=None,max_length=100)

@router.get('/sessions/{session_id}/context')
def session_context(session_id: str,service: Service,user: User):
    return service.context(user,session_id)

@router.put('/sessions/{session_id}/context')
def update_session_context(session_id: str,body: SessionContextUpdate,service: Service,user: User):
    return service.set_context(user,session_id,body.document_ids)
