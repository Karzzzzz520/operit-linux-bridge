#!/usr/bin/env python3
import json, os, sys, subprocess, time, shutil, random, string
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

HOST = '0.0.0.0'
PORT = 21073
START_TIME = time.time()

TOKEN_DIR = os.path.join(os.getenv('HOME', '/tmp'), '.config', 'operit-bridge')
TOKEN_FILE = os.path.join(TOKEN_DIR, 'token')

def _load_or_create_token():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except:
        token = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        os.makedirs(TOKEN_DIR, exist_ok=True)
        with open(TOKEN_FILE, 'w') as f:
            f.write(token + '\n')
        return token

BRIDGE_TOKEN = _load_or_create_token()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, f, *a):
        pass

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def _respond(self, obj):
        self.wfile.write(json.dumps(obj).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except Exception:
            self._set_headers(400)
            self._respond({"ok": False, "error": "invalid_json"})
            return
        action = req.get('action')
        rid = req.get('id')
        resp = {"ok": True, "id": rid, "token": BRIDGE_TOKEN[:8] + '...'}
        try:
            if action == 'exec':
                self._exec(req, resp)
            elif action == 'exec_bg':
                self._exec_bg(req, resp)
            elif action == 'read':
                self._read(req, resp)
            elif action == 'write':
                self._write(req, resp)
            elif action == 'delete':
                self._delete(req, resp)
            elif action == 'env':
                resp["env"] = dict(os.environ)
            elif action == 'ping':
                resp.update({"pong": True, "pid": os.getpid(),
                             "uptime_s": int(time.time() - START_TIME),
                             "env_count": len(os.environ),
                             "version": "2.1.0",
                             "token_set": os.path.exists(TOKEN_FILE)})
            elif action == 'list_dir':
                self._list_dir(req, resp)
            elif action == 'stat':
                self._stat(req, resp)
            elif action == 'mkdir':
                self._mkdir(req, resp)
            elif action == 'move':
                self._move(req, resp)
            elif action == 'copy':
                self._copy(req, resp)
            elif action == 'exists':
                self._exists(req, resp)
            elif action == 'process_list':
                self._process_list(req, resp)
            elif action == 'process_kill':
                self._process_kill(req, resp)
            elif action == 'sysinfo':
                self._sysinfo(req, resp)
            elif action == 'process_info':
                self._process_info(req, resp)
            elif action == 'clipboard_read':
                self._clipboard_read(req, resp)
            elif action == 'clipboard_write':
                self._clipboard_write(req, resp)
            elif action == 'notify':
                self._notify(req, resp)
            elif action == 'exec_stream':
                self._exec_stream(req, resp)
            elif action == 'watch':
                self._watch(req, resp)
            else:
                resp = {"ok": False, "error": "unknown_action", "id": rid}
        except KeyError as e:
            resp = {"ok": False, "error": "missing_parameter",
                    "message": f"Missing: {e}", "id": rid}
        except FileNotFoundError as e:
            resp = {"ok": False, "error": "not_found",
                    "message": str(e), "id": rid}
        except PermissionError as e:
            resp = {"ok": False, "error": "permission_denied",
                    "message": str(e), "id": rid}
        except Exception as e:
            resp = {"ok": False, "error": "internal_error",
                    "message": str(e), "id": rid}
        self._set_headers()
        self._respond(resp)

    def _exec(self, req, resp):
        cmd = req['command']
        timeout = req.get('timeout_ms', 30000) / 1000
        cwd = req.get('cwd') or os.getenv('HOME')
        env = os.environ.copy()
        env.update(req.get('env') or {})
        proc = subprocess.Popen(cmd, shell=True, cwd=cwd, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            resp.update({"exit_code": proc.returncode, "stdout": stdout,
                         "stderr": stderr, "pid": proc.pid,
                         "elapsed_ms": int((time.time() - START_TIME) * 1000)})
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            resp.update({"ok": False, "error": "timeout",
                         "stdout": stdout, "stderr": stderr})

    def _exec_bg(self, req, resp):
        cmd = req['command']
        cwd = req.get('cwd') or os.getenv('HOME')
        env = os.environ.copy()
        env.update(req.get('env') or {})
        proc = subprocess.Popen(cmd, shell=True, cwd=cwd, env=env,
                                start_new_session=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        resp["pid"] = proc.pid

    def _read(self, req, resp):
        path = req['path']
        offset = req.get('offset')
        limit = req.get('limit')
        encoding = req.get('encoding', 'utf-8')
        with open(path, 'rb') as f:
            if offset:
                f.seek(offset)
            data = f.read(limit) if limit else f.read()
        if encoding == 'base64':
            import base64
            resp.update({"path": path,
                         "content": base64.b64encode(data).decode('ascii'),
                         "size": len(data), "encoding": "base64",
                         "truncated": bool(limit and len(data) == limit)})
        else:
            try:
                content = data.decode('utf-8')
            except UnicodeDecodeError:
                content = data.decode('utf-8', errors='replace')
            resp.update({"path": path, "content": content,
                         "size": len(data),
                         "truncated": bool(limit and len(data) == limit)})

    def _write(self, req, resp):
        path = req['path']
        content = req['content']
        mode = req.get('mode')
        append = req.get('append', False)
        encoding = req.get('encoding', 'utf-8')
        flags = 'ab' if append else 'wb'
        if encoding == 'base64':
            import base64
            raw = base64.b64decode(content)
        else:
            raw = content.encode('utf-8')
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        with open(path, flags) as f:
            f.write(raw)
        if mode is not None:
            os.chmod(path, mode)
        resp.update({"path": path, "size": os.path.getsize(path)})

    def _delete(self, req, resp):
        path = req['path']
        recursive = req.get('recursive', False)
        if os.path.isdir(path) and recursive:
            shutil.rmtree(path)
        elif os.path.isdir(path):
            os.rmdir(path)
        else:
            os.remove(path)
        resp["path"] = path

    def _list_dir(self, req, resp):
        path = req.get('path', os.getenv('HOME'))
        entries = []
        for name in os.listdir(path):
            full = os.path.join(path, name)
            try:
                st = os.stat(full)
                entries.append({"name": name,
                                "type": 'dir' if os.path.isdir(full) else 'file',
                                "size": st.st_size, "mtime": int(st.st_mtime)})
            except Exception:
                entries.append({"name": name, "type": "unknown",
                                "size": 0, "mtime": 0})
        resp.update({"path": path, "entries": entries, "count": len(entries)})

    def _stat(self, req, resp):
        path = req['path']
        st = os.stat(path)
        resp.update({"path": path, "exists": True,
                     "type": 'dir' if os.path.isdir(path) else 'file',
                     "size": st.st_size, "mode": oct(st.st_mode),
                     "mtime": int(st.st_mtime), "atime": int(st.st_atime)})

    def _mkdir(self, req, resp):
        path = req['path']
        if req.get('recursive', False):
            os.makedirs(path, exist_ok=True)
        else:
            os.mkdir(path)
        resp["path"] = path

    def _move(self, req, resp):
        src = req.get('src') or req['path']
        dst = req['dst']
        shutil.move(src, dst)
        resp.update({"src": src, "dst": dst})

    def _copy(self, req, resp):
        src = req.get('src') or req['path']
        dst = req['dst']
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        resp.update({"src": src, "dst": dst})

    def _exists(self, req, resp):
        path = req['path']
        e = os.path.exists(path)
        resp.update({"path": path, "exists": e,
                     "type": ('dir' if os.path.isdir(path) else 'file') if e else None})

    def _process_list(self, req, resp):
        keyword = req.get('keyword', '')
        sort_by = req.get('sort', 'cpu')
        limit = req.get('limit', 30)
        sort_flag = '--sort=-%cpu' if sort_by == 'cpu' else '--sort=-rss'
        cmd = f"ps aux {sort_flag}"
        if keyword:
            cmd += f" | head -1; ps aux {sort_flag} | grep -i '{keyword}' | grep -v grep"
        cmd += f" | head -{int(limit) + 1}"
        out = subprocess.check_output(cmd, shell=True, text=True, timeout=10)
        resp.update({"output": out.strip(), "keyword": keyword, "sort": sort_by})

    def _process_kill(self, req, resp):
        pid = int(req['pid'])
        sig = int(req.get('signal', 15))
        os.kill(pid, sig)
        resp.update({"pid": pid, "signal": sig})

    def _sysinfo(self, req, resp):
        import platform
        info = {"hostname": platform.node(), "kernel": platform.release(),
                "arch": platform.machine(), "python": platform.python_version(),
                "user": os.getenv('USER', ''), "home": os.getenv('HOME', ''),
                "pid": os.getpid(), "uptime_s": int(time.time() - START_TIME)}
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal'):
                        info['mem_total_kb'] = int(line.split()[1])
                    elif line.startswith('MemAvailable'):
                        info['mem_avail_kb'] = int(line.split()[1])
        except Exception:
            pass
        try:
            st = os.statvfs(os.getenv('HOME', '/'))
            info['disk_total_gb'] = round(st.f_blocks * st.f_frsize / (1024**3), 1)
            info['disk_avail_gb'] = round(st.f_bavail * st.f_frsize / (1024**3), 1)
        except Exception:
            pass
        resp.update(info)

    def _process_info(self, req, resp):
        pid = int(req['pid'])
        out = subprocess.check_output(
            ['ps', '-p', str(pid), '-o', 'pid,user,%cpu,%mem,vsz,rss,stat,comm,args'],
            text=True, timeout=5)
        resp.update({"pid": pid, "output": out.strip()})

    def _clipboard_read(self, req, resp):
        content = ''
        try:
            content = subprocess.check_output(['wl-paste'], text=True, timeout=3).strip()
        except Exception:
            try:
                content = subprocess.check_output(
                    ['xclip', '-selection', 'clipboard', '-o'], text=True, timeout=3).strip()
            except Exception:
                resp.update({"ok": False, "error": "clipboard_unavailable",
                             "message": "Need wl-paste or xclip"})
                return
        resp.update({"content": content, "size": len(content)})

    def _clipboard_write(self, req, resp):
        content = req['content']
        ok = False
        try:
            subprocess.run(['wl-copy'], input=content, text=True, timeout=3)
            ok = True
        except Exception:
            try:
                subprocess.run(['xclip', '-selection', 'clipboard'],
                               input=content, text=True, timeout=3)
                ok = True
            except Exception:
                pass
        if not ok:
            resp.update({"ok": False, "error": "clipboard_unavailable",
                         "message": "Need wl-copy or xclip"})
            return
        resp.update({"ok": True, "size": len(content)})

    def _notify(self, req, resp):
        summary = req.get('summary', 'Operit Bridge')
        body = req.get('body', '')
        urgency = req.get('urgency', 'normal')
        timeout_ms = str(req.get('timeout_ms', 5000))
        icon = req.get('icon', 'dialog-information')
        try:
            subprocess.check_output(
                ['notify-send', '-u', urgency, '-t', timeout_ms,
                 '-i', icon, summary, body],
                timeout=5, stderr=subprocess.DEVNULL)
        except Exception as e:
            resp.update({"ok": False, "error": "notify_unavailable",
                         "message": str(e)})
            return
        resp.update({"ok": True, "summary": summary})

    def _exec_stream(self,req,resp):
        return self._exec(req,resp)

    def _watch(self,req,resp):
        path=req["path"]
        r=req.get("recursive",False)
        cmd="inotifywait -m" + (" -r" if r else "") + " " + path
        import subprocess as sp
        p=sp.Popen(cmd,shell=True,stdout=sp.PIPE,stderr=sp.PIPE,text=True)
        resp.update({"pid":p.pid,"watch_path":path})


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def run():
    server = ThreadedHTTPServer((HOST, PORT), Handler)
    print(f"Operit Bridge v2.1 on http://{HOST}:{PORT}")
    print(f"Token: {BRIDGE_TOKEN}")
    server.serve_forever()


if __name__ == '__main__':
    run()

    def _exec_stream(self,req,resp):
        return self._exec(req,resp)

    def _watch(self,req,resp):
        path=req["path"]
        r=req.get("recursive",False)
        cmd="inotifywait -m" + (" -r" if r else "") + " " + path
        import subprocess as sp
        p=sp.Popen(cmd,shell=True,stdout=sp.PIPE,stderr=sp.PIPE,text=True)
        resp.update({"pid":p.pid,"watch_path":path})

