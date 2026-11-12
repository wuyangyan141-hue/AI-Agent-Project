import logging
import asyncio
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from .agent.service import StudyAgent
from .database import store
from .skills.replan import propose_replan
from .skills.review_session import begin_review, daily_quiz, evaluate_review, weak_point_review
from .skills.learning_loop import format_next_step, mark_study_activity, next_step
from .knowledge.api import router as knowledge_router
from .knowledge.documents import DocumentError
from .knowledge.integration import get_knowledge
from .knowledge.config import Settings
from .agent.intent import StudyIntent, explicit_intent

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    with store.connect():
        pass
    yield

app = FastAPI(title='AI Learning Companion API', version='0.3.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173', 'null'], allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'], allow_headers=['Content-Type','X-User-Id'])
app.include_router(knowledge_router)

@app.exception_handler(DocumentError)
async def invalid_document(request, exc):
    return JSONResponse(status_code=422,content={'detail':str(exc)})

@app.exception_handler(KeyError)
async def missing_knowledge(request, exc):
    return JSONResponse(status_code=404,content={'detail':str(exc.args[0])})

Settings.from_env()  # Load the same ignored local configuration for both members.
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
async def create_plan_draft(item: PlanInput) -> dict:
    try:
        steps = [step.__dict__ for step in await asyncio.wait_for(agent.generate_plan(item.goal, item.days, item.minutes_per_day), timeout=45)]
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, 'Plan generation timed out') from exc
    except Exception as exc:
        logger.exception('Plan generation failed')
        raise HTTPException(503, 'Plan generation failed; check model configuration') from exc
    with store.connect() as db:
        return store.save_plan_draft(db, {'goal': item.goal.strip(), 'steps': steps})

@app.post('/plans/drafts/{draft_id}/confirm')
def confirm_plan(draft_id: int) -> dict:
    with store.connect() as db:
        result = store.apply_plan_draft(db, draft_id)
    if result is None:
        raise HTTPException(409, 'Draft missing or already applied')
    return {**result, 'next_step': next_step('plan')}

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
        status = store.focus_status(db)
        minutes = int((status or {}).get('duration_minutes') or 0) if status and status.get('id') == session_id else 0
        if not store.finish_focus(db, session_id):
            raise HTTPException(404, 'Active session not found')
    streak = mark_study_activity(minutes)
    step = next_step('focus')
    return {'id': session_id, 'finished': True, 'streak': streak, 'next_step': step}

@app.post('/reviews', status_code=201)
def start_review(item: ReviewInput) -> dict:
    review = begin_review(item.topic)
    with store.connect() as db:
        cursor = db.execute('INSERT INTO review_sessions(topic, question) VALUES (?, ?)', (review['topic'], review['question']))
        db.commit()
    return {'id': cursor.lastrowid, **review, 'status': 'waiting'}

@app.post('/reviews/daily-quiz', status_code=201)
def start_daily_quiz() -> dict:
    quiz = daily_quiz()
    created = []
    with store.connect() as db:
        for item in quiz['items']:
            cursor = db.execute(
                'INSERT INTO review_sessions(topic, question) VALUES (?, ?)',
                (item['topic'], item['question']),
            )
            created.append({'id': cursor.lastrowid, **item, 'status': 'waiting'})
        db.commit()
    return {**quiz, 'items': created, 'next_step': next_step('review')}

@app.post('/reviews/weak-point', status_code=201)
def start_weak_point() -> dict:
    with store.connect() as db:
        rows = [dict(row) for row in db.execute(
            'SELECT topic, status FROM review_sessions ORDER BY id DESC LIMIT 20'
        ).fetchall()]
    review = weak_point_review(rows)
    with store.connect() as db:
        cursor = db.execute(
            'INSERT INTO review_sessions(topic, question) VALUES (?, ?)',
            (review['topic'], review['question']),
        )
        db.commit()
    return {'id': cursor.lastrowid, **review, 'status': 'waiting', 'next_step': next_step('review')}

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
    streak = mark_study_activity(0)
    return {'id': review_id, **result, 'streak': streak, 'next_step': next_step('review')}

@app.get('/learning/next-step')
def learning_next_step(after: str | None = None) -> dict:
    return next_step(after)

@app.get('/learning/streak')
def learning_streak() -> dict:
    with store.connect() as db:
        from .skills.learning_loop import ensure_streak
        return ensure_streak(db)

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
        return {'key': key, 'value': store.get_preference(db, key, '豆豆')}

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
    pending_plan = None
    active_session_id = None
    coach = next_step()
    welcome = '你好！我是你的学习伙伴。\n' + format_next_step(coach)
    await websocket.send_json({
        'type': 'welcome', 'text': welcome, 'state': 'idle', 'mode': agent.mode, 'next_step': coach,
    })
    try:
        while True:
            try:
                event = await websocket.receive_json()
            except ValueError:
                await websocket.send_json({'type': 'error', 'text': '消息必须是 JSON。', 'state': 'error'})
                continue
            if isinstance(event, dict) and event.get('type') == 'plan_request':
                try:
                    pending_plan = None
                    requested_session = event.get('session_id',active_session_id)
                    if requested_session is not None:
                        get_knowledge().get_session('local-user',requested_session)
                    request = PlanInput.model_validate(event.get('payload'))
                    await websocket.send_json({'type': 'status', 'text': '正在生成计划草稿', 'state': 'thinking'})
                    steps = [step.__dict__ for step in await asyncio.wait_for(agent.generate_plan(request.goal, request.days, request.minutes_per_day), timeout=45)]
                    with store.connect() as db:
                        draft = store.save_plan_draft(db, {'goal': request.goal.strip(), 'steps': steps})
                    saved = get_knowledge().record_exchange('local-user',f'制定计划：{request.goal}','计划草稿已生成，请检查并确认。',requested_session,{'draft':draft,'kind':'plan'})
                    active_session_id = saved['session_id']
                    await websocket.send_json({'type': 'plan_draft', 'text': saved['answer'], 'state': 'success', 'draft': draft,'session_id':saved['session_id']})
                except (ValueError, TypeError):
                    await websocket.send_json({'type': 'error', 'text': '请提供目标、1–14 天和每天 15–240 分钟。', 'state': 'error'})
                except asyncio.TimeoutError:
                    await websocket.send_json({'type': 'error', 'text': '计划生成超时，请重试。', 'state': 'error'})
                except Exception:
                    logger.exception('Plan generation failed')
                    await websocket.send_json({'type': 'error', 'text': '计划生成失败，请检查模型配置。', 'state': 'error'})
                continue
            if not isinstance(event, dict) or event.get('type') != 'message' or not isinstance(event.get('text'), str) or not event['text'].strip() or len(event['text']) > 4000:
                await websocket.send_json({'type': 'error', 'text': '请发送 1–4000 字的 message.text。', 'state': 'error'})
                continue
            text = event['text'].strip()
            await websocket.send_json({'type': 'status', 'text': '正在思考', 'state': 'thinking'})
            try:
                knowledge = get_knowledge()
                session_id = event.get('session_id',active_session_id)
                if session_id != active_session_id:
                    pending_plan = None
                active_session_id = session_id
                if session_id is not None and (not isinstance(session_id,str) or not re.fullmatch(r'[a-f0-9]{32}',session_id)):
                    raise ValueError('对话标识无效，请开启新对话。')
                document_ids = event.get('document_ids')
                if document_ids is not None and (not isinstance(document_ids,list) or len(document_ids)>100 or any(not isinstance(item,str) for item in document_ids)):
                    raise ValueError('资料选择无效。')
                personal = knowledge.is_personal_request(text)
                if session_id:
                    knowledge.get_session('local-user',session_id)
                    saved_messages = knowledge.db.messages('local-user',session_id)[-12:]
                    history = [{'role':m['role'],'content':m['content']} for m in saved_messages]
                    if pending_plan is None and saved_messages and saved_messages[-1]['metadata'].get('pending_plan'):
                        pending_plan = StudyIntent.model_validate(saved_messages[-1]['metadata']['pending_plan'])
                else:
                    history = []
                async def emit(state: str, message: str) -> None:
                    await websocket.send_json({'type': 'status', 'text': message, 'state': state})
                # Open review session: treat normal chat as the answer (don't restart the same topic).
                waiting = None
                with store.connect() as db:
                    row = db.execute(
                        "SELECT id, topic, question FROM review_sessions WHERE status='waiting' ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    if row:
                        waiting = dict(row)
                intent_preview = explicit_intent(text)
                answering_echo = bool(re.search(r'我来回答|直接作答|提交答案', text))
                social = text.strip('！!。,.，?？ ~～') in {
                    '你好', '嗨', 'hi', 'hello', '在吗', '早上好', '晚上好', '下午好',
                    '谢谢', '谢谢你', '拜拜', '再见', '嗯', '好的', '好', 'ok', 'OK',
                }
                skip_review = bool(re.search(r'跳过(这题|本题|复习)?|取消复习|先不答|下次再答', text))
                if waiting and skip_review:
                    with store.connect() as db:
                        db.execute(
                            "UPDATE review_sessions SET status=?, feedback=? WHERE id=?",
                            ('skipped', '用户跳过本题', waiting['id']),
                        )
                        db.commit()
                    coach = next_step()
                    answer = '好，这题先跳过。\n' + format_next_step(coach)
                    saved = knowledge.record_exchange('local-user', text, answer, session_id, {
                        'review': {'id': waiting['id'], 'status': 'skipped'}, 'next_step': coach,
                    })
                    active_session_id = saved['session_id']
                    await websocket.send_json({
                        'type': 'reply', 'text': saved['answer'], 'state': 'success',
                        'session_id': saved['session_id'], 'next_step': coach,
                    })
                    continue
                # New quiz/review/plan commands win over grading the pending answer.
                if waiting and intent_preview.action in {'quiz', 'review', 'weak', 'plan', 'replan', 'focus'}:
                    with store.connect() as db:
                        db.execute(
                            "UPDATE review_sessions SET status=?, feedback=? WHERE id=? AND status=?",
                            ('skipped', '被新的学习请求替换', waiting['id'], 'waiting'),
                        )
                        db.commit()
                    waiting = None
                # Greetings / short social chat should not be graded as review answers.
                if waiting and intent_preview.action in {'chat', 'next'} and not personal and not social:
                    if answering_echo:
                        coach = next_step('review')
                        answer = (
                            f'题目还在等你：{waiting["question"]}\n'
                            f'主题：{waiting["topic"]}。请直接输入你的理解或例子；'
                            f'闲聊可以说「你好」，跳过可以说「跳过这题」。\n'
                            + format_next_step(coach)
                        )
                        saved = knowledge.record_exchange('local-user', text, answer, session_id, {
                            'review': waiting, 'next_step': coach,
                        })
                        active_session_id = saved['session_id']
                        await websocket.send_json({
                            'type': 'reply', 'text': saved['answer'], 'state': 'idle',
                            'session_id': saved['session_id'], 'next_step': coach,
                        })
                        continue
                    await emit('tool', '正在批改复习题')
                    result = evaluate_review(waiting['topic'], text)
                    with store.connect() as db:
                        db.execute(
                            'UPDATE review_sessions SET answer=?, feedback=?, status=? WHERE id=?',
                            (text, result['feedback'], result['result'], waiting['id']),
                        )
                        db.commit()
                    streak = mark_study_activity(0)
                    coach = next_step('review')
                    score = result.get('score')
                    verdict = result.get('verdict') or result.get('result')
                    score_line = f'判定：{verdict}' + (f'（{score} 分）' if score is not None else '')
                    answer = (
                        f'{score_line}\n{result["feedback"]}\n' + format_next_step(coach)
                    )
                    saved = knowledge.record_exchange('local-user', text, answer, session_id, {
                        'review': {'id': waiting['id'], **result}, 'next_step': coach, 'streak': streak,
                    })
                    active_session_id = saved['session_id']
                    await websocket.send_json({
                        'type': 'reply', 'text': saved['answer'], 'state': 'success',
                        'session_id': saved['session_id'], 'next_step': coach, 'streak': streak,
                    })
                    continue
                if pending_plan is not None:
                    intent = pending_plan.model_copy(update={'goal': text[:200]})
                    pending_plan = None
                else:
                    if (personal or event.get('knowledge') is True) and explicit_intent(text).action=='chat':
                        intent = StudyIntent()
                    else:
                        intent = await asyncio.wait_for(agent.detect_intent(text, history), timeout=25)
                # Starting "复习" while one is waiting → remind instead of spawning duplicates.
                if intent.action == 'review' and waiting:
                    coach = next_step('review')
                    answer = (
                        f'上一题还没答完：{waiting["question"]}\n'
                        f'请先作答（主题：{waiting["topic"]}），答完再说「开始复习」出下一题。\n'
                        + format_next_step(coach)
                    )
                    saved = knowledge.record_exchange('local-user', text, answer, session_id, {
                        'review': waiting, 'next_step': coach,
                    })
                    active_session_id = saved['session_id']
                    await websocket.send_json({
                        'type': 'reply', 'text': saved['answer'], 'state': 'idle',
                        'session_id': saved['session_id'], 'next_step': coach,
                    })
                    continue
                if intent.action in {'plan', 'replan'}:
                    if intent.action == 'plan' and not intent.goal.strip():
                        pending_plan = intent
                        saved = knowledge.record_exchange('local-user',text,'想学习什么内容？请告诉我学习目标。',session_id,{'pending_plan':intent.model_dump()})
                        active_session_id = saved['session_id']
                        await websocket.send_json({'type': 'reply', 'text': saved['answer'], 'state': 'idle','session_id':saved['session_id']})
                        continue
                    await emit('tool', '正在调用学习工作流：' + ('study_plan' if intent.action == 'plan' else 'replan'))
                    if intent.action == 'plan':
                        steps = [step.__dict__ for step in await asyncio.wait_for(agent.generate_plan(intent.goal, intent.days, intent.minutes_per_day), timeout=45)]
                    with store.connect() as db:
                        if intent.action == 'plan':
                            draft = store.save_plan_draft(db, {'goal': intent.goal.strip(), 'steps': steps})
                            kind = 'plan'
                        else:
                            proposal = propose_replan(store.list_tasks(db), intent.days, intent.minutes_per_day)
                            draft = store.save_replan_draft(db, proposal)
                            kind = 'replan'
                        store.add_message(db, 'user', text)
                        store.add_message(db, 'assistant', '已生成待确认的' + ('学习计划' if kind == 'plan' else '任务重排') + '草稿。')
                    coach = next_step('plan')
                    answer = '草稿已生成，请检查后确认。确认后我会提醒你开始专注。\n' + format_next_step(coach)
                    saved = knowledge.record_exchange('local-user',text,answer,session_id,{'draft':draft,'kind':kind,'next_step':coach})
                    active_session_id = saved['session_id']
                    await websocket.send_json({'type': 'plan_draft', 'text': saved['answer'], 'state': 'success', 'draft': draft, 'kind': kind,'session_id':saved['session_id'],'next_step':coach})
                    continue
                if intent.action == 'focus':
                    await emit('tool', '正在开始专注计时')
                    with store.connect() as db:
                        try:
                            focus = store.start_focus(db, None, intent.minutes)
                        except ValueError as exc:
                            raise ValueError(str(exc)) from exc
                    coach = next_step('focus')
                    answer = f'已开始 {intent.minutes} 分钟专注。加油～\n' + format_next_step(coach)
                    saved = knowledge.record_exchange('local-user',text,answer,session_id,{'focus':focus,'next_step':coach})
                    active_session_id = saved['session_id']
                    await websocket.send_json({'type':'reply','text':saved['answer'],'state':'success','session_id':saved['session_id'],'next_step':coach,'focus':focus})
                    continue
                if intent.action in {'review', 'quiz', 'weak'}:
                    await emit('tool', '正在准备复习')
                    with store.connect() as db:
                        history_rows = [dict(row) for row in db.execute(
                            'SELECT topic, status FROM review_sessions ORDER BY id DESC LIMIT 20'
                        ).fetchall()]
                    if intent.action == 'quiz':
                        payload = daily_quiz()
                        created = []
                        with store.connect() as db:
                            for item in payload['items']:
                                cursor = db.execute(
                                    'INSERT INTO review_sessions(topic, question) VALUES (?, ?)',
                                    (item['topic'], item['question']),
                                )
                                created.append({'id': cursor.lastrowid, **item})
                            db.commit()
                        first = created[0]
                        answer = f'今日小测共 {len(created)} 题。先看第一题：\n{first["question"]}\n主题：{first["topic"]}'
                        meta = {'review': first, 'quiz': created, 'next_step': next_step('review')}
                    elif intent.action == 'weak':
                        review = weak_point_review(history_rows)
                        with store.connect() as db:
                            cursor = db.execute(
                                'INSERT INTO review_sessions(topic, question) VALUES (?, ?)',
                                (review['topic'], review['question']),
                            )
                            db.commit()
                        answer = f'{review.get("hint","")}\n{review["question"]}\n主题：{review["topic"]}'
                        meta = {'review': {'id': cursor.lastrowid, **review}, 'next_step': next_step('review')}
                    else:
                        review = begin_review(intent.topic or '今日重点')
                        with store.connect() as db:
                            cursor = db.execute(
                                'INSERT INTO review_sessions(topic, question) VALUES (?, ?)',
                                (review['topic'], review['question']),
                            )
                            db.commit()
                        answer = f'{review["question"]}\n主题：{review["topic"]}。直接在聊天里作答即可。'
                        meta = {'review': {'id': cursor.lastrowid, **review, 'status': 'waiting'}, 'next_step': next_step('review')}
                    answer = answer + '\n' + format_next_step(meta['next_step'])
                    saved = knowledge.record_exchange('local-user',text,answer,session_id,meta)
                    active_session_id = saved['session_id']
                    await websocket.send_json({'type':'reply','text':saved['answer'],'state':'success','session_id':saved['session_id'],'next_step':meta['next_step']})
                    continue
                if intent.action == 'next':
                    coach = next_step()
                    answer = format_next_step(coach)
                    saved = knowledge.record_exchange('local-user',text,answer,session_id,{'next_step':coach})
                    active_session_id = saved['session_id']
                    await websocket.send_json({'type':'reply','text':saved['answer'],'state':'success','session_id':saved['session_id'],'next_step':coach})
                    continue
                has_documents = any(d['status']=='ready' and not d['needs_reindex'] for d in knowledge.list_documents('local-user'))
                greeting = text.strip('！!。,.，?？ ') in {'你好','嗨','hi','hello','谢谢','谢谢你'}
                if personal or event.get('knowledge') is True or (has_documents and not greeting):
                    await emit('searching','正在查阅知识库和相关记忆')
                    result = await asyncio.wait_for(run_in_threadpool(knowledge.answer,'local-user',text,session_id,document_ids),timeout=60)
                    active_session_id = result['session_id']
                    after = 'overview' if result.get('mode') == 'overview' else 'ask'
                    coach = next_step(after)
                    text_out = result['answer']
                    if '👉 下一步' not in text_out:
                        text_out = text_out + '\n\n' + format_next_step(coach)
                    with store.connect() as db:
                        store.add_message(db,'user',text)
                        store.add_message(db,'assistant',text_out)
                    await websocket.send_json({'type':'reply','text':text_out,'state':'success',
                        'session_id':result['session_id'],'sources':result['sources'],'answer_mode':result['mode'],
                        'warning':result['warning'],'memories_used':result['memories_used'],'preferences_used':result['preferences_used'],
                        'next_step':coach,'overview':result.get('overview')})
                    continue
                reply = await asyncio.wait_for(agent.respond(text, history, emit), timeout=45)
                coach = next_step()
                if '👉 下一步' not in reply:
                    reply = reply + '\n\n' + format_next_step(coach)
                with store.connect() as db:
                    store.add_message(db, 'user', text)
                    store.add_message(db, 'assistant', reply)
                saved = knowledge.record_exchange('local-user',text,reply,session_id,{'next_step':coach})
                active_session_id = saved['session_id']
                await websocket.send_json({'type': 'reply', 'text': reply, 'state': 'success','session_id':saved['session_id'],'next_step':coach})
            except asyncio.TimeoutError:
                await websocket.send_json({'type': 'error', 'text': '模型响应超时，请稍后重试。', 'state': 'error'})
            except ValueError as exc:
                await websocket.send_json({'type': 'error', 'text': str(exc), 'state': 'error'})
            except Exception:
                logger.exception('Agent request failed')
                await websocket.send_json({'type': 'error', 'text': '处理失败，请检查模型配置后重试。', 'state': 'error'})
    except WebSocketDisconnect:
        pass
