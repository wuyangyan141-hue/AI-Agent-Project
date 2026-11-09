import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .agent.service import StudyAgent
from .database import store
from .skills.replan import propose_replan
from .skills.study_plan import make_study_plan
from .skills.review_session import begin_review, evaluate_review

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
    estimated_minutes: int = Field(default=30, ge=5, le=240)

class TaskUpdate(BaseModel):
    done: bool | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    estimated_minutes: int | None = Field(default=None, ge=5, le=240)

class PreferenceInput(BaseModel):
    value: str = Field(max_length=100)

class ReplanInput(BaseModel):
    days: int = Field(ge=1, le=14)
    minutes_per_day: int = Field(ge=15, le=240)

class PlanInput(BaseModel):
    goal: str = Field(min_length=1, max_length=200)
    days: int = Field(default=3, ge=1, le=14)
    minutes_per_day: int = Field(default=45, ge=15, le=240)

class FocusInput(BaseModel):
    task_id: int | None = None
    minutes: int = Field(default=25, ge=1, le=240)

class ReviewInput(BaseModel):
    topic: str = Field(min_length=1, max_length=200)

class ReviewAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)

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
        return store.add_task(db, item.title.strip(), item.estimated_minutes)

@app.patch('/tasks/{task_id}')
def update_task(task_id: int, item: TaskUpdate) -> dict:
    with store.connect() as db:
        result = store.edit_task(db, task_id, item.title.strip() if item.title else None, item.estimated_minutes, item.done)
        if result is None:
            raise HTTPException(404, 'Task not found')
    return result

@app.post('/plans/drafts', status_code=201)
def create_plan_draft(item: PlanInput) -> dict:
    try:
        steps = [step.__dict__ for step in make_study_plan(item.goal, item.days, item.minutes_per_day)]
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with store.connect() as db:
        return store.save_plan_draft(db, {'goal': item.goal.strip(), 'steps': steps})

@app.post('/plans/drafts/{draft_id}/confirm')
def confirm_plan(draft_id: int) -> dict:
    with store.connect() as db:
        result = store.apply_plan_draft(db, draft_id)
    if result is None:
        raise HTTPException(409, 'Draft missing or already applied')
    return result

@app.post('/focus', status_code=201)
def start_focus(item: FocusInput) -> dict:
    with store.connect() as db:
        try:
            result = store.start_focus(db, item.task_id, item.minutes)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
    if result is None:
        raise HTTPException(404, 'Task not found')
    return result

@app.get('/focus')
def get_focus() -> dict:
    with store.connect() as db:
        return store.focus_status(db) or {'remaining_seconds': 0, 'id': None}

@app.post('/focus/{session_id}/finish')
def stop_focus(session_id: int) -> dict:
    with store.connect() as db:
        if not store.finish_focus(db, session_id):
            raise HTTPException(404, 'Active session not found')
    return {'id': session_id, 'finished': True}

@app.post('/reviews', status_code=201)
def start_review(item: ReviewInput) -> dict:
    review = begin_review(item.topic)
    with store.connect() as db:
        cursor = db.execute('INSERT INTO review_sessions(topic, question) VALUES (?, ?)', (review['topic'], review['question']))
        db.commit()
    return {'id': cursor.lastrowid, **review, 'status': 'waiting'}

@app.post('/reviews/{review_id}/answer')
def answer_review(review_id: int, item: ReviewAnswer) -> dict:
    with store.connect() as db:
        row = db.execute('SELECT topic, status FROM review_sessions WHERE id=?', (review_id,)).fetchone()
        if row is None or row['status'] != 'waiting':
            raise HTTPException(409, 'Review missing or already answered')
        result = evaluate_review(row['topic'], item.answer)
        db.execute('UPDATE review_sessions SET answer=?, feedback=?, status=? WHERE id=?',
                   (item.answer, result['feedback'], result['result'], review_id))
        db.commit()
    return {'id': review_id, **result}

@app.post('/plans/replan-drafts', status_code=201)
def create_replan_draft(request: ReplanInput) -> dict:
    with store.connect() as db:
        try:
            proposal = propose_replan(store.list_tasks(db), request.days, request.minutes_per_day)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return store.save_replan_draft(db, proposal)

@app.post('/plans/replan-drafts/{draft_id}/confirm')
def confirm_replan(draft_id: int) -> dict:
    with store.connect() as db:
        result = store.apply_replan_draft(db, draft_id)
    if result is None:
        raise HTTPException(409, 'Draft missing, already applied, or tasks changed')
    return result

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
                async def emit(state: str, message: str) -> None:
                    await websocket.send_json({'type': 'status', 'text': message, 'state': state})
                reply = await asyncio.wait_for(agent.respond(text, history, emit), timeout=45)
                with store.connect() as db:
                    store.add_message(db, 'user', text)
                    store.add_message(db, 'assistant', reply)
                await websocket.send_json({'type': 'reply', 'text': reply, 'state': 'success'})
            except asyncio.TimeoutError:
                await websocket.send_json({'type': 'error', 'text': '模型响应超时，请稍后重试。', 'state': 'error'})
            except Exception:
                logger.exception('Agent request failed')
                await websocket.send_json({'type': 'error', 'text': '处理失败，请检查模型配置后重试。', 'state': 'error'})
    except WebSocketDisconnect:
        pass
