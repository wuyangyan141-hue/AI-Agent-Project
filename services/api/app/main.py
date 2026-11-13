import logging
import os
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
from .skills.review_session import begin_review, daily_quiz, evaluate_review, weak_point_review, save_review, public_review, grade_saved_review
from .skills.learning_loop import format_next_step, mark_study_activity, next_step, today_plan
from .knowledge.api import router as knowledge_router
from .knowledge.documents import DocumentError
from .knowledge.integration import get_knowledge
from .knowledge.config import Settings
from .knowledge.service import UNSET
from .knowledge.routing import route_request, SOCIAL, QUESTION
from .knowledge.storage import uid
from .agent.intent import StudyIntent, explicit_intent
from .agent.dispatch import classify_explicit, resolve_turn
from .runtime_llm import apply_runtime, public_config, save_config

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    with store.connect():
        pass
    yield

app = FastAPI(title='AI Learning Companion API', version='0.4.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('FRONTEND_ORIGINS','http://127.0.0.1:5173,http://localhost:5173,null').split(','), allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'], allow_headers=['Content-Type','X-User-Id'])
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
    document_ids: list[str] | None = Field(default=None,max_length=4)
    session_id: str | None = None

class FocusInput(BaseModel):
    task_id: int | None = None
    minutes: float = Field(default=25, gt=0, le=240)
    seconds: int | None = Field(default=None, ge=1, le=14400)

class ReviewInput(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    document_ids: list[str] | None = Field(default=None,max_length=4)
    session_id: str | None = None

class ReviewScope(BaseModel):
    document_ids: list[str] | None = Field(default=None,max_length=4)
    session_id: str | None = None

class ReviewAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)

class LlmSettingsInput(BaseModel):
    mode: str | None = Field(default=None, pattern='^(offline|online)$')
    provider: str | None = Field(default=None, max_length=40)
    llm_model: str | None = Field(default=None, max_length=120)
    llm_api_key: str | None = Field(default=None, max_length=200)
    llm_base_url: str | None = Field(default=None, max_length=300)

@app.get('/health')
def health() -> dict:
    cfg = public_config()
    return {
        'status': 'ok',
        'agent_mode': agent.mode,
        'llm_mode': cfg['mode'],
        'online_ready': cfg['online_ready'],
        'version': '0.4.0',
        'protocol_version': 2,
    }

@app.get('/settings/llm')
def get_llm_settings() -> dict:
    return public_config()

@app.put('/settings/llm')
def update_llm_settings(item: LlmSettingsInput) -> dict:
    try:
        save_config(item.model_dump(exclude_unset=True))
        return apply_runtime(agent)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get('/tasks')
def tasks() -> list[dict]:
    with store.connect() as db:
        return store.list_tasks(db)

@app.get('/tasks/trash')
def trashed_tasks() -> list[dict]:
    with store.connect() as db:
        return store.list_trashed_tasks(db)

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

@app.delete('/tasks/{task_id}')
def delete_task(task_id: int) -> dict:
    with store.connect() as db:
        result = store.soft_delete_task(db, task_id)
        if result is None:
            raise HTTPException(404, 'Task not found')
    return {'deleted': True, 'task': result}

@app.post('/tasks/{task_id}/restore')
def restore_task(task_id: int) -> dict:
    with store.connect() as db:
        result = store.restore_task(db, task_id)
        if result is None:
            raise HTTPException(404, 'Trashed task not found')
    return result

@app.delete('/tasks/{task_id}/purge')
def purge_task(task_id: int) -> dict:
    with store.connect() as db:
        if not store.purge_task(db, task_id):
            raise HTTPException(404, 'Trashed task not found')
    return {'purged': True, 'id': task_id}

@app.post('/plans/drafts', status_code=201)
async def create_plan_draft(item: PlanInput) -> dict:
    try:
        knowledge=get_knowledge()
        ids=knowledge.resolve_scope('local-user',item.session_id,item.document_ids if 'document_ids' in item.model_fields_set else UNSET)
        materials=await run_in_threadpool(knowledge.learning_context,'local-user',item.goal,ids)
        steps = [step.__dict__ for step in await asyncio.wait_for(agent.generate_plan(item.goal, item.days, item.minutes_per_day,material_context=materials), timeout=45)]
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, 'Plan generation timed out') from exc
    except Exception as exc:
        logger.exception('Plan generation failed')
        raise HTTPException(503, 'Plan generation failed; check model configuration') from exc
    with store.connect() as db:
        return store.save_plan_draft(db, {'goal': item.goal.strip(), 'steps': steps,'sources':materials['sources'],'document_ids':materials['document_ids']})

@app.post('/plans/drafts/{draft_id}/confirm')
def confirm_plan(draft_id: int, replace_open: bool = False) -> dict:
    """Apply a draft; optionally soft-delete unfinished tasks first (for 三选一换套)."""
    with store.connect() as db:
        if replace_open:
            for task in store.list_tasks(db):
                if not task.get('done'):
                    store.soft_delete_task(db, int(task['id']))
        result = store.apply_plan_draft(db, draft_id)
    if result is None:
        raise HTTPException(409, 'Draft missing or already applied')
    agenda = today_plan()
    return {**result, 'today_plan': agenda, 'next_step': agenda.get('next_step') or next_step('plan')}

@app.post('/focus', status_code=201)
def start_focus(item: FocusInput) -> dict:
    duration = (item.seconds / 60.0) if item.seconds else float(item.minutes)
    with store.connect() as db:
        try:
            result = store.start_focus(db, item.task_id, duration)
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
    """End focus; if linked to a task, mark it done and award bones once."""
    with store.connect() as db:
        status = store.focus_status(db)
        if not status or status.get('id') != session_id:
            raise HTTPException(404, 'Active session not found')
        minutes = float(status.get('duration_minutes') or 0)
        task_id = status.get('task_id')
        task_title = status.get('task_title')
        if not store.finish_focus(db, session_id):
            raise HTTPException(404, 'Active session not found')
        reward = None
        task = None
        if task_id is not None:
            task = store.edit_task(db, int(task_id), None, None, True)
            if task is not None:
                reward = task.get('reward')
    streak = mark_study_activity(max(1, int(round(minutes))) if minutes else 0)
    step = next_step('focus')
    speech = (reward or {}).get('speech') if reward else None
    if not speech and task_id is not None:
        short = (task_title or '这项任务')[:18]
        speech = f'汪！「{short}」打卡完成，骨头到手啦～'
    if speech and task_id is not None:
        speech = f'{speech}\n要不要出一题巩固一下？'
    return {
        'id': session_id,
        'finished': True,
        'task_id': task_id,
        'task': task,
        'reward': reward,
        'speech': speech,
        'offer_review': bool(task_id is not None),
        'streak': streak,
        'next_step': step,
    }

def review_scope(item):
    knowledge=get_knowledge()
    return knowledge.resolve_scope('local-user',item.session_id,item.document_ids if 'document_ids' in item.model_fields_set else UNSET)

@app.post('/reviews',status_code=201)
def start_review(item: ReviewInput):
    # Single review defaults to short answer; daily quiz rotates objective/subjective types.
    review=begin_review(item.topic,document_ids=review_scope(item),preferred_type='short_answer')
    with store.connect() as db:
        return public_review(save_review(db,review,item.session_id))

@app.post('/reviews/daily-quiz',status_code=201)
def start_daily_quiz(item: ReviewScope | None = None):
    item=item or ReviewScope()
    quiz=daily_quiz(document_ids=review_scope(item))
    with store.connect() as db:
        created=[public_review(save_review(db,q,item.session_id)) for q in quiz['items']]
    return {**quiz,'items':created,'next_step':next_step('review')}

@app.post('/reviews/weak-point',status_code=201)
def start_weak_point(item: ReviewScope | None = None):
    item=item or ReviewScope()
    with store.connect() as db:
        rows=[dict(row) for row in db.execute('SELECT topic,status FROM review_sessions WHERE session_id IS ? ORDER BY id DESC LIMIT 20',(item.session_id,))]
    picked=weak_point_review(rows)
    review=begin_review(picked['topic'],document_ids=review_scope(item))
    with store.connect() as db:
        saved=public_review(save_review(db,review,item.session_id))
    return {**saved,'next_step':next_step('review')}

@app.post('/reviews/{review_id}/answer')
def answer_review(review_id: int,item: ReviewAnswer):
    try:
        with store.connect() as db:
            result=grade_saved_review(db,review_id,item.answer)
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    return {**result,'streak':mark_study_activity(0),'next_step':next_step('review')}

@app.get('/learning/next-step')
def learning_next_step(after: str | None = None) -> dict:
    return next_step(after)

@app.get('/learning/streak')
def learning_streak() -> dict:
    with store.connect() as db:
        from .skills.learning_loop import ensure_streak
        return ensure_streak(db)

@app.post('/learning/bones/feed')
def feed_pet_with_bones() -> dict:
    """Spend bones to feed the desk pet for a cheer."""
    from .skills.learning_loop import spend_bones_feed_pet
    try:
        return spend_bones_feed_pet()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

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

async def with_progress(awaitable, emit, text, timeout=600):
    task=asyncio.ensure_future(awaitable)
    loop=asyncio.get_running_loop(); deadline=loop.time()+timeout
    try:
        while not task.done():
            remaining=deadline-loop.time()
            if remaining<=0: raise asyncio.TimeoutError()
            await asyncio.wait({task},timeout=min(8,remaining))
            if not task.done(): await emit('searching',text)
        return await task
    finally:
        if not task.done():
            task.cancel()
            # Threaded chapter work may finish its cache entry after cancellation.

@app.websocket('/ws/chat')
async def chat(websocket: WebSocket):
    await websocket.accept()
    opening=next_step()
    # Keep welcome short for the pet bubble; details live in next_step for the panel card.
    title=(opening.get('title') or '').strip()
    welcome=f'你好，我是豆豆。{title}' if title else '你好，我是豆豆。今天想学一点什么？'
    if len(welcome)>48:
        welcome='你好，我是豆豆。'+((title[:18]+'…') if title else '今天想学一点什么？')
    await websocket.send_json({'type':'welcome','text':welcome,'state':'idle','mode':agent.mode,'next_step':opening})
    active_session_id=None
    try:
        while True:
            try: event=await websocket.receive_json()
            except ValueError:
                await websocket.send_json({'type':'error','text':'消息必须是 JSON。','state':'error'});continue
            request_id=event.get('request_id') if isinstance(event,dict) else None
            request_id=request_id if isinstance(request_id,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',request_id) else uid()
            async def emit(state,text):
                await websocket.send_json({'type':'status','text':text,'state':state,'request_id':request_id})
            if not isinstance(event,dict) or event.get('type') not in {'message','plan_request'}:
                await websocket.send_json({'type':'error','text':'无效消息类型。','state':'error','request_id':request_id});continue
            if event['type']=='message' and (not isinstance(event.get('text'),str) or not event['text'].strip() or len(event['text'])>4000):
                await websocket.send_json({'type':'error','text':'请发送1–4000字的消息。','state':'error','request_id':request_id});continue
            if event['type']=='plan_request':
                try: PlanInput.model_validate(event.get('payload'))
                except ValueError:
                    await websocket.send_json({'type':'error','text':'请提供目标、1–14天和每天15–240分钟。','state':'error','request_id':request_id});continue
            await emit('thinking','正在理解你的问题')
            try:
                knowledge=get_knowledge()
                requested=event.get('session_id',active_session_id)
                if requested is not None and (not isinstance(requested,str) or not re.fullmatch(r'[a-f0-9]{32}',requested)):
                    raise ValueError('对话标识无效，请开启新对话。')
                if requested: knowledge.get_session('local-user',requested)
                document_ids=event.get('document_ids',UNSET)
                if document_ids is not UNSET and document_ids is not None and (not isinstance(document_ids,list) or len(document_ids)>100 or any(not isinstance(x,str) for x in document_ids)):
                    raise ValueError('资料范围无效。')
                text=event.get('text','').strip() if event['type']=='message' else '制定学习计划'
                session_id=requested or knowledge.ensure_session('local-user',text)
                active_session_id=session_id
                ids=knowledge.resolve_scope('local-user',session_id,document_ids)
                context=knowledge.context('local-user',session_id)
                history_rows=knowledge.db.messages('local-user',session_id)[-12:]
                history=[{'role':m['role'],'content':m['content']} for m in history_rows]
                personal=knowledge.is_personal_request(text)
                ready=any(d['status']=='ready' and not d['needs_reindex'] for d in knowledge.list_documents('local-user'))
                general=event.get('general') is True
                # Only the explicit knowledge flag forces RAG; selected docs alone must not
                # turn “陪我学习” into a document Q&A.
                route=route_request(text,forced=event.get('knowledge') is True,general=general,
                                    has_documents=ready,active_topic=bool(context['topic']))
                direct=classify_explicit(text)
                pending=history_rows[-1]['metadata'].get('pending_plan') if history_rows else None
                if event['type']=='plan_request':
                    plan=PlanInput.model_validate(event.get('payload'))
                    intent=StudyIntent(action='plan',goal=plan.goal,days=plan.days,minutes_per_day=plan.minutes_per_day)
                elif pending and direct.action=='chat' and route=='chat' and not SOCIAL.search(text) and not QUESTION.search(text):
                    # Confusion is a request to explain, not a study-goal reply for pending plans.
                    from .knowledge.routing import CONFUSED
                    if CONFUSED.search(text):
                        intent=StudyIntent()
                        route='knowledge'
                    else:
                        intent=StudyIntent.model_validate(pending).model_copy(update={'goal':text[:200]})
                elif direct.action!='chat' or personal or route!='chat' or general:
                    intent=direct
                else:
                    intent=await asyncio.wait_for(agent.detect_intent(text,history),timeout=30)
                    # Model may keep picking "plan" after a draft; confusion must explain instead.
                    from .knowledge.routing import CONFUSED
                    if CONFUSED.search(text) and intent.action=='plan':
                        intent=StudyIntent()
                        route='knowledge'
                with store.connect() as db:
                    waiting=db.execute("SELECT * FROM review_sessions WHERE status='waiting' AND session_id=? ORDER BY id LIMIT 1",(session_id,)).fetchone()
                    waiting=dict(waiting) if waiting else None
                decision=resolve_turn(
                    text,
                    intent=intent,
                    route=route,
                    waiting=bool(waiting),
                    personal=personal,
                    pending_plan=bool(pending),
                    force_review_answer=event.get('review_answer') is True,
                    general=general,
                )
                intent=decision.intent
                saved=None;out_type='reply';extra={}
                # Infer preferences / 三类记忆 from natural chat, then keep preference_summary fresh.
                pref_inferred={'prefs':{},'memories':{},'notes':[]}
                try:
                    from .skills.preferences_loop import infer_from_utterance
                    if decision.kind not in {'review_answer','skip'} and not re.fullmatch(r'[A-Da-d]', text.strip()):
                        pref_inferred=await run_in_threadpool(infer_from_utterance, text, 'local-user')
                except Exception:
                    logger.exception('Preference inference failed')
                if decision.kind=='skip' and waiting:
                    with store.connect() as db:
                        db.execute("UPDATE review_sessions SET status='skipped',feedback='用户跳过本题' WHERE id=?",(waiting['id'],));db.commit()
                    saved=knowledge.record_exchange('local-user',text,'好，这题先跳过。',session_id,{'review':{'id':waiting['id'],'status':'skipped'}})
                elif decision.kind=='review_answer' and waiting:
                    await emit('tool','正在根据出题时的资料核对答案')
                    def grade():
                        with store.connect() as db: return grade_saved_review(db,waiting['id'],text)
                    result=await with_progress(run_in_threadpool(grade),emit,'正在逐项核对评分要点')
                    saved=knowledge.record_exchange('local-user',text,result['feedback'],session_id,{'review':result,'sources':result['sources'],'mode':'review_feedback','streak':mark_study_activity(0)})
                elif decision.kind in {'command','plan_followup'} and intent.action in {'plan','replan'}:
                    if intent.action=='plan' and not intent.goal.strip():
                        ready_docs=[d for d in knowledge.list_documents('local-user') if d['status']=='ready' and not d['needs_reindex']]
                        if ready_docs:
                            # Prefer filename + ranked topics over noisy raw keywords.
                            from .skills.review_session import _knowledge_topics
                            ranked=_knowledge_topics(4)
                            fname=ready_docs[0]['filename']
                            inferred=(f"复习《{fname}》" + (f"：{'、'.join(ranked[:3])}" if ranked else ''))[:200]
                            if len(ready_docs)>1:
                                inferred=f"{inferred}（已结合知识库 {len(ready_docs)} 份资料）"[:200]
                            intent=intent.model_copy(update={'goal':inferred})
                        else:
                            saved=knowledge.record_exchange('local-user',text,'想学习什么内容？可以先上传资料，或直接告诉我学习目标。',session_id,{'pending_plan':intent.model_dump()})
                    if saved is None and intent.action in {'plan','replan'} and (intent.action!='plan' or intent.goal.strip()):
                        if event['type']!='plan_request': await emit('tool','正在根据资料和时间预算制定计划草稿')
                        materials=await with_progress(run_in_threadpool(knowledge.learning_context,'local-user',intent.goal,ids),emit,'正在整理资料中的学习主题') if intent.action=='plan' else {'sources':[],'document_ids':ids}
                        if intent.action=='plan':
                            from .skills.study_plan import grounded_goal
                            plan_goal=grounded_goal(intent.goal,materials)
                            intent=intent.model_copy(update={'goal':plan_goal})
                            steps=[step.__dict__ for step in await asyncio.wait_for(agent.generate_plan(plan_goal,intent.days,intent.minutes_per_day,material_context=materials),timeout=60)]
                        with store.connect() as db:
                            if intent.action=='plan': draft=store.save_plan_draft(db,{'goal':intent.goal,'steps':steps,'sources':materials['sources'],'document_ids':materials['document_ids']})
                            else: draft=store.save_replan_draft(db,propose_replan(store.list_tasks(db),intent.days,intent.minutes_per_day))
                        if intent.action=='plan' and intent.goal.strip():
                            knowledge.set_context('local-user',session_id,materials.get('document_ids') if materials.get('document_ids') is not None else ids,topic=intent.goal[:200])
                        saved=knowledge.record_exchange('local-user',text,'计划草稿已生成，请检查后确认保存。',session_id,{'draft':draft,'kind':intent.action,'sources':materials['sources']})
                        out_type='plan_draft'
                elif decision.kind=='command' and intent.action=='focus':
                    await emit('tool','正在开始专注')
                    duration=(intent.seconds/60.0) if intent.seconds else float(intent.minutes or 25)
                    with store.connect() as db: focus=store.start_focus(db,None,duration)
                    if intent.seconds and not intent.minutes:
                        label=f'{intent.seconds}秒'
                    elif intent.seconds:
                        label=f'{intent.minutes}分{intent.seconds}秒'
                    else:
                        label=f'{intent.minutes}分钟'
                    saved=knowledge.record_exchange('local-user',text,f'已开始{label}专注。',session_id,{'focus':focus})
                elif decision.kind=='command' and intent.action=='done':
                    await emit('tool','正在确认打卡完成')
                    with store.connect() as db:
                        status=store.focus_status(db)
                    if not status or not status.get('id'):
                        saved=knowledge.record_exchange(
                            'local-user', text,
                            '现在没有进行中的打卡。先点「今日计划」选一项，确认后开始打卡～',
                            session_id, {'mode': 'check_in_idle'},
                        )
                    else:
                        result=stop_focus(int(status['id']))
                        speech=(result.get('speech') or '打卡完成，骨头到手啦～').strip()
                        saved=knowledge.record_exchange(
                            'local-user', text, speech, session_id,
                            {
                                'mode': 'task_reward',
                                'offer_review': bool(result.get('offer_review')),
                                'reward': result.get('reward'),
                                'focus_finish': result,
                                'today_task_id': result.get('task_id'),
                            },
                        )
                elif decision.kind=='command' and intent.action in {'review','quiz','weak'}:
                    await emit('tool','正在根据资料准备复习题（含单选/判断等）')
                    preferred='multiple_choice' if intent.action=='quiz' else ('short_answer' if intent.action=='review' else 'true_false')
                    # Retire any unanswered card so one-click「薄弱点/出题」lands on the new question.
                    with store.connect() as db:
                        db.execute(
                            "UPDATE review_sessions SET status='skipped', feedback='用户开始新题，自动跳过未答题' "
                            "WHERE status='waiting' AND session_id=?",
                            (session_id,),
                        )
                        db.commit()
                    def prepare():
                        if intent.action=='quiz': return daily_quiz(document_ids=ids)['items']
                        topic=intent.topic or '今日重点'
                        if intent.action=='weak':
                            with store.connect() as db:
                                rows=[dict(row) for row in db.execute('SELECT topic,status FROM review_sessions WHERE session_id=? ORDER BY id DESC LIMIT 20',(session_id,))]
                            topic=weak_point_review(rows)['topic']
                            try:
                                from .skills.preferences_loop import weak_topic_hint
                                hint=weak_topic_hint('local-user')
                                if hint and (not topic or topic in {'今日重点','重点'}):
                                    topic=hint[:80]
                                elif hint and hint not in topic:
                                    topic=f'{hint}'[:80]
                            except Exception:
                                pass
                        return [begin_review(topic,document_ids=ids,preferred_type=preferred)]
                    reviews=await with_progress(run_in_threadpool(prepare),emit,'正在生成带资料依据的复习题')
                    with store.connect() as db: created=[save_review(db,item,session_id) for item in reviews]
                    first=public_review(created[0])
                    saved=knowledge.record_exchange('local-user',text,first['question'],session_id,{'review':first,'quiz':[public_review(q) for q in created],'sources':first.get('sources',[]),'mode':'review_question'})
                elif decision.kind=='command' and intent.action=='today':
                    await emit('thinking','正在整理今日计划')
                    agenda=today_plan(session_id)
                    # 三选一 only when empty, or user explicitly asks to switch intensity.
                    want_options=bool(agenda.get('needs_plan') or re.search(r'换一套|重新选计划|换个计划|换强度|三选一', text))
                    ready_docs=[d for d in knowledge.list_documents('local-user') if d['status']=='ready' and not d['needs_reindex']]
                    options=[]
                    materials=None
                    if want_options and ready_docs:
                        from .skills.review_session import _knowledge_topics
                        from .skills.study_plan import grounded_goal, make_today_plan_options
                        ranked=_knowledge_topics(4)
                        fname=ready_docs[0]['filename']
                        inferred=(f"复习《{fname}》" + (f"：{'、'.join(ranked[:3])}" if ranked else ''))[:200]
                        await emit('tool','正在生成轻量 / 标准 / 加练三套今日计划')
                        materials=await with_progress(run_in_threadpool(knowledge.learning_context,'local-user',inferred,ids),emit,'正在整理资料中的学习主题')
                        plan_goal=grounded_goal(inferred,materials)
                        from .skills.preferences_loop import load_user_preferences, memory_context_blob, parse_daily_minutes
                        prefs=load_user_preferences('local-user')
                        variants=make_today_plan_options(
                            plan_goal,
                            materials,
                            daily_minutes=parse_daily_minutes(prefs.get('daily_minutes'), 45),
                            memory_blob=memory_context_blob('local-user'),
                        )
                        with store.connect() as db:
                            for variant in variants:
                                draft=store.save_plan_draft(db,{
                                    'goal': plan_goal,
                                    'steps': variant['steps'],
                                    'sources': materials['sources'],
                                    'document_ids': materials['document_ids'],
                                    'variant': variant['key'],
                                })
                                options.append({
                                    'id': draft['id'],
                                    'key': variant['key'],
                                    'label': variant['label'],
                                    'blurb': variant['blurb'],
                                    'minutes': variant['minutes'],
                                    'steps': variant['steps'],
                                })
                        knowledge.set_context('local-user',session_id,materials.get('document_ids') if materials.get('document_ids') is not None else ids,topic=plan_goal[:200])
                    if options:
                        lines=['汪！今日计划给你 3 套，请选一套：','']
                        for opt in options:
                            titles='；'.join(step['title'][:28] for step in opt['steps'][:2])
                            lines.append(f"· {opt['label']}（{opt['minutes']}分）：{titles}")
                        lines.append('')
                        lines.append('点下方方案保存后即可打卡；已有事办会被替换。' if agenda.get('tasks') else '点下方方案即可保存为今日事办，再开始打卡。')
                        saved=knowledge.record_exchange(
                            'local-user', text, '\n'.join(lines), session_id,
                            {
                                'mode': 'plan_options',
                                'plan_options': options,
                                'sources': (materials or {}).get('sources') or [],
                                'next_step': {
                                    'stage': 'plan',
                                    'action': 'plan',
                                    'title': '选择今日计划强度',
                                    'suggestion': '选轻量 / 标准 / 加练；选定后确认打卡。',
                                    'prompt': '今日计划',
                                },
                            },
                        )
                    elif agenda.get('needs_plan'):
                        saved=knowledge.record_exchange('local-user',text,agenda['text'],session_id,{'next_step':agenda['next_step'],'mode':'today_plan','today_plan':agenda})
                    else:
                        reminder='📌 今日事办——选一项确认后开始打卡；想换强度可以说「换一套计划」。\n\n'
                        saved=knowledge.record_exchange(
                            'local-user', text, reminder + agenda['text'], session_id,
                            {'next_step': agenda['next_step'], 'mode': 'today_plan', 'today_plan': agenda},
                        )
                elif decision.kind=='command' and intent.action=='next':
                    await emit('thinking','正在根据任务与资料判断下一步')
                    coach=next_step(session_id=session_id)
                    saved=knowledge.record_exchange('local-user',text,format_next_step(coach),session_id,{'next_step':coach})
                elif decision.kind=='knowledge':
                    await emit('searching','正在查找相关证据')
                    saved=await with_progress(run_in_threadpool(knowledge.answer,'local-user',text,session_id,ids,route if not personal else 'knowledge'),emit,'正在覆盖全文并检查引用，首次摘要需要一些时间')
                else:
                    await emit('thinking','正在根据任务与资料判断下一步')
                    reply=await asyncio.wait_for(agent.respond(text,history,emit,allow_knowledge=False),timeout=60)
                    saved=knowledge.record_exchange('local-user',text,reply,session_id,{'mode':'general','next_step':next_step(session_id=session_id)})
                coach=saved.get('next_step') or next_step(session_id=session_id)
                # Preferences stay silent in the bubble — applied to plan/review behavior only.
                await websocket.send_json({**saved,'type':out_type,'text':saved['answer'],'state':'success','answer_mode':saved['mode'],
                    'request_id':request_id,'next_step':coach,'mode':agent.mode,
                    **({'preference_notes': pref_inferred['notes']} if pref_inferred.get('notes') else {})})
            except asyncio.TimeoutError:
                await websocket.send_json({'type':'error','text':'处理超时，请重试。已完成的章节摘要会保留。','state':'error','request_id':request_id})
            except (ValueError,KeyError) as exc:
                await websocket.send_json({'type':'error','text':str(exc),'state':'error','request_id':request_id})
            except Exception:
                logger.exception('Companion request failed')
                await websocket.send_json({'type':'error','text':'处理失败，请检查模型配置或重试。','state':'error','request_id':request_id})
    except WebSocketDisconnect:
        pass
