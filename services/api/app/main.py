import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .agent.service import StudyAgent
from .database import store

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    with store.connect():
        pass
    yield

app = FastAPI(title='AI Learning Companion API', version='0.2.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173', 'null'], allow_methods=['GET', 'POST', 'PATCH', 'PUT'], allow_headers=['Content-Type'])
agent = StudyAgent(store.connect)

class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)

class TaskUpdate(BaseModel):
    done: bool

class PreferenceInput(BaseModel):
    value: str = Field(max_length=100)

@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok', 'agent_mode': agent.mode}

@app.get('/tasks')
def tasks() -> list[dict]:
    with store.connect() as db:
        return store.list_tasks(db)

@app.post('/tasks', status_code=201)
def create_task(item: TaskInput) -> dict:
    if not item.title.strip():
        raise HTTPException(422, 'Task title cannot be blank')
    with store.connect() as db:
        return store.add_task(db, item.title.strip())

@app.patch('/tasks/{task_id}')
def update_task(task_id: int, item: TaskUpdate) -> dict:
    with store.connect() as db:
        if not store.set_task_done(db, task_id, item.done):
            raise HTTPException(404, 'Task not found')
    return {'id': task_id, 'done': item.done}

@app.get('/preferences/{key}')
def get_preference(key: str) -> dict:
    if key not in {'pet_name'}:
        raise HTTPException(404, 'Unknown preference')
    with store.connect() as db:
        return {'key': key, 'value': store.get_preference(db, key, '小鲸')}

@app.put('/preferences/{key}')
def update_preference(key: str, item: PreferenceInput) -> dict:
    if key not in {'pet_name'}:
        raise HTTPException(404, 'Unknown preference')
    with store.connect() as db:
        store.set_preference(db, key, item.value)
    return {'key': key, 'value': item.value}

@app.websocket('/ws/chat')
async def chat(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({'type': 'welcome', 'text': '你好！我们开始学习吧。', 'state': 'idle', 'mode': agent.mode})
    try:
        while True:
            try:
                event = await websocket.receive_json()
            except ValueError:
                await websocket.send_json({'type': 'error', 'text': '消息必须是 JSON。', 'state': 'error'})
                continue
            if not isinstance(event, dict) or event.get('type') != 'message' or not isinstance(event.get('text'), str) or not event['text'].strip() or len(event['text']) > 4000:
                await websocket.send_json({'type': 'error', 'text': '请发送 1–4000 字的 message.text。', 'state': 'error'})
                continue
            text = event['text'].strip()
            await websocket.send_json({'type': 'status', 'text': '正在思考', 'state': 'thinking'})
            try:
                with store.connect() as db:
                    history = store.recent_messages(db)
                reply = await agent.respond(text, history)
                with store.connect() as db:
                    store.add_message(db, 'user', text)
                    store.add_message(db, 'assistant', reply)
                await websocket.send_json({'type': 'reply', 'text': reply, 'state': 'success'})
            except Exception:
                logger.exception('Agent request failed')
                await websocket.send_json({'type': 'error', 'text': '处理失败，请检查模型配置后重试。', 'state': 'error'})
    except WebSocketDisconnect:
        pass
