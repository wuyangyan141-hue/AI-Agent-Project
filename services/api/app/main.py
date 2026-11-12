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
from .skills.learning_loop import format_next_step, mark_study_activity, next_step
from .knowledge.api import router as knowledge_router
from .knowledge.documents import DocumentError
from .knowledge.integration import get_knowledge
from .knowledge.config import Settings
from .knowledge.service import UNSET
from .knowledge.routing import route_request, SOCIAL, QUESTION
from .knowledge.storage import uid
from .agent.intent import StudyIntent, explicit_intent

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
    minutes: int = Field(default=25, ge=1, le=240)

class ReviewInput(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    document_ids: list[str] | None = Field(default=None,max_length=4)
    session_id: str | None = None

class ReviewScope(BaseModel):
    document_ids: list[str] | None = Field(default=None,max_length=4)
    session_id: str | None = None

class ReviewAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)

@app.get('/health')
def health() -> dict[str, str | int]:
    return {'status': 'ok', 'agent_mode': agent.mode,'version':'0.4.0','protocol_version':2}

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

def review_scope(item):
    knowledge=get_knowledge()
    return knowledge.resolve_scope('local-user',item.session_id,item.document_ids if 'document_ids' in item.model_fields_set else UNSET)

@app.post('/reviews',status_code=201)
def start_review(item: ReviewInput):
    review=begin_review(item.topic,document_ids=review_scope(item))
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
    await websocket.send_json({'type':'welcome','text':'你好，我是豆豆。可以聊聊，也可以选择资料提问。','state':'idle','mode':agent.mode,'next_step':next_step()})
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
                route=route_request(text,forced=event.get('knowledge') is True or bool(ids),general=event.get('general') is True,
                                    has_documents=ready,active_topic=bool(context['topic']))
                direct=explicit_intent(text)
                pending=history_rows[-1]['metadata'].get('pending_plan') if history_rows else None
                if event['type']=='plan_request':
                    plan=PlanInput.model_validate(event.get('payload'))
                    intent=StudyIntent(action='plan',goal=plan.goal,days=plan.days,minutes_per_day=plan.minutes_per_day)
                elif pending and route=='chat' and not SOCIAL.search(text) and not QUESTION.search(text):
                    intent=StudyIntent.model_validate(pending).model_copy(update={'goal':text[:200]})
                elif direct.action!='chat' or personal or route!='chat' or event.get('general') is True:
                    intent=direct
                else:
                    intent=await asyncio.wait_for(agent.detect_intent(text,history),timeout=30)
                with store.connect() as db:
                    waiting=db.execute("SELECT * FROM review_sessions WHERE status='waiting' AND session_id=? ORDER BY id LIMIT 1",(session_id,)).fetchone()
                    waiting=dict(waiting) if waiting else None
                saved=None;out_type='reply';extra={}
                if waiting and re.search(r'跳过(这题|本题|复习)?|取消复习|先不答|下次再答',text):
                    with store.connect() as db:
                        db.execute("UPDATE review_sessions SET status='skipped',feedback='用户跳过本题' WHERE id=?",(waiting['id'],));db.commit()
                    saved=knowledge.record_exchange('local-user',text,'好，这题先跳过。',session_id,{'review':{'id':waiting['id'],'status':'skipped'}})
                elif waiting and intent.action=='chat' and not personal and not SOCIAL.search(text) and (event.get('review_answer') is True or (route not in {'summary','compare'} and not QUESTION.search(text))):
                    await emit('tool','正在根据出题时的资料核对答案')
                    def grade():
                        with store.connect() as db: return grade_saved_review(db,waiting['id'],text)
                    result=await with_progress(run_in_threadpool(grade),emit,'正在逐项核对评分要点')
                    saved=knowledge.record_exchange('local-user',text,result['feedback'],session_id,{'review':result,'sources':result['sources'],'mode':'review','streak':mark_study_activity(0)})
                elif intent.action in {'plan','replan'}:
                    if intent.action=='plan' and not intent.goal.strip():
                        saved=knowledge.record_exchange('local-user',text,'想学习什么内容？请告诉我学习目标。',session_id,{'pending_plan':intent.model_dump()})
                    else:
                        if event['type']!='plan_request': await emit('tool','正在根据资料和时间预算制定计划草稿')
                        materials=await with_progress(run_in_threadpool(knowledge.learning_context,'local-user',intent.goal,ids),emit,'正在整理资料中的学习主题') if intent.action=='plan' else {'sources':[],'document_ids':ids}
                        if intent.action=='plan':
                            steps=[step.__dict__ for step in await asyncio.wait_for(agent.generate_plan(intent.goal,intent.days,intent.minutes_per_day,material_context=materials),timeout=60)]
                        with store.connect() as db:
                            if intent.action=='plan': draft=store.save_plan_draft(db,{'goal':intent.goal,'steps':steps,'sources':materials['sources'],'document_ids':materials['document_ids']})
                            else: draft=store.save_replan_draft(db,propose_replan(store.list_tasks(db),intent.days,intent.minutes_per_day))
                        saved=knowledge.record_exchange('local-user',text,'计划草稿已生成，请检查后确认保存。',session_id,{'draft':draft,'kind':intent.action,'sources':materials['sources']})
                        out_type='plan_draft'
                elif intent.action=='focus':
                    await emit('tool','正在开始专注')
                    with store.connect() as db: focus=store.start_focus(db,None,intent.minutes)
                    saved=knowledge.record_exchange('local-user',text,f'已开始{intent.minutes}分钟专注。',session_id,{'focus':focus})
                elif intent.action in {'review','quiz','weak'}:
                    await emit('tool','正在根据资料准备复习题')
                    def prepare():
                        if intent.action=='quiz': return daily_quiz(document_ids=ids)['items']
                        topic=intent.topic or '今日重点'
                        if intent.action=='weak':
                            with store.connect() as db:
                                rows=[dict(row) for row in db.execute('SELECT topic,status FROM review_sessions WHERE session_id=? ORDER BY id DESC LIMIT 20',(session_id,))]
                            topic=weak_point_review(rows)['topic']
                        return [begin_review(topic,document_ids=ids)]
                    reviews=await with_progress(run_in_threadpool(prepare),emit,'正在生成带资料依据的复习题')
                    with store.connect() as db: created=[save_review(db,item,session_id) for item in reviews]
                    first=public_review(created[0])
                    saved=knowledge.record_exchange('local-user',text,first['question'],session_id,{'review':first,'quiz':[public_review(q) for q in created],'sources':first.get('sources',[]),'mode':'review'})
                elif intent.action=='next':
                    coach=next_step(session_id=session_id)
                    saved=knowledge.record_exchange('local-user',text,format_next_step(coach),session_id,{'next_step':coach})
                elif personal or route in {'knowledge','summary','compare'}:
                    await emit('searching','正在查找相关证据')
                    saved=await with_progress(run_in_threadpool(knowledge.answer,'local-user',text,session_id,ids,route if not personal else 'knowledge'),emit,'正在覆盖全文并检查引用，首次摘要需要一些时间')
                else:
                    reply=await asyncio.wait_for(agent.respond(text,history,emit,allow_knowledge=False),timeout=60)
                    saved=knowledge.record_exchange('local-user',text,reply,session_id,{'mode':'general'})
                coach=saved.get('next_step') or next_step(session_id=session_id)
                await websocket.send_json({**saved,'type':out_type,'text':saved['answer'],'state':'success','answer_mode':saved['mode'],
                    'request_id':request_id,'next_step':coach,'mode':agent.mode})
            except asyncio.TimeoutError:
                await websocket.send_json({'type':'error','text':'处理超时，请重试。已完成的章节摘要会保留。','state':'error','request_id':request_id})
            except (ValueError,KeyError) as exc:
                await websocket.send_json({'type':'error','text':str(exc),'state':'error','request_id':request_id})
            except Exception:
                logger.exception('Companion request failed')
                await websocket.send_json({'type':'error','text':'处理失败，请检查模型配置或重试。','state':'error','request_id':request_id})
    except WebSocketDisconnect:
        pass
