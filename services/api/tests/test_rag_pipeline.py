import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from app.knowledge.config import Settings
from app.knowledge.service import KnowledgeService
from app.knowledge.integration import get_knowledge
from app.knowledge.grounding import GroundedAnswer, GroundingVerdict, render_claims
from app.knowledge.routing import route_request
from app.main import app

@pytest.fixture
def kb(): return get_knowledge()

def upload(kb,text='B+ trees keep records in leaf nodes. Linked leaves support range queries.',name='lecture.txt'):
    return kb.upload('local-user',name,text.encode())

class EvidenceModel:
    def __init__(self,invalid_quote=False,supported=True,relevant=True):
        self.calls=[];self.invalid_quote=invalid_quote;self.supported=supported;self.relevant=relevant
    def with_structured_output(self,schema,method):
        assert method=='function_calling'
        owner=self
        class Call:
            def invoke(self,messages):
                data=json.loads(messages[1][1]);owner.calls.append((schema.__name__,data))
                if schema is GroundingVerdict:
                    return schema(supported=owner.supported,relevant=owner.relevant)
                if schema is GroundedAnswer:
                    return schema(claims=[{'text':s.get('digest') or s['snippet'][:80],
                        'evidence':[{'source_id':s['id'],'quote':'invented nonexistent quote' if owner.invalid_quote else s['snippet'][:100]}]}
                        for s in data['sources'][:12]])
                if schema.__name__=='ReviewQuestion':
                    s=data['sources'][0]
                    return schema(topic='范围查询',question='根据资料解释范围查询为何有效，并举例说明。',reference_answer='叶子节点相连支持范围扫描。',criteria=['叶子节点之间连接支持顺序扫描'],source_ids=[s['id']],quotes=[s['snippet'][:100]])
                if schema.__name__=='Grade':
                    return schema(points=[{'index':0,'met':True,'explanation':'同义表达正确描述了相邻叶子的顺序访问。'}],feedback='理解正确，接受同义表达。')
                raise AssertionError(schema)
        return Call()

@pytest.mark.parametrize('question',['火星大气层的主要成分是什么？','太阳温度是多少？','quantum gravity experiment'])
def test_unrelated_queries_have_no_evidence(kb,question):
    doc=upload(kb)
    assert kb.search('local-user',question)==[]
    result=kb.answer('local-user',question,document_ids=[doc['id']])
    assert result['mode']=='no_evidence' and result['sources']==[]

def test_scope_and_restart_followup_inherit(kb):
    a=upload(kb);b=upload(kb,'Solar cells transform sunlight into electricity.','solar.txt')
    first=kb.answer('local-user','B+ trees range queries',document_ids=[a['id']])
    restarted=KnowledgeService(kb.settings)
    second=restarted.answer('local-user','它为什么有效？',first['session_id'])
    assert second['context']['document_ids']==[a['id']]
    assert second['sources'] and all(s['document_id']==a['id'] for s in second['sources'])
    assert 'B+ trees range queries' in second['retrieval_query']
    assert restarted.answer('local-user','Solar cells',first['session_id'],[b['id']])['context']['document_ids']==[b['id']]

def test_unresolved_followup_clarifies(kb):
    upload(kb)
    assert kb.answer('local-user','它为什么有效？')['mode']=='clarification'

def test_rest_omitted_scope_inherits(kb):
    doc=upload(kb);client=TestClient(app)
    first=client.post('/knowledge/chat',json={'question':'B+ trees','document_ids':[doc['id']]}).json()
    second=client.post('/knowledge/chat',json={'question':'那范围查询呢？','session_id':first['session_id']}).json()
    assert second['context']['document_ids']==[doc['id']]
    assert client.put(f"/knowledge/sessions/{first['session_id']}/context",json={'document_ids':None}).status_code==200

def test_semantic_cross_language_without_lexical_overlap(tmp_path):
    class Semantic(Embeddings):
        def embed_documents(self,texts): return [[1.,0.] if 'range' in t else [0.,1.] for t in texts]
        def embed_query(self,text): return [1.,0.] if '范围' in text else [0.,1.]
    kb=KnowledgeService(Settings(data_dir=tmp_path/'semantic'),embeddings=Semantic(),embedding_id='multilingual-test')
    doc=upload(kb)
    assert kb.search('local-user','为什么适合范围扫描？')[0]['document_id']==doc['id']
    assert kb.search('local-user','完全无关的问题')==[]

@pytest.mark.parametrize('invalid,supported,relevant,mode',[(True,True,True,'citation_fallback'),(False,False,True,'citation_fallback'),(False,True,False,'no_evidence'),(False,True,True,'llm')])
def test_grounding_checks_quotes_and_support(kb,invalid,supported,relevant,mode):
    upload(kb);kb.chat_model=EvidenceModel(invalid,supported,relevant)
    result=kb.answer('local-user','B+ trees range queries')
    assert result['mode']==mode
    if mode=='llm': assert result['quotes'] and '[S1]' in result['answer']
    if mode=='no_evidence': assert result['sources']==[]

def test_unknown_citation_id_is_rejected():
    result=GroundedAnswer(claims=[{'text':'A claim','evidence':[{'source_id':'S999','quote':'some actual words'}]}])
    with pytest.raises(ValueError):render_claims(result,[{'id':'S1','snippet':'some actual words'}])

def test_summary_covers_last_chapter_and_clarifies_ambiguous_doc(kb):
    text='\n\n'.join(f'Chapter {i}: topic{i} '+('important explanation and examples. '*26) for i in range(14))
    doc=upload(kb,text,'long.txt')
    result=kb.answer('local-user','总结这份资料',document_ids=[doc['id']])
    assert result['coverage']['processed_chunks']==doc['chunk_count']
    assert any('topic13' in s['snippet'] for s in result['sources'])
    assert result['mode']=='extractive_overview'
    upload(kb,'A different unrelated document.','other.txt')
    assert kb.answer('local-user','总结这份资料')['mode']=='clarification'

def test_model_summary_maps_full_document_and_caches_groups(kb):
    doc=upload(kb,'\n\n'.join(f'Section {i}: '+('range queries use linked leaf nodes. '*40) for i in range(16)),'long.txt')
    model=EvidenceModel();kb.chat_model=model
    first=kb.summarize_document('local-user',doc['id'])
    assert first['coverage']['processed_chunks']==doc['chunk_count']
    before=len(model.calls)
    second=kb.summarize_document('local-user',doc['id'])
    assert len(model.calls)-before==2
    assert second['coverage']==first['coverage']

def test_comparison_requires_evidence_from_each_document(kb):
    a=upload(kb);b=upload(kb,'Solar cells transform sunlight into electricity.','solar.txt')
    result=kb.compare_documents('local-user',[a['id'],b['id']],'B+ trees range')
    assert result['mode']=='no_evidence'
    kb.chat_model=EvidenceModel()
    result=kb.compare_documents('local-user',[a['id'],b['id']])
    assert result['mode']=='comparison'
    assert {s['document_id'] for s in result['sources']}=={a['id'],b['id']}

def test_preferences_are_used_without_replacing_course_evidence(kb):
    upload(kb);kb.save_preferences('local-user',{'explanation_style':'先讲结论'})
    model=EvidenceModel();kb.chat_model=model
    result=kb.answer('local-user','根据我的偏好解释 B+ trees range queries')
    assert result['mode']=='llm'
    assert model.calls[0][1]['preferences']['explanation_style']=='先讲结论'

@pytest.mark.parametrize('text,expected',[('今天好累，陪我聊聊','chat'),('总结这份讲义','summary'),('比较这些资料','compare'),('B+树为什么适合范围查询？','knowledge')])
def test_request_routes(text,expected): assert route_request(text,has_documents=True)==expected

def terminal(ws):
    while True:
        event=ws.receive_json()
        if event['type'] in {'reply','error','plan_draft'}: return event

def test_websocket_chat_and_knowledge_stay_separate(kb):
    doc=upload(kb);client=TestClient(app)
    with client.websocket_connect('/ws/chat') as ws:
        ws.receive_json();ws.send_json({'type':'message','text':'今天好累，陪我聊聊','request_id':'chat1'})
        social=terminal(ws);assert social['answer_mode']=='general'
        ws.send_json({'type':'message','text':'火星大气层的成分是什么？','session_id':social['session_id'],'knowledge':True,'document_ids':[doc['id']],'request_id':'ask1'})
        result=terminal(ws);assert result['request_id']=='ask1' and result['answer_mode']=='no_evidence'

def test_plan_uses_materials_and_still_requires_confirmation(kb):
    doc=upload(kb);client=TestClient(app)
    result=client.post('/plans/drafts',json={'goal':'复习这份资料','days':2,'minutes_per_day':30,'document_ids':[doc['id']]}).json()
    assert result['document_ids']==[doc['id']] and result['sources']
    assert '这份资料' not in result['steps'][0]['title']
    assert client.get('/tasks').json()==[]
    assert client.post(f"/plans/drafts/{result['id']}/confirm").status_code==200

def test_review_uses_fixed_snapshot_after_document_deletion(kb):
    from app.skills.review_session import begin_review,save_review,grade_saved_review
    from app.database import store
    doc=upload(kb);kb.chat_model=EvidenceModel()
    review=begin_review('range queries',document_ids=[doc['id']])
    with store.connect() as db: saved=save_review(db,review,'session-a')
    kb.delete_document('local-user',doc['id'])
    with store.connect() as db: result=grade_saved_review(db,saved['id'],'相邻叶子能沿顺序访问，所以区间扫描很快。')
    assert result['result']=='correct' and result['sources']==review['sources']
    with store.connect() as db:
        with pytest.raises(ValueError):grade_saved_review(db,saved['id'],'重复提交')

def test_review_in_one_conversation_does_not_capture_another(kb):
    client=TestClient(app)
    with client.websocket_connect('/ws/chat') as first:
        first.receive_json();first.send_json({'type':'message','text':'开始复习 B+树','request_id':'review1'})
        review=terminal(first);assert review['review']['id']
        with client.websocket_connect('/ws/chat') as second:
            second.receive_json();second.send_json({'type':'message','text':'我想聊点别的','session_id':None,'request_id':'chat2'})
            reply=terminal(second)
            assert reply['answer_mode']=='general' and 'review' not in reply

def test_knowledge_question_does_not_submit_pending_review(kb):
    from app.database import store
    doc=upload(kb);client=TestClient(app)
    with client.websocket_connect('/ws/chat') as ws:
        ws.receive_json();ws.send_json({'type':'message','text':'开始复习','document_ids':[doc['id']],'request_id':'r1'})
        review=terminal(ws)
        ws.send_json({'type':'message','text':'B+ trees 为什么适合范围查询？','session_id':review['session_id'],'request_id':'q1'})
        question=terminal(ws)
        assert question['answer_mode'] in {'extractive','no_evidence'}
        with store.connect() as db:
            row=db.execute('SELECT status FROM review_sessions WHERE id=?',(review['review']['id'],)).fetchone()
            assert row['status']=='waiting'


def test_bailian_embedding_sends_strings_in_batches_of_ten(tmp_path):
    import httpx
    from openai import OpenAI
    captured=[]
    def respond(request):
        data=json.loads(request.content);captured.append(data)
        assert request.url.path.endswith('/embeddings')
        assert data['encoding_format']=='float'
        assert all(isinstance(text,str) for text in data['input'])
        return httpx.Response(200,json={'object':'list','data':[{'object':'embedding','index':i,'embedding':[1.,0.,0.]} for i,_ in enumerate(data['input'])],'model':'text-embedding-v4','usage':{'prompt_tokens':3,'total_tokens':3}})
    kb=KnowledgeService(Settings(data_dir=tmp_path/'bailian',llm_api_key='test-only',llm_base_url='https://bailian.example/compatible-mode/v1',embedding_provider='openai',embedding_model='text-embedding-v4',embedding_batch_size=10))
    kb.embeddings.client=OpenAI(api_key='test-only',base_url='https://bailian.example/compatible-mode/v1',http_client=httpx.Client(transport=httpx.MockTransport(respond))).embeddings
    vectors=kb.embeddings.embed_documents([f'chunk {i}' for i in range(23)])
    assert len(vectors)==23 and [len(call['input']) for call in captured]==[10,10,3]


def test_docx_headings_and_table_locations_are_retained(kb):
    from docx import Document
    from io import BytesIO
    word=Document();word.add_heading('Range Queries',level=1);word.add_paragraph('Linked leaves support range queries.')
    table=word.add_table(rows=1,cols=2);table.cell(0,0).text='Index type';table.cell(0,1).text='B+ tree'
    word.add_heading('Hash Lookup',level=1);word.add_paragraph('Hash indexes support equality lookup.')
    data=BytesIO();word.save(data)
    doc=kb.upload('local-user','lecture.docx',data.getvalue())
    chunks=kb.document_chunks('local-user',doc['id'])
    assert 'Range Queries' in chunks[0]['section'] and 'Hash Lookup' in chunks[-1]['section']
    assert 'Index type | B+ tree' in chunks[0]['content']


def test_semantic_model_switch_requires_reindex(kb):
    doc=upload(kb)
    kb.embedding_id='changed-model'
    assert kb.list_documents('local-user')[0]['needs_reindex']
    assert kb.search('local-user','B+ trees')==[]


def test_comparison_creates_a_scoped_history(kb):
    first=upload(kb);second=upload(kb,'B+ trees use ordered linked leaves for ranges.','second.txt')
    result=TestClient(app).post('/knowledge/compare',json={'document_ids':[first['id'],second['id']]}).json()
    assert result['session_id'] and result['context']['document_ids']==[first['id'],second['id']]
    assert len(kb.db.messages('local-user',result['session_id']))==2


@pytest.mark.parametrize('ambiguous',[False,True])
def test_model_followup_rewrite_is_scoped_and_can_clarify(kb,ambiguous):
    doc=upload(kb,'B+树的叶子节点按顺序连接，因此适合范围查询。')
    initial=kb.answer('local-user','B+树范围查询',document_ids=[doc['id']])
    class RewriteModel(EvidenceModel):
        def with_structured_output(self,schema,method):
            if schema.__name__=='QueryRewrite':
                class Call:
                    def invoke(self,messages):return schema(question='B+树为什么适合范围查询？',ambiguous=ambiguous)
                return Call()
            return super().with_structured_output(schema,method)
    kb.chat_model=RewriteModel()
    result=kb.answer('local-user','它为什么更快？',initial['session_id'])
    assert result['mode']==('clarification' if ambiguous else 'llm')
    if not ambiguous:
        assert result['retrieval_query']=='B+树为什么适合范围查询？'
        assert all(s['document_id']==doc['id'] for s in result['sources'])
