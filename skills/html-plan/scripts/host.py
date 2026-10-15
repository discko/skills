#!/usr/bin/env python3
"""One native message in, one response out, then exit."""
import json
import os
import struct
import sys

from core import EXTENSION_ID, MAX_MESSAGE, PlanError, handle_message


def read_exact(stream, size):
    chunks = bytearray()
    while len(chunks) < size:
        part = stream.read(size - len(chunks))
        if not part:
            raise PlanError("INVALID_MESSAGE", "消息不完整。")
        chunks.extend(part)
    return bytes(chunks)


def serve(source, target, origin=None):
    try:
        if origin is not None and origin != "chrome-extension://" + EXTENSION_ID + "/":
            raise PlanError("INVALID_ORIGIN", "扩展 ID 与 host 不匹配。")
        size = struct.unpack("=I", read_exact(source, 4))[0]
        if not 0 < size <= MAX_MESSAGE:
            raise PlanError("INVALID_MESSAGE", "消息长度超出限制。")
        message = json.loads(read_exact(source, size).decode("utf-8"))
        result = handle_message(message)
    except PlanError as exc:
        result = exc.response()
    except (ValueError, UnicodeError):
        result = {"ok": False, "code": "INVALID_MESSAGE", "message": "JSON 消息无法解析。"}
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        result = {"ok": False, "code": "IO_ERROR", "message": "文件读写失败，请检查文件位置和写入权限。"}
    except Exception as exc:
        print(repr(exc), file=sys.stderr)
        result = {"ok": False, "code": "HOST_ERROR", "message": "保存程序发生错误，当前输入已保留。"}
    payload = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    target.write(struct.pack("=I", len(payload)) + payload)
    target.flush()


if __name__ == "__main__":
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    serve(sys.stdin.buffer, sys.stdout.buffer, sys.argv[1] if len(sys.argv) > 1 else None)
