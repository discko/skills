#!/usr/bin/env python3
"""Install, diagnose or remove the local HTML Plan bridge (stdlib only)."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import struct
import subprocess
import sys

from core import EXTENSION_ID, HOST_NAME, PROTOCOL, VERSION
from plan import build

SKILL = Path(__file__).resolve().parent.parent


def system_paths(system=None, home=None):
    system, home = system or platform.system(), Path(home or Path.home())
    if system == "Darwin":
        base = home / "Library/Application Support"
        return base / "HtmlPlan", base / "Google/Chrome/NativeMessagingHosts" / (HOST_NAME + ".json")
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
        root = base / "HtmlPlan"
        return root, root / (HOST_NAME + ".json")
    raise ValueError("此版本支持 macOS 和 Windows；其他平台请自行注册 native host。")


def extension_id():
    manifest = json.loads((SKILL / "assets/extension/manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(base64.b64decode(manifest["key"])).hexdigest()[:32]
    value = "".join(chr(97 + int(c, 16)) for c in digest)
    if value != EXTENSION_ID:
        raise ValueError("扩展公钥和 host ID 不一致。")
    return value


def windows_quote(value):
    # Batch expands % even inside quotes. Disable delayed expansion for ! paths.
    if any(c in str(value) for c in ('"', '\r', '\n')):
        raise ValueError("安装路径包含不支持的字符。")
    return '"' + str(value).replace('%', '%%') + '"'


def launcher_text(system, python, host):
    if system == "Windows":
        return "@echo off\r\nchcp 65001 >nul\r\nsetlocal DisableDelayedExpansion\r\n" + windows_quote(python) + " " + windows_quote(host) + " %*\r\n"
    return "#!/bin/sh\nexec " + shlex.quote(str(python)) + " " + shlex.quote(str(host)) + ' "$@"\n'


def register_windows(manifest_path):
    import winreg
    key = "Software\\Google\\Chrome\\NativeMessagingHosts\\" + HOST_NAME
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as registry:
        winreg.SetValueEx(registry, "", 0, winreg.REG_SZ, str(manifest_path))


def install(root, manifest_path, system, register=True, skill_dir=None):
    extension_id()
    root, manifest_path = root.resolve(), manifest_path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "native-host").mkdir(exist_ok=True)
    for name in ("host.py", "core.py"):
        shutil.copy2(SKILL / "scripts" / name, root / "native-host" / name)
    shutil.copytree(SKILL / "assets/extension", root / "extension", dirs_exist_ok=True)
    launch = root / ("launch.bat" if system == "Windows" else "launch.sh")
    # Keep the active interpreter path (including a venv) rather than resolving symlinks.
    python = Path(sys.executable).absolute()
    launch.write_bytes(launcher_text(system, python, root / "native-host/host.py").encode("utf-8"))
    if system != "Windows":
        launch.chmod(0o755)
    manifest = {"name": HOST_NAME, "description": "HTML Plan local save helper", "path": str(launch),
                "type": "stdio", "allowed_origins": ["chrome-extension://" + EXTENSION_ID + "/"]}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if system == "Windows" and register:
        register_windows(manifest_path)
    test_path = root / "connection-test.html"
    if not test_path.exists():
        build(json.loads((SKILL / "assets/example.json").read_text(encoding="utf-8")), test_path)
    if skill_dir:
        destination = Path(skill_dir).expanduser().resolve()
        if destination != SKILL:
            if destination.is_relative_to(SKILL) or SKILL.is_relative_to(destination):
                raise ValueError("Skill 安装目录不能与源目录互相包含。")
            if (destination / "SKILL.md").exists() and "name: html-plan" not in (destination / "SKILL.md").read_text(encoding="utf-8"):
                raise ValueError("目标位置已存在其他 Skill。")
            shutil.copytree(SKILL, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (root / "installation.json").write_text(json.dumps({"version": VERSION, "python": str(python),
        "manifest": str(manifest_path), "system": system, "skillSource": str(SKILL)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "root": str(root), "extensionDirectory": str(root / "extension"),
            "extensionId": EXTENSION_ID, "testPage": test_path.as_uri(),
            "next": ["Chrome 打开 chrome://extensions，开启开发者模式。",
                     "加载已解压的扩展，选择 extensionDirectory。",
                     "进入扩展详情，开启允许访问文件网址。",
                     "打开 testPage，保存反馈并重新打开确认。若此前已打开测试页，需要刷新。"]}


def doctor(root, manifest_path, system, check_registry=True):
    checks = []
    def record(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    record("python", sys.version_info >= (3, 9), sys.executable)
    try:
        config = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = Path(config["path"])
        record("registration", config["name"] == HOST_NAME and config.get("allowed_origins") == ["chrome-extension://" + EXTENSION_ID + "/"] and entry.is_file(), str(manifest_path))
        if system == "Windows" and check_registry:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Google\\Chrome\\NativeMessagingHosts\\" + HOST_NAME) as key:
                registered = winreg.QueryValueEx(key, "")[0]
            record("registry", Path(registered).resolve() == manifest_path.resolve(), registered)
        packet = json.dumps({"protocol": PROTOCOL, "action": "ping"}).encode()
        command = [str(entry), "chrome-extension://" + EXTENSION_ID + "/"]
        result = subprocess.run(command, input=struct.pack("=I", len(packet)) + packet, capture_output=True, timeout=10)
        size = struct.unpack("=I", result.stdout[:4])[0]
        response = json.loads(result.stdout[4:4 + size])
        record("native-launcher", result.returncode == 0 and response.get("ok") and len(result.stdout) == size + 4, response)
        manifest = json.loads((root / "extension/manifest.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256(base64.b64decode(manifest["key"])).hexdigest()[:32]
        record("extension-files", "".join(chr(97 + int(c, 16)) for c in digest) == EXTENSION_ID, manifest["version"])
    except (OSError, ValueError, KeyError, struct.error, subprocess.SubprocessError) as exc:
        record("bridge", False, str(exc))
    return {"ok": all(x["ok"] for x in checks), "checks": checks,
            "browserVerified": False, "next": "本检查验证本地注册和启动；扩展是否加载、文件授权与真实保存，请通过扩展弹窗和 connection-test.html 验证。"}


def uninstall(root, manifest_path, system, register=True):
    # Only remove our registered files, never the surrounding folder or user plans.
    receipt = root / "installation.json"
    if not receipt.exists():
        return {"ok": True, "message": "未找到安装记录，无需卸载。"}
    config = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    expected = root / ("launch.bat" if system == "Windows" else "launch.sh")
    if config and (config.get("name") != HOST_NAME or Path(config.get("path", "")).resolve() != expected.resolve()):
        raise ValueError("注册信息已指向其他位置，未删除。")
    if system == "Windows" and register:
        import winreg
        key = "Software\\Google\\Chrome\\NativeMessagingHosts\\" + HOST_NAME
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as registry:
                registered = winreg.QueryValueEx(registry, "")[0]
            if Path(registered).resolve() != manifest_path.resolve():
                raise ValueError("注册表已指向其他安装，未删除。")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except FileNotFoundError:
            pass
    manifest_path.unlink(missing_ok=True)
    expected.unlink(missing_ok=True)
    for name in ("host.py", "core.py"):
        (root / "native-host" / name).unlink(missing_ok=True)
    receipt.unlink()
    return {"ok": True, "message": "本地 host 已卸载。扩展、测试页和 Skill 保留；可在 Chrome 手动移除扩展。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "doctor", "uninstall"))
    parser.add_argument("--root", type=Path, help="可选的稳定安装目录")
    parser.add_argument("--manifest-dir", type=Path, help="用于测试或自定义 Chrome 的注册目录")
    parser.add_argument("--no-register", action="store_true", help="Windows 测试时跳过注册表写入")
    parser.add_argument("--skill-dir", type=Path, help="同时复制完整 Skill 到此目录")
    args = parser.parse_args()
    system = platform.system()
    root, manifest_path = system_paths()
    root = args.root.expanduser().resolve() if args.root else root
    if args.manifest_dir:
        manifest_path = args.manifest_dir.expanduser().resolve() / (HOST_NAME + ".json")
    elif system == "Windows":
        manifest_path = root / (HOST_NAME + ".json")
    if args.command == "install":
        result = install(root, manifest_path, system, not args.no_register, args.skill_dir)
    elif args.command == "doctor":
        result = doctor(root, manifest_path, system, not args.no_register)
    else:
        result = uninstall(root, manifest_path, system, not args.no_register)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
