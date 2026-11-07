#!/usr/bin/python3
"""Small same-origin admin UI. Runs unprivileged; all privileged work is allowlisted."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import subprocess
import threading
import time
import uuid
from collections import deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit


ROOT = Path("/opt/grok-admin-panel")
STATIC = ROOT / "static"
HELPER = "/usr/local/sbin/grok-admin-action"
AUTH_FILE = Path("/etc/grok-admin-panel/auth.json")
READONLY_AUTH_FILE = Path("/etc/grok-admin-panel/readonly-auth.json")
ORIGIN = os.environ.get("GROK_ADMIN_ORIGIN", "")
HOST = ORIGIN.removeprefix("http://").removeprefix("https://")
PORT = int(os.environ.get("GROK_ADMIN_PORT", "6069"))
MAX_BODY = 300_000
PBKDF2_ITERATIONS = 600_000
SESSION_TTL = 6 * 60 * 60
SESSIONS: dict[str, dict[str, Any]] = {}
LOGIN_ATTEMPTS: dict[str, deque[float]] = {}
LOCK = threading.RLock()
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
JOB_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="grok-admin-job")


def profile_query(value: Any) -> str:
    if not isinstance(value, str) or not value.isdigit() or not 5 <= len(value) <= 12:
        raise ValueError("QQ 号格式无效")
    return value


def profile_view(data: Any) -> dict[str, Any]:
    source = data if isinstance(data, dict) else {}
    profile = source.get("profile") if isinstance(source.get("profile"), dict) else {}
    relationship = source.get("relationship") if isinstance(source.get("relationship"), dict) else {}
    profile_keys = ("preferredName", "privateNickname", "groupNicknames", "relationships", "chatHabits", "preferences")
    relation_keys = ("stage", "familiarity", "trust", "affection", "boundary", "lastMood", "milestones", "turns", "updatedAt")
    return {
        "profile": {key: profile[key] for key in profile_keys if key in profile},
        "relationship": {key: relationship[key] for key in relation_keys if key in relationship},
        "portrait": source.get("portrait") if isinstance(source.get("portrait"), dict) else {},
        "native": source.get("native") if isinstance(source.get("native"), dict) else {},
        "readOnly": True,
    }


def auth_record(path: Path = AUTH_FILE) -> dict[str, Any]:
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
        if (isinstance(item, dict) and isinstance(item.get("salt"), str)
                and isinstance(item.get("hash"), str) and item.get("iterations") == PBKDF2_ITERATIONS):
            return item
    except (OSError, json.JSONDecodeError):
        pass
    raise RuntimeError("admin password is not initialized")


def password_digest(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS).hex()


def verify_password(password: str, path: Path = AUTH_FILE) -> bool:
    try:
        record = auth_record(path)
        actual = password_digest(password, record["salt"])
        return hmac.compare_digest(actual, record["hash"])
    except Exception:
        return False


def helper_call(payload: dict[str, Any], timeout: int = 45) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(raw) > MAX_BODY:
        raise RuntimeError("request too large")
    try:
        result = subprocess.run(
            ["sudo", "-n", HELPER], input=raw, capture_output=True, timeout=timeout,
            check=False, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("operation timed out") from exc
    except OSError as exc:
        raise RuntimeError("helper unavailable") from exc
    try:
        response = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("invalid helper response") from exc
    if result.returncode != 0 or not isinstance(response, dict) or not response.get("ok"):
        message = response.get("error") if isinstance(response, dict) else None
        raise RuntimeError(message if isinstance(message, str) else "operation failed")
    data = response.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("invalid helper data")
    return data


def new_session() -> tuple[str, str]:
    return secrets.token_urlsafe(32), secrets.token_urlsafe(32)


def run_job(job_id: str, payload: dict[str, Any], timeout: int) -> None:
    with JOBS_LOCK:
        JOBS[job_id]["state"] = "running"
        JOBS[job_id]["started"] = int(time.time())
    try:
        data = helper_call(payload, timeout=timeout)
        safe = {key: value for key, value in data.items() if key in {"state", "kind", "package", "backupId", "reloaded", "restored", "hostRebooted", "summaryLines", "hermesVersion", "hermesUpdate", "apt"}}
        with JOBS_LOCK:
            JOBS[job_id].update({"state": "completed", "result": safe, "finished": int(time.time())})
    except RuntimeError as exc:
        with JOBS_LOCK:
            JOBS[job_id].update({"state": "failed", "error": str(exc)[:160], "finished": int(time.time())})
    except Exception:
        with JOBS_LOCK:
            JOBS[job_id].update({"state": "failed", "error": "操作失败；敏感详情未保存", "finished": int(time.time())})


class Handler(BaseHTTPRequestHandler):
    server_version = "JiangshengAdmin/1"
    sys_version = ""

    def log_message(self, _format: str, *args: Any) -> None:
        # Never record URL query strings, client IPs, request bodies, or credentials.
        return

    def send_common_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Cache-Control", "no-store")

    def send_json(self, value: Any, status: int = 200, extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_asset(self, filename: str, content_type: str) -> None:
        path = STATIC / filename
        try:
            body = path.read_bytes()
        except OSError:
            self.send_json({"error": "页面资源不可用"}, 503)
            return
        self.send_response(200)
        self.send_common_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def get_session(self) -> tuple[str | None, dict[str, Any] | None]:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            token = cookie.get("grok_admin_session").value if cookie.get("grok_admin_session") else None
        except Exception:
            token = None
        if not token:
            return None, None
        with LOCK:
            session = SESSIONS.get(token)
            if not session:
                return token, None
            if session["expires"] < time.time():
                SESSIONS.pop(token, None)
                return token, None
            session["expires"] = time.time() + SESSION_TTL
            return token, session

    def request_origin_ok(self) -> bool:
        if not ORIGIN or self.headers.get("Origin") != ORIGIN:
            return False
        return self.headers.get("Host", "") == HOST

    def read_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("请求长度无效") from exc
        if length < 0 or length > MAX_BODY:
            raise ValueError("请求内容过大")
        if self.headers.get_content_type() != "application/json":
            raise ValueError("请求类型无效")
        try:
            result = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("JSON 格式无效") from exc
        if not isinstance(result, dict):
            raise ValueError("请求必须为对象")
        return result

    def require_session(self) -> tuple[str, dict[str, Any]] | None:
        token, session = self.get_session()
        if not token or not session:
            self.send_json({"error": "请先登录"}, 401)
            return None
        return token, session

    def require_write(self) -> tuple[str, dict[str, Any]] | None:
        if not self.request_origin_ok():
            self.send_json({"error": "请求来源无效"}, 403)
            return None
        result = self.require_session()
        if not result:
            return None
        _token, session = result
        if session.get("role") != "admin":
            self.send_json({"error": "只读账号不能执行修改、重启、更新或恢复操作"}, 403)
            return None
        if not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), session["csrf"]):
            self.send_json({"error": "安全校验失败，请刷新页面后重试"}, 403)
            return None
        return result

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self.send_asset("index.html", "text/html; charset=utf-8")
            return
        if path == "/app.js":
            self.send_asset("app.js", "text/javascript; charset=utf-8")
            return
        if path == "/style.css":
            self.send_asset("style.css", "text/css; charset=utf-8")
            return
        if path == "/api/session":
            token, session = self.get_session()
            if token and session:
                self.send_json({"authenticated": True, "csrf": session["csrf"], "role": session.get("role", "admin")})
            else:
                self.send_json({"authenticated": False}, 401)
            return
        if path == "/api/status":
            if not self.require_session():
                return
            try:
                self.send_json(helper_call({"action": "status"}, timeout=20))
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 503)
            return
        if path == "/api/evolution":
            if not self.require_session():
                return
            try:
                snapshot = json.loads(Path("/var/lib/grok-admin-panel/evolution-status.json").read_text(encoding="utf-8"))
                snapshot["stale"] = time.time() - int(snapshot.get("generatedAt", 0)) > 150
                self.send_json(snapshot)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                self.send_json({"error": "两台服务器状态暂不可用"}, 503)
            return
        if path == "/api/settings":
            if not self.require_session():
                return
            try:
                self.send_json(helper_call({"action": "settings"}, timeout=20))
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 503)
            return
        if path == "/api/backups":
            if not self.require_session():
                return
            try:
                self.send_json(helper_call({"action": "backups"}))
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 503)
            return
        if path == "/api/profile":
            if not self.require_session():
                return
            try:
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                qq = profile_query(query.get("qq", [""])[0])
                self.send_json(profile_view(helper_call({"action": "profile", "qq": qq}, timeout=20)))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, 400)
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 503)
            return
        if path == "/api/updates":
            if not self.require_session():
                return
            try:
                self.send_json(helper_call({"action": "updates_snapshot"}, timeout=40))
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 503)
            return
        if path.startswith("/api/jobs/"):
            if not self.require_session():
                return
            job_id = path.removeprefix("/api/jobs/")
            if not all(char in "0123456789abcdef-" for char in job_id) or len(job_id) > 40:
                self.send_json({"error": "任务编号无效"}, 400)
                return
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                if job:
                    self.send_json({key: value for key, value in job.items() if key in {"id", "kind", "state", "result", "error", "started", "finished"}})
                else:
                    self.send_json({"error": "任务不存在"}, 404)
            return
        self.send_json({"error": "页面不存在"}, 404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/login":
            if not self.request_origin_ok():
                self.send_json({"error": "请求来源无效"}, 403)
                return
            address = self.client_address[0]
            now = time.time()
            attempts = LOGIN_ATTEMPTS.setdefault(address, deque())
            while attempts and now - attempts[0] > 900:
                attempts.popleft()
            if len(attempts) >= 8:
                self.send_json({"error": "登录尝试过多，请稍后再试"}, 429)
                return
            try:
                payload = self.read_body()
            except ValueError as exc:
                self.send_json({"error": str(exc)}, 400)
                return
            password = payload.get("password")
            if not isinstance(password, str) or len(password) > 256:
                attempts.append(now)
                self.send_json({"error": "口令错误"}, 401)
                return
            role = "admin" if verify_password(password, AUTH_FILE) else ("readonly" if verify_password(password, READONLY_AUTH_FILE) else None)
            if role is None:
                attempts.append(now)
                self.send_json({"error": "口令错误"}, 401)
                return
            LOGIN_ATTEMPTS.pop(address, None)
            token, csrf = new_session()
            with LOCK:
                SESSIONS[token] = {"csrf": csrf, "role": role, "expires": now + SESSION_TTL}
            self.send_json({"authenticated": True, "csrf": csrf, "role": role}, 200, {
                "Set-Cookie": f"grok_admin_session={token}; HttpOnly; Path=/; SameSite=Strict; Max-Age={SESSION_TTL}",
            })
            return
        if path == "/api/logout":
            result = self.require_session()
            if not result:
                return
            token, session = result
            if not self.request_origin_ok() or not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), session["csrf"]):
                self.send_json({"error": "安全校验失败，请刷新页面后重试"}, 403)
                return
            with LOCK:
                SESSIONS.pop(token, None)
            self.send_json({"loggedOut": True}, 200, {"Set-Cookie": "grok_admin_session=; HttpOnly; Path=/; SameSite=Strict; Max-Age=0"})
            return
        if path == "/api/profile" or path.startswith("/api/profile/"):
            self.send_json({"error": "用户档案为只读，不能修改或删除"}, 405)
            return
        result = self.require_write()
        if not result:
            return
        _token, session = result
        try:
            payload = self.read_body()
        except ValueError as exc:
            self.send_json({"error": str(exc)}, 400)
            return
        if path == "/api/persona":
            try:
                self.send_json(helper_call({"action": "save_persona", "persona": payload.get("persona")}, timeout=60))
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path == "/api/features":
            try:
                self.send_json(helper_call({"action": "save_features", "features": payload.get("features")}, timeout=60))
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path == "/api/proactive":
            try:
                self.send_json(helper_call({"action": "save_proactive", "proactive": payload.get("proactive")}, timeout=60))
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path == "/api/model":
            try:
                self.send_json(helper_call({"action": "set_model", "model": payload.get("model")}, timeout=90))
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path == "/api/services/restart":
            try:
                self.send_json(helper_call({"action": "restart_service", "service": payload.get("service")}, timeout=90))
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path == "/api/backups/restore":
            try:
                self.send_json(helper_call({"action": "restore_backup", "backupId": payload.get("backupId"), "files": payload.get("files")}, timeout=120))
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path == "/api/password":
            current = payload.get("currentPassword")
            new_password = payload.get("newPassword")
            if (session.get("role") != "admin" or not isinstance(current, str) or not verify_password(current)
                    or not isinstance(new_password, str) or len(new_password) < 16 or len(new_password) > 256):
                self.send_json({"error": "当前口令不匹配，或新口令长度不符合要求（16–256 字符）"}, 400)
                return
            salt = secrets.token_hex(16)
            digest = password_digest(new_password, salt)
            try:
                helper_call({"action": "save_auth_hash", "salt": salt, "hash": digest, "iterations": PBKDF2_ITERATIONS})
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 503)
                return
            with LOCK:
                SESSIONS.clear()
            self.send_json({"passwordChanged": True}, 200, {"Set-Cookie": "grok_admin_session=; HttpOnly; Path=/; SameSite=Strict; Max-Age=0"})
            return
        if path == "/api/updates/check":
            self.start_job("update-check", {"action": "updates_check"}, 180)
            return
        if path == "/api/updates/plan":
            self.start_job("update-plan", {"action": "update_plan"}, 90)
            return
        if path == "/api/updates/simulate":
            try:
                data = helper_call({"action": "apt_simulate", "package": payload.get("package"), "candidate": payload.get("candidate")}, timeout=75)
                self.send_json(data)
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if path == "/api/updates/apply":
            if payload.get("confirm") is not True:
                self.send_json({"error": "请先确认更新操作"}, 400)
                return
            kind = payload.get("kind")
            if kind == "apt" and payload.get("snapshotConfirmed") is not True:
                self.send_json({"error": "系统包更新前请在阿里云控制台创建 ECS 快照"}, 400)
                return
            action = {"action": "apply_update", "kind": kind, "package": payload.get("package"), "candidate": payload.get("candidate"), "snapshotConfirmed": payload.get("snapshotConfirmed") is True}
            self.start_job("update-apply", action, 1900)
            return
        self.send_json({"error": "操作不存在"}, 404)

    def start_job(self, kind: str, payload: dict[str, Any], timeout: int) -> None:
        with JOBS_LOCK:
            if any(job.get("state") in ("queued", "running") for job in JOBS.values()):
                self.send_json({"error": "已有更新任务正在运行"}, 409)
                return
            job_id = str(uuid.uuid4())
            JOBS[job_id] = {"id": job_id, "kind": kind, "state": "queued", "created": int(time.time())}
            # Keep only the newest 30 job summaries.
            for old_id in sorted(JOBS, key=lambda key: JOBS[key].get("created", 0))[:-30]:
                if JOBS[old_id].get("state") not in ("queued", "running"):
                    JOBS.pop(old_id, None)
        JOB_POOL.submit(run_job, job_id, payload, timeout)
        self.send_json({"id": job_id, "state": "queued"}, 202)


def main() -> None:
    if not ORIGIN.startswith("http://") or not HOST or "/" in HOST:
        raise SystemExit("GROK_ADMIN_ORIGIN must be the exact public http origin")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()
