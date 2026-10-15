"""HTML Plan file format and transactional feedback storage. Python stdlib only."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import url2pathname

VERSION = "0.3.0"
HOST_NAME = "com.html_plan.host"
EXTENSION_ID = "hlheonemgicdhgjghbfepkiddnlbmhml"
PROTOCOL = "html-plan/v1"
BEGIN = b"<!-- HTMLPLAN_STATE_BEGIN -->"
END = b"<!-- HTMLPLAN_STATE_END -->"
MAX_MESSAGE = 4 * 1024 * 1024
MAX_FILE = 32 * 1024 * 1024


class PlanError(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details

    def response(self):
        return {"ok": False, "code": self.code, "message": str(self), **self.details}


def safe_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).replace("<", "\\u003c")


def state_block(state):
    return (BEGIN + b'\n<script id="html-plan-state" type="application/json">\n'
            + safe_json(state).encode("utf-8") + b"\n</script>\n" + END)


def integer(value):
    return type(value) is int and 0 <= value <= 9007199254740991


def validate_review(review):
    fields = {"decisions", "comments", "struck", "edits", "seen", "note"}
    if not isinstance(review, dict) or set(review) != fields:
        raise PlanError("INVALID_REVIEW", "反馈字段不完整或包含不支持的字段。")
    for key in ("decisions", "comments", "edits"):
        values = review[key]
        if not isinstance(values, dict) or len(values) > 2000:
            raise PlanError("INVALID_REVIEW", "反馈条目数量或格式不正确。")
        for item_id, value in values.items():
            if not isinstance(item_id, str) or not 1 <= len(item_id) <= 200:
                raise PlanError("INVALID_REVIEW", "反馈条目 ID 不正确。")
            valid = isinstance(value, str) and len(value) <= 200000
            if key == "decisions":
                valid = valid or type(value) is bool or (isinstance(value, list) and len(value) <= 2000
                    and all(isinstance(v, str) and len(v) <= 200000 for v in value)
                    and len(value) == len(set(value)))
            if not valid:
                raise PlanError("INVALID_REVIEW", "选择值需为文本、布尔值或不重复的文本数组；评论与编辑需为文本。")
    for key in ("struck", "seen"):
        if (not isinstance(review[key], list) or len(review[key]) > 2000
                or any(not isinstance(x, str) or not 1 <= len(x) <= 200 for x in review[key])):
            raise PlanError("INVALID_REVIEW", "反馈列表不正确。")
    if not isinstance(review["note"], str) or len(review["note"]) > 200000:
        raise PlanError("INVALID_REVIEW", "整体意见格式不正确。")
    return review


def empty_review():
    return {"decisions": {}, "comments": {}, "struck": [], "edits": {}, "seen": [], "note": ""}


def parse_document(data):
    if len(data) > MAX_FILE or data.count(BEGIN) != 1 or data.count(END) != 1:
        raise PlanError("INVALID_DOCUMENT", "文件过大或反馈区块标记不唯一。")
    start, finish = data.index(BEGIN), data.index(END) + len(END)
    head = re.search(br"<head\b[^>]*>", data, re.I)
    close = re.search(br"</head\s*>", data, re.I)
    if not head or not close or not head.end() <= start < finish <= close.start():
        raise PlanError("INVALID_DOCUMENT", "反馈区块必须位于 head 中。")
    match = re.fullmatch(
        br'\s*<script id="html-plan-state" type="application/json">\s*(.*?)\s*</script>\s*',
        data[start + len(BEGIN):finish - len(END)], re.S)
    if not match or data.count(b'id="html-plan-state"') != 1:
        raise PlanError("INVALID_DOCUMENT", "反馈 JSON 区块格式不正确。")
    try:
        state = json.loads(match[1].decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise PlanError("INVALID_DOCUMENT", "反馈 JSON 无法解析。") from exc
    if not isinstance(state, dict) or state.get("schemaVersion") != 1:
        raise PlanError("INVALID_DOCUMENT", "不支持的 HTML Plan 格式。")
    for key in ("planId", "documentId"):
        if not isinstance(state.get(key), str) or not re.fullmatch(r"[\w-]{1,100}", state[key]):
            raise PlanError("INVALID_DOCUMENT", "计划标识不正确。")
    for key in ("documentRevision", "reviewRevision"):
        if not integer(state.get(key)):
            raise PlanError("INVALID_DOCUMENT", "计划版本不正确。")
    validate_review(state.get("review"))
    return state, start, finish


def path_from_url(value):
    if not isinstance(value, str):
        raise PlanError("INVALID_PATH", "缺少本地文件 URL。")
    url = urlsplit(value)
    if url.scheme != "file" or url.netloc not in ("", "localhost") or url.query or url.fragment:
        raise PlanError("INVALID_PATH", "只支持本机 file URL。")
    try:
        path = Path(url2pathname(url.path)).resolve(strict=True)
    except (OSError, ValueError) as exc:
        raise PlanError("FILE_NOT_FOUND", "文件不存在或已移动。") from exc
    if path.suffix.lower() not in (".html", ".htm") or not path.is_file():
        raise PlanError("INVALID_PATH", "目标必须是 HTML 文件。")
    return path


@contextlib.contextmanager
def file_lock(path, timeout=5):
    # Lock a stable side object: locking the target inode fails after os.replace.
    # OS releases locks after crashes. Never unlink the shared lock while in use.
    root = Path(tempfile.gettempdir()) / "html-plan-locks"
    root.mkdir(exist_ok=True)
    name = hashlib.sha256(os.path.normcase(str(path)).encode()).hexdigest()
    with (root / name).open("a+b") as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise PlanError("FILE_BUSY", "另一操作正在保存，请稍后重试。")
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def atomic_replace(path, data):
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def handle_message(message):
    if not isinstance(message, dict) or message.get("protocol") != PROTOCOL:
        raise PlanError("INVALID_MESSAGE", "不支持的通信协议。")
    if message.get("action") == "ping":
        return {"ok": True, "version": VERSION, "protocol": PROTOCOL, "capabilities": ["typed-decisions"]}
    if message.get("action") != "save":
        raise PlanError("INVALID_MESSAGE", "不支持的操作。")
    request_id = message.get("requestId")
    if not isinstance(request_id, str) or not re.fullmatch(r"[\w-]{1,100}", request_id):
        raise PlanError("INVALID_MESSAGE", "缺少有效请求 ID。")
    review = validate_review(message.get("review"))
    if not integer(message.get("expectedReviewRevision")):
        raise PlanError("INVALID_MESSAGE", "缺少反馈版本。")
    path = path_from_url(message.get("fileUrl"))
    fingerprint = hashlib.sha256(safe_json({k: message.get(k) for k in (
        "planId", "documentId", "documentRevision", "expectedReviewRevision", "review"
    )}).encode()).hexdigest()
    with file_lock(path):
        with path.open("rb") as source:
            original = source.read(MAX_FILE + 1)
        state, start, finish = parse_document(original)
        for key in ("planId", "documentId", "documentRevision"):
            if type(message.get(key)) is not type(state[key]) or message[key] != state[key]:
                raise PlanError("DOCUMENT_CHANGED", "文件中的计划已变化；当前输入已保留，请另存反馈后重新打开。")
        previous = state.get("lastRequest", {})
        if previous.get("id") == request_id:
            if previous.get("hash") != fingerprint:
                raise PlanError("INVALID_MESSAGE", "同一请求 ID 的内容发生变化。")
            return {"ok": True, "reviewRevision": state["reviewRevision"], "savedAt": state.get("savedAt"), "replayed": True}
        if message["expectedReviewRevision"] != state["reviewRevision"]:
            raise PlanError("REVISION_CONFLICT", "保存被拒绝：其他页面已更新此文件。当前输入已保留。",
                            expectedReviewRevision=message["expectedReviewRevision"],
                            actualReviewRevision=state["reviewRevision"])
        state["review"] = review
        state["reviewRevision"] += 1
        state["savedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state["lastRequest"] = {"id": request_id, "hash": fingerprint}
        atomic_replace(path, original[:start] + state_block(state) + original[finish:])
        return {"ok": True, "reviewRevision": state["reviewRevision"], "savedAt": state["savedAt"]}
