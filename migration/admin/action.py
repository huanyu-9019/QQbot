#!/usr/bin/python3
"""Root-only, fixed-action helper for the public Grok administration panel."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import stat
import sqlite3
from contextlib import closing
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


HERMES = Path("/home/hermes")
CONFIG = HERMES / ".hermes/config.yaml"
PROACTIVE_CONFIG = HERMES / "qq-proactive-config.json"
PERSONA_JS = HERMES / "qq-memory.mjs"
PERSONA_TEXT = HERMES / "qq-persona.md"
BACKUPS = Path("/var/lib/grok-admin-panel/backups")
AUDIT = Path("/var/lib/grok-admin-panel/audit.jsonl")
HERMES_BIN = HERMES / ".local/bin/hermes"
USER_MEMORY = Path('/opt/jiangsheng-astrbot/runtime/data/legacy/qq-user-memory')
RELATIONSHIP_MEMORY = HERMES / "qq-relationship"
APT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$")

CONFIG_FILES = {
    "persona": PERSONA_TEXT,
    "persona_source": PERSONA_JS,
    "interaction": HERMES / "qq-interaction-config.json",
    "media": HERMES / "qq-media-config.json",
    "online_stickers": HERMES / "qq-online-stickers.json",
    "learned_stickers": HERMES / "qq-learned-stickers.json",
    "hermes_config": CONFIG,
    "proactive": PROACTIVE_CONFIG,
}

FEATURE_FIELDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "queueEnabled": ("interaction", ("queue", "enabled")),
    "priorityLane": ("interaction", ("queue", "priorityLane")),
    "coalesceGroupText": ("interaction", ("queue", "coalesceGroupText")),
    "groupEnabled": ("interaction", ("group", "enabled")),
    "typingEnabled": ("interaction", ("typing", "enabled")),
    "recentImagesEnabled": ("interaction", ("recentImages", "enabled")),
    "imagesEnabled": ("media", ("imagesEnabled",)),
    "stickersEnabled": ("media", ("stickersEnabled",)),
    "onlineStickersEnabled": ("online_stickers", ("enabled",)),
    "networkStickersEnabled": ("online_stickers", ("networkEnabled",)),
    "learnedStickersEnabled": ("learned_stickers", ("enabled",)),
}

ALLOWED_SERVICES = {
    "hermes-api": "hermes-qq-api.service",
    "qq-bridge": "qq-hermes-bridge.service",
}


class ActionError(Exception):
    pass


def run(argv: list[str], *, timeout: int = 12, user: str | None = None,
        input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    command = argv if user is None else ["runuser", "-u", user, "--", *argv]
    env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": str(HERMES)}
    try:
        return subprocess.run(
            command, input=input_text, text=True, capture_output=True,
            timeout=timeout, check=False, cwd=str(HERMES), env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise ActionError("操作超时") from exc
    except OSError as exc:
        raise ActionError("系统操作不可用") from exc


def checked_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ActionError("服务器配置无法读取或格式无效") from exc


def set_nested(data: dict[str, Any], keys: tuple[str, ...], value: bool) -> None:
    current: Any = data
    for key in keys[:-1]:
        if not isinstance(current, dict) or key not in current:
            raise ActionError("配置结构与预期不符")
        current = current[key]
    if not isinstance(current, dict) or not isinstance(current.get(keys[-1]), bool):
        raise ActionError("配置开关与预期不符")
    current[keys[-1]] = value


def backup_files(names: list[str]) -> str:
    BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S") + f"-{time.time_ns() % 1_000_000:06d}"
    directory = BACKUPS / stamp
    directory.mkdir(mode=0o700)
    manifest: dict[str, Any] = {"id": stamp, "created": dt.datetime.now().astimezone().isoformat(), "files": []}
    try:
        for name in names:
            path = CONFIG_FILES[name]
            if path.is_file():
                shutil.copy2(path, directory / f"{name}.bak")
                os.chmod(directory / f"{name}.bak", 0o600)
                manifest["files"].append(name)
        (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False) + "\n", encoding="utf-8")
        os.chmod(directory / "manifest.json", 0o600)
        return stamp
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


def atomic_write(path: Path, content: bytes) -> None:
    if not path.exists():
        raise ActionError("目标配置不存在")
    old = path.stat()
    fd, temp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temp_name, old.st_uid, old.st_gid)
        os.chmod(temp_name, stat.S_IMODE(old.st_mode))
        os.replace(temp_name, path)
        dir_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def extract_inline_persona(source: str) -> str:
    match = re.search(r"^export const persona = (\"(?:\\.|[^\"\\])*\");\s*$", source, re.MULTILINE)
    if not match:
        raise ActionError("找不到当前人格定义；未修改文件")
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ActionError("当前人格格式无法安全迁移；未修改文件") from exc
    if not isinstance(value, str) or not value.strip():
        raise ActionError("当前人格为空；未修改文件")
    return value


def get_persona() -> str:
    if PERSONA_TEXT.exists():
        return PERSONA_TEXT.read_text(encoding="utf-8")
    return extract_inline_persona(PERSONA_JS.read_text(encoding="utf-8"))


def migrate_persona_if_needed() -> str:
    if PERSONA_TEXT.exists():
        return "already-migrated"
    source = PERSONA_JS.read_text(encoding="utf-8")
    current = extract_inline_persona(source)
    pattern = re.compile(r"^export const persona = (\"(?:\\.|[^\"\\])*\");\s*$", re.MULTILINE)
    updated, count = pattern.subn("export const persona = readFileSync('/home/hermes/qq-persona.md', 'utf8');", source, count=1)
    if count != 1:
        raise ActionError("人格接入点与预期不符；未修改文件")
    if not re.search(r"import\s*\{[^}]*\breadFileSync\b[^}]*\}\s*from\s*['\"]node:fs['\"]", updated):
        if re.search(r"\breadFileSync\b", source):
            raise ActionError("人格模块已使用 readFileSync；未修改文件")
        updated = "import { readFileSync } from 'node:fs';\n" + updated
    stamp = backup_files(["persona_source"])
    persona_target = PERSONA_TEXT
    old_persona = PERSONA_JS.stat()
    fd, temp_name = tempfile.mkstemp(prefix=".qq-persona.", dir=str(HERMES))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(current)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temp_name, old_persona.st_uid, old_persona.st_gid)
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, persona_target)
        atomic_write(PERSONA_JS, updated.encode("utf-8"))
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        if persona_target.exists():
            persona_target.unlink()
        raise
    return stamp


def hermes_config_get(key: str, timeout: int = 12) -> str:
    result = run([str(HERMES_BIN), "config", "get", key], timeout=timeout, user="hermes")
    if result.returncode != 0:
        raise ActionError("Hermes 配置读取失败")
    return result.stdout.strip()


def model_info() -> dict[str, Any]:
    if is_astrbot():
        import urllib.request
        try:
            data = json.load(urllib.request.urlopen('http://127.0.0.1:8650/health', timeout=4))
        except Exception:
            data = {}
        return {'primary': 'qq-chat', 'fallback': [r.get('model') for r in data.get('routes', [])], 'available': ['qq-chat']}

    primary = hermes_config_get("model.default")
    fallback_raw = hermes_config_get("fallback_providers")
    fallback = []
    for line in fallback_raw.splitlines():
        match = re.match(r"\s*model:\s*['\"]?([^'\"#\s]+)", line)
        if match and MODEL_RE.fullmatch(match.group(1)):
            fallback.append(match.group(1))
    custom_raw = hermes_config_get("custom_providers")
    available = {primary}
    for line in custom_raw.splitlines() + fallback_raw.splitlines():
        match = re.match(r"\s*model:\s*['\"]?([^'\"#\s]+)", line)
        if match and MODEL_RE.fullmatch(match.group(1)):
            available.add(match.group(1))
    return {
        "primary": primary,
        "fallback": fallback,
        "available": sorted(available),
    }


def read_features() -> dict[str, bool]:
    data = {name: checked_json(CONFIG_FILES[file_key]) for name, (file_key, _path) in FEATURE_FIELDS.items()}
    result: dict[str, bool] = {}
    for name, (file_key, path) in FEATURE_FIELDS.items():
        value: Any = data[name]
        for key in path:
            if not isinstance(value, dict):
                raise ActionError("对话配置结构与预期不符")
            value = value.get(key)
        if not isinstance(value, bool):
            raise ActionError("对话配置开关与预期不符")
        result[name] = value
    return result


def service_state(unit: str) -> dict[str, Any]:
    result = run(["systemctl", "show", unit, "-p", "ActiveState", "-p", "SubState", "-p", "NRestarts"])
    values = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    state = values.get("ActiveState", "unknown")
    return {
        "active": state == "active",
        "state": state,
        "substate": values.get("SubState", "unknown"),
        "restarts": int(values["NRestarts"]) if values.get("NRestarts", "").isdigit() else 0,
    }


def is_astrbot():
    marker = Path('/etc/jiangsheng-runtime')
    return marker.exists() and marker.read_text().strip() == 'astrbot'


def restart_checked(service: str, timeout: int = 60) -> dict[str, Any]:
    unit = 'jiangsheng-astrbot.service' if is_astrbot() else ALLOWED_SERVICES[service]
    if is_astrbot():
        result = run(['/usr/bin/python3', '-c', "import sys;sys.path.insert(0,'/home/hermes');import importlib.util;s=importlib.util.spec_from_file_location('release','/home/hermes/qq-evolution-release.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.sync_astrbot()"], timeout=60)
        if result.returncode:
            raise ActionError('AstrBot 人格与兼容模块同步失败')
    result = run(["systemctl", "restart", unit], timeout=timeout)
    state = service_state(unit)
    if result.returncode != 0 or not state["active"]:
        raise ActionError(f"{service} 重载后未恢复运行")
    return state


def journal_count(unit: str, pattern: str) -> int:
    result = run(["journalctl", "-q", "-u", unit, "--since", "24 hours ago", "--grep", pattern, "--no-pager", "-o", "cat"], timeout=15)
    if result.returncode not in (0, 1):
        return 0
    return sum(1 for line in result.stdout.splitlines() if line)


def status() -> dict[str, Any]:
    load = Path("/proc/loadavg").read_text().split()[:3]
    mem_total = mem_available = 0
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            mem_total = int(line.split()[1])
        elif line.startswith("MemAvailable:"):
            mem_available = int(line.split()[1])
    disk = os.statvfs("/")
    total_gb = round(disk.f_blocks * disk.f_frsize / (1024 ** 3), 1)
    free_gb = round(disk.f_bavail * disk.f_frsize / (1024 ** 3), 1)
    model = model_info()
    return {
        "runtime": "astrbot" if is_astrbot() else "hermes",
        "services": {
            "hermesApi": service_state("jiangsheng-astrbot.service" if is_astrbot() else "hermes-qq-api.service"),
            "qqBridge": service_state("qq-chat-router.service" if is_astrbot() else "qq-hermes-bridge.service"),
            "napcat": service_state("napcat-qq.service"),
            "modelNotice": service_state("qq-model-switch-qzone.service"),
        },
        "model": model,
        "metrics": {
            "load": load,
            "memoryTotalMiB": round(mem_total / 1024),
            "memoryAvailableMiB": round(mem_available / 1024),
            "diskTotalGiB": total_gb,
            "diskFreeGiB": free_gb,
            "modelFallbacks24h": journal_count("hermes-qq-api.service", "Model fallback:"),
            "primaryRestores24h": journal_count("hermes-qq-api.service", "Primary runtime restored for new turn:"),
        },
        "checkedAt": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def settings() -> dict[str, Any]:
    return {
        "persona": get_persona(),
        "features": read_features(),
        "model": model_info(),
        "proactive": checked_json(PROACTIVE_CONFIG),
    }


def save_proactive(values: Any) -> dict[str, Any]:
    if is_astrbot():
        raise ActionError("当前使用 AstrBot；该旧版设置已停用，请通过 AstrBot 配置和受控发布修改。")
    if not isinstance(values, dict) or set(values) != {"enabled", "idleDays", "repeatDays"}:
        raise ActionError("主动互动设置字段无效")
    if (not isinstance(values["enabled"], bool)
            or not isinstance(values["idleDays"], int) or isinstance(values["idleDays"], bool) or not 1 <= values["idleDays"] <= 14
            or not isinstance(values["repeatDays"], int) or isinstance(values["repeatDays"], bool) or not 1 <= values["repeatDays"] <= 30):
        raise ActionError("主动互动天数超出允许范围")
    backup_id = backup_files(["proactive"])
    previous = PROACTIVE_CONFIG.read_bytes()
    atomic_write(PROACTIVE_CONFIG, (json.dumps(values, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    try:
        restart_checked("qq-bridge", timeout=30)
    except ActionError:
        atomic_write(PROACTIVE_CONFIG, previous)
        try:
            restart_checked("qq-bridge", timeout=30)
        except ActionError:
            pass
        raise ActionError("主动互动设置未生效；已恢复原配置")
    return {"backupId": backup_id, "reloaded": "qq-bridge", "proactive": values}


def save_persona(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 200_000:
        raise ActionError("人格不能为空，且最多 200 KB")
    backup_id = migrate_persona_if_needed()
    if backup_id == "already-migrated":
        backup_id = backup_files(["persona"])
    old_persona = PERSONA_TEXT.read_bytes()
    atomic_write(PERSONA_TEXT, value.encode("utf-8"))
    try:
        restart_checked("qq-bridge", timeout=30)
    except ActionError:
        atomic_write(PERSONA_TEXT, old_persona)
        try:
            restart_checked("qq-bridge", timeout=30)
        except ActionError:
            pass
        raise ActionError("桥接重载失败；人格文件已恢复")
    return {"backupId": backup_id, "reloaded": "qq-bridge"}


def save_features(values: Any) -> dict[str, Any]:
    if is_astrbot():
        raise ActionError("当前使用 AstrBot；该旧版设置已停用，请通过 AstrBot 配置和受控发布修改。")
    if not isinstance(values, dict) or not values or set(values) - set(FEATURE_FIELDS):
        raise ActionError("包含不支持的能力设置")
    if any(not isinstance(value, bool) for value in values.values()):
        raise ActionError("能力开关必须为布尔值")
    files = sorted({FEATURE_FIELDS[name][0] for name in values})
    backup_id = backup_files(files)
    changed: dict[str, tuple[Path, bytes]] = {}
    try:
        docs = {key: checked_json(CONFIG_FILES[key]) for key in files}
        for name, value in values.items():
            file_key, path = FEATURE_FIELDS[name]
            set_nested(docs[file_key], path, value)
        for key, doc in docs.items():
            path = CONFIG_FILES[key]
            changed[path] = (path, path.read_bytes())
            atomic_write(path, (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        restart_checked("qq-bridge", timeout=30)
    except Exception:
        for path, content in changed.values():
            atomic_write(path, content)
        try:
            restart_checked("qq-bridge", timeout=30)
        except ActionError:
            pass
        raise
    return {"backupId": backup_id, "reloaded": "qq-bridge"}


def set_model(model: Any) -> dict[str, Any]:
    if is_astrbot():
        raise ActionError("当前使用 AstrBot；该旧版设置已停用，请通过 AstrBot 配置和受控发布修改。")
    if not isinstance(model, str) or not MODEL_RE.fullmatch(model):
        raise ActionError("模型标识无效")
    info = model_info()
    if model not in info["available"]:
        raise ActionError("只能选择当前已配置的模型")
    backup_id = backup_files(["hermes_config"])
    result = run([str(HERMES_BIN), "config", "set", "model.default", model], timeout=20, user="hermes")
    if result.returncode != 0:
        raise ActionError("模型配置未通过 Hermes 校验")
    check = run([str(HERMES_BIN), "config", "check"], timeout=30, user="hermes")
    if check.returncode != 0:
        restore_file_from_backup(backup_id, "hermes_config")
        raise ActionError("Hermes 配置检查失败；已恢复原配置")
    try:
        restart_checked("hermes-api")
    except ActionError:
        restore_file_from_backup(backup_id, "hermes_config")
        try:
            restart_checked("hermes-api")
        except ActionError:
            pass
        raise ActionError("API 重载失败；已恢复原配置")
    return {"backupId": backup_id, "reloaded": "hermes-api", "model": model}


def restart_service(name: Any) -> dict[str, Any]:
    if name not in ALLOWED_SERVICES:
        raise ActionError("该服务不允许从管理页重载")
    state = restart_checked(name)
    return {"service": name, "state": state}


def list_backups() -> list[dict[str, Any]]:
    if not BACKUPS.exists():
        return []
    result = []
    for directory in sorted(BACKUPS.iterdir(), reverse=True)[:50]:
        manifest_path = directory / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            names = manifest.get("files", [])
            if not isinstance(names, list) or any(name not in CONFIG_FILES for name in names):
                continue
            result.append({"id": manifest.get("id", directory.name), "created": manifest.get("created", ""), "files": names})
        except (OSError, json.JSONDecodeError):
            continue
    return result


def restore_file_from_backup(backup_id: str, name: str) -> None:
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}-[0-9]{6}", backup_id) or name not in CONFIG_FILES:
        raise ActionError("备份标识无效")
    directory = BACKUPS / backup_id
    manifest = checked_json(directory / "manifest.json")
    if manifest.get("id") != backup_id or name not in manifest.get("files", []):
        raise ActionError("备份中没有该配置")
    source = directory / f"{name}.bak"
    content = source.read_bytes()
    target = CONFIG_FILES[name]
    atomic_write(target, content)


def restore_backup(backup_id: Any, names: Any) -> dict[str, Any]:
    if not isinstance(backup_id, str) or not isinstance(names, list) or not names:
        raise ActionError("恢复参数无效")
    if any(not isinstance(name, str) or name not in CONFIG_FILES for name in names):
        raise ActionError("备份文件范围无效")
    rollback_id = backup_files(names)
    for name in names:
        restore_file_from_backup(backup_id, name)
    services = set()
    if any(name in names for name in ("persona", "persona_source", "interaction", "media", "online_stickers", "learned_stickers", "proactive")):
        services.add("qq-bridge")
    if "hermes_config" in names:
        services.add("hermes-api")
    for service in sorted(services):
        restart_checked(service)
    return {"backupId": rollback_id, "restored": names, "reloaded": sorted(services)}


def apt_updates() -> list[dict[str, str]]:
    result = run(["apt", "list", "--upgradable"], timeout=30)
    rows = []
    for line in result.stdout.splitlines()[1:]:
        # apt's first token is package/repository; only expose package and version fields.
        match = re.match(r"^([a-z0-9][a-z0-9+.-]*)/[^ ]+\s+([^ ]+)\s+([^ ]+)\s+\[upgradable from: ([^]]+)\]", line)
        if match:
            rows.append({"name": match.group(1), "candidate": match.group(2), "architecture": match.group(3), "installed": match.group(4)})
    return rows[:100]


def updates_check() -> dict[str, Any]:
    if is_astrbot():
        return {"hermesVersion": "AstrBot 4.29.4", "hermesUpdate": "由 Codex 测试后发布", "apt": apt_updates()}
    version = run([str(HERMES_BIN), "--version"], timeout=10, user="hermes")
    check = run([str(HERMES_BIN), "update", "--check"], timeout=120, user="hermes")
    safe = "up-to-date" if "up to date" in (check.stdout + check.stderr).lower() else "available-or-unknown"
    return {"hermesVersion": version.stdout.strip()[:80] if version.returncode == 0 else "unknown", "hermesUpdate": safe, "apt": apt_updates()}


def updates_snapshot() -> dict[str, Any]:
    if is_astrbot():
        return {"hermesVersion": "AstrBot 4.29.4", "hermesUpdate": "由 Codex 测试后发布", "apt": apt_updates()}
    version = run([str(HERMES_BIN), "--version"], timeout=10, user="hermes")
    return {"hermesVersion": version.stdout.strip()[:80] if version.returncode == 0 else "unknown", "apt": apt_updates()}


def apt_simulate(package: Any, candidate: Any) -> dict[str, Any]:
    if not isinstance(package, str) or not APT_NAME_RE.fullmatch(package):
        raise ActionError("软件包名称无效")
    if not isinstance(candidate, str) or not re.fullmatch(r"[A-Za-z0-9.+:~_-]{1,120}", candidate):
        raise ActionError("候选版本无效")
    current = next((item for item in apt_updates() if item["name"] == package and item["candidate"] == candidate), None)
    if current is None:
        raise ActionError("软件包候选版本已变化，请重新检查更新")
    result = run(["apt-get", "-s", "install", "--no-install-recommends", f"{package}={candidate}"], timeout=60)
    if result.returncode != 0:
        raise ActionError("无法生成系统包模拟计划")
    lines = result.stdout.splitlines()
    changed = sum(line.startswith("Inst ") for line in lines)
    removed = sum(line.startswith("Remv ") for line in lines)
    return {"package": package, "candidate": candidate, "changedPackages": changed, "removedPackages": removed}


def save_auth_hash(salt: Any, digest: Any, iterations: Any) -> dict[str, Any]:
    if (not isinstance(salt, str) or not re.fullmatch(r"[a-f0-9]{32}", salt)
            or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
            or not isinstance(iterations, int) or iterations != 600_000):
        raise ActionError("认证配置无效")
    auth_path = Path("/etc/grok-admin-panel/auth.json")
    auth_path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    content = json.dumps({"salt": salt, "hash": digest, "iterations": iterations}, separators=(",", ":")) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=".auth.", dir=str(auth_path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        import grp
        gid = grp.getgrnam("grok-admin").gr_gid
        os.chown(temp_name, 0, gid)
        os.chmod(temp_name, 0o640)
        os.replace(temp_name, auth_path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
    return {"saved": True}


def apply_update(kind: Any, package: Any = None, candidate: Any = None, snapshot_confirmed: Any = False) -> dict[str, Any]:
    if kind == "hermes" and is_astrbot():
        raise ActionError("旧 Hermes 更新已停用；AstrBot 由 Codex 验证后发布。")
    if kind == "hermes":
        backup_id = backup_files(["hermes_config"])
        # Hermes itself creates its supported pre-update state snapshot and archive.
        result = run([str(HERMES_BIN), "update", "--yes", "--backup", "--no-gateway-restart"], timeout=1800, user="hermes")
        if result.returncode != 0:
            raise ActionError("Hermes 更新失败；请在更新页查看状态并按备份恢复")
        restart_checked("hermes-api", timeout=90)
        return {"backupId": backup_id, "kind": "hermes", "state": "completed"}
    if kind != "apt" or not snapshot_confirmed:
        raise ActionError("系统包更新必须确认已创建 ECS 快照")
    if not isinstance(package, str) or not APT_NAME_RE.fullmatch(package):
        raise ActionError("软件包名称无效")
    if not isinstance(candidate, str) or not re.fullmatch(r"[A-Za-z0-9.+:~_-]{1,120}", candidate):
        raise ActionError("候选版本无效")
    current = next((item for item in apt_updates() if item["name"] == package and item["candidate"] == candidate), None)
    if current is None:
        raise ActionError("软件包候选版本已变化，请重新检查更新")
    result = run(["apt-get", "install", "-y", "--no-install-recommends", f"{package}={candidate}"], timeout=1800)
    if result.returncode != 0:
        raise ActionError("系统包更新失败；请检查服务器软件包状态")
    return {"kind": "apt", "package": package, "state": "completed", "hostRebooted": False}



def memory_support():
    """Load audited stdlib-only code, without initializing the AstrBot plugin."""
    import importlib
    import types
    local = Path(__file__).resolve().parents[1]/'plugin'
    folder = local if (local/'person_memory.py').is_file() else Path('/home/hermes/migration/plugin')
    name = '_jiangsheng_admin_memory'
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(folder)]
        sys.modules[name] = package
    return importlib.import_module(name+'.policy'), importlib.import_module(name+'.person_memory')


def native_profile(qq: str, database=None) -> dict[str, Any]:
    database = Path(database or '/opt/jiangsheng-astrbot/runtime/data/plugin_data/astrbot_plugin_private_companion/installations/jiangsheng/runtime/companion-v2.sqlite3')
    if not database.is_file():
        return {'status': 'unavailable', 'facts': []}
    try:
        _, support = memory_support()
        values = support.native_memories(database, qq, limit=100)
        facts = [{'category': x.get('category') or ('关系理解' if x['kind'] == 'adopted_relationship_interpretation' else '已保存记忆'),
                  'value': x.get('value'), 'detail': x['text'], 'updatedAt': x['updated_at'],
                  'sourceCount': x.get('sourceCount'), 'confidence': x.get('confidence'),
                  'attribution': x.get('attribution'), 'kind': x['kind']} for x in values]
        return {'status': 'available', 'facts': facts}
    except (sqlite3.Error, ValueError, TypeError, OSError):
        return {'status': 'unavailable', 'facts': []}



def profile_read(qq: Any) -> dict[str, Any]:
    if not isinstance(qq, str) or not qq.isdigit() or not 5 <= len(qq) <= 12:
        raise ActionError("QQ 号格式无效")
    filename = hashlib.sha256(("user:" + qq).encode("utf-8")).hexdigest() + ".json"

    def read(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    memory = read(USER_MEMORY / filename)
    relationship = read(RELATIONSHIP_MEMORY / filename)
    profile = memory.get("profile") if isinstance(memory.get("profile"), dict) else {}
    profile_keys = (
        "preferredName", "privateNickname", "groupNicknames",
        "relationships", "chatHabits", "preferences",
    )
    relationship_keys = (
        "stage", "familiarity", "trust", "affection", "boundary",
        "lastMood", "milestones", "turns", "updatedAt",
    )
    policy, support = memory_support()
    portrait = policy.person_portrait(profile, relationship)
    history_path = Path('/opt/jiangsheng-astrbot/runtime/data/jiangsheng-person-memory.sqlite3')
    try:
        current_attitude = support.read_attitude(history_path, qq)
        if current_attitude:
            portrait['relationship']['attitude'] = current_attitude
    except (sqlite3.Error, ValueError, OSError):
        # Keep historical data explicitly labelled when the current estimate fails.
        pass
    try:
        portrait['history'] = support.interaction_timeline(history_path, qq)
        portrait['history']['status'] = 'available'
    except (sqlite3.Error, ValueError, OSError):
        portrait['history'] = {'status': 'unavailable', 'excerpts': []}
    return {
        "portrait": portrait,
        "profile": {key: profile[key] for key in profile_keys if key in profile},
        "relationship": {key: relationship[key] for key in relationship_keys if key in relationship},
        "native": native_profile(qq),
        "readOnly": True,
    }


def audit(action: str, succeeded: bool) -> None:
    try:
        BACKUPS.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        line = json.dumps({"time": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "action": action, "ok": succeeded}, ensure_ascii=False)
        fd = os.open(AUDIT, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as stream:
            stream.write(line + "\n")
    except OSError:
        pass


def dispatch(request: dict[str, Any]) -> dict[str, Any]:
    action = request.get("action")
    if action == "profile":
        return profile_read(request.get("qq"))
    if action == "status":
        return status()
    if action == "settings":
        return settings()
    if action == "save_persona":
        result = save_persona(request.get("persona"))
        audit(action, True)
        return result
    if action == "save_features":
        result = save_features(request.get("features"))
        audit(action, True)
        return result
    if action == "save_proactive":
        result = save_proactive(request.get("proactive"))
        audit(action, True)
        return result
    if action == "set_model":
        result = set_model(request.get("model"))
        audit(action, True)
        return result
    if action == "restart_service":
        result = restart_service(request.get("service"))
        audit(action, True)
        return result
    if action == "backups":
        return {"items": list_backups()}
    if action == "restore_backup":
        result = restore_backup(request.get("backupId"), request.get("files"))
        audit(action, True)
        return result
    if action == "updates_check":
        return updates_check()
    if action == "updates_snapshot":
        return updates_snapshot()
    if action == "apt_simulate":
        return apt_simulate(request.get("package"), request.get("candidate"))
    if action == "update_plan":
        result = run([str(HERMES_BIN), "update", "--plan"], timeout=60, user="hermes")
        if result.returncode != 0:
            raise ActionError("无法生成 Hermes 更新计划")
        # The raw planner output may contain local paths; return only status and line count.
        return {"state": "ready", "summaryLines": sum(bool(line.strip()) for line in result.stdout.splitlines())}
    if action == "apply_update":
        result = apply_update(request.get("kind"), request.get("package"), request.get("candidate"), request.get("snapshotConfirmed"))
        audit(action, True)
        return result
    if action == "save_auth_hash":
        return save_auth_hash(request.get("salt"), request.get("hash"), request.get("iterations"))
    raise ActionError("不支持的管理动作")


def main() -> None:
    raw = sys.stdin.buffer.read(300_001)
    if len(raw) > 300_000:
        raise SystemExit("request too large")
    try:
        request = json.loads(raw.decode("utf-8"))
        if not isinstance(request, dict):
            raise ValueError("request must be an object")
        output = dispatch(request)
        sys.stdout.write(json.dumps({"ok": True, "data": output}, ensure_ascii=False) + "\n")
    except ActionError as exc:
        action = "invalid"
        try:
            action = str(request.get("action", "invalid"))[:40]
        except Exception:
            pass
        audit(action, False)
        sys.stdout.write(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False) + "\n")
    except Exception:
        audit("internal-error", False)
        sys.stdout.write('{"ok":false,"error":"操作失败；未记录敏感详情"}\n')


if __name__ == "__main__":
    main()
