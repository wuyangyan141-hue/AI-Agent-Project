"""Start this checkout's local API and Electron, with explicit version checks."""
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]

def health():
    try:
        with urlopen('http://127.0.0.1:8000/health',timeout=1) as response:
            return json.load(response)
    except Exception:
        return None

def main():
    existing=health()
    if existing and existing.get('protocol_version')!=2:
        raise SystemExit('8000端口正在运行旧版后端，请先在旧后端终端按Ctrl+C关闭，再重新启动豆豆。')
    backend=None
    try:
        if not existing:
            backend=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],cwd=ROOT/'services/api')
            for _ in range(60):
                if backend.poll() is not None:
                    raise SystemExit('后端启动失败，请查看上面的错误。')
                if (health() or {}).get('protocol_version')==2:break
                time.sleep(.25)
            else: raise SystemExit('后端启动超时。')
        result=subprocess.run(['npm.cmd' if sys.platform=='win32' else 'npm','run','start'],cwd=ROOT)
        return result.returncode
    finally:
        if backend:
            backend.terminate()
            try:backend.wait(timeout=5)
            except subprocess.TimeoutExpired:backend.kill();backend.wait()

if __name__=='__main__':
    try:sys.exit(main())
    except KeyboardInterrupt:pass
