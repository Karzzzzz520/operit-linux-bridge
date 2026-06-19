#!/usr/bin/env python3
import json, os, sys, subprocess, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

HOST = '0.0.0.0'
PORT = 21073
START_TIME = time.time()

class Handler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self._set_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except Exception:
            self.send_response(400)
            self._set_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "invalid_json"}).encode())
            return
        action = req.get('action')
        resp = {"ok": True, "id": req.get('id')}
        try:
            if action == 'exec':
                cmd = req['command']
                timeout = req.get('timeout_ms', 30000) / 1000
                cwd = req.get('cwd') or os.getenv('HOME')
                env = os.environ.copy()
                env.update(req.get('env') or {})
                proc = subprocess.Popen(cmd, shell=True, cwd=cwd, env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    stdout, stderr = proc.communicate(timeout=timeout)
                    elapsed = int((time.time() - START_TIME) * 1000)
                    resp.update({
                        "exit_code": proc.returncode,
                        "stdout": stdout,
                        "stderr": stderr,
                        "pid": proc.pid,
                        "elapsed_ms": elapsed
                    })
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                    resp["ok"] = False
                    resp["error"] = "timeout"
                    resp["stdout"] = stdout
                    resp["stderr"] = stderr
                    resp["pid"] = proc.pid
            elif action == 'exec_bg':
                cmd = req['command']
                cwd = req.get('cwd') or os.getenv('HOME')
                env = os.environ.copy()
                env.update(req.get('env') or {})
                proc = subprocess.Popen(cmd, shell=True, cwd=cwd, env=env,
                                        start_new_session=True, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
                resp.update({"pid": proc.pid})
            elif action == 'read':
                path = req['path']
                offset = req.get('offset')
                limit = req.get('limit')
                with open(path, 'rb') as f:
                    if offset:
                        f.seek(offset)
                    data = f.read(limit) if limit else f.read()
                try:
                    content = data.decode('utf-8')
                except UnicodeDecodeError:
                    content = data.decode('utf-8', errors='replace')
                resp.update({
                    "path": path,
                    "content": content,
                    "size": len(data),
                    "truncated": bool(limit and len(data) == limit)
                })
            elif action == 'write':
                path = req['path']
                content = req['content']
                mode = req.get('mode')
                append = req.get('append', False)
                flags = 'ab' if append else 'wb'
                with open(path, flags) as f:
                    f.write(content.encode('utf-8'))
                if mode is not None:
                    os.chmod(path, mode)
                resp.update({"path": path, "size": os.path.getsize(path)})
            elif action == 'delete':
                path = req['path']
                recursive = req.get('recursive', False)
                if os.path.isdir(path) and recursive:
                    import shutil
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                resp.update({"path": path})
            elif action == 'env':
                resp.update({"env": dict(os.environ)})
            elif action == 'ping':
                resp.update({
                    "pong": True,
                    "pid": os.getpid(),
                    "uptime_s": int(time.time() - START_TIME),
                    "env_count": len(os.environ)
                })
            else:
                resp = {"ok": False, "error": "unknown_action", "id": req.get('id')}
        except Exception as e:
            resp = {"ok": False, "error": "internal_error", "message": str(e), "id": req.get('id')}
        self.send_response(200)
        self._set_headers()
        self.wfile.write(json.dumps(resp).encode())

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def run():
    server = ThreadedHTTPServer((HOST, PORT), Handler)
    print(f"Operit Bridge listening on http://{HOST}:{PORT}")
    server.serve_forever()

if __name__ == '__main__':
    run()
