from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from .agent.service import EchoAgent

app = FastAPI(title='AI Learning Companion API', version='0.1.0')
agent = EchoAgent()

@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}

@app.websocket('/ws/chat')
async def chat(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({'type': 'welcome', 'text': '你好！我已经准备好陪你学习。'})
    try:
        while True:
            try:
                event = await websocket.receive_json()
            except ValueError:
                await websocket.send_json({'type': 'error', 'text': '消息必须是 JSON。'})
                continue
            if not isinstance(event, dict) or event.get('type') != 'message' or not isinstance(event.get('text'), str) or not event['text'].strip():
                await websocket.send_json({'type': 'error', 'text': '请发送非空的 message.text。'})
                continue
            await websocket.send_json({'type': 'reply', 'text': await agent.respond(event['text'].strip())})
    except WebSocketDisconnect:
        pass
