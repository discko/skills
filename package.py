#!/usr/bin/env python3
"""Build a shareable HTML Plan ZIP with one html-plan root directory."""
from pathlib import Path
import json
import zipfile

root = Path(__file__).resolve().parent
version = json.loads((root / "plugin.json").read_text(encoding="utf-8"))["version"]
output = root / "dist" / f"html-plan-{version}.zip"
output.parent.mkdir(exist_ok=True)
files = [root / name for name in ("plugin.json", "README.md", "README.en.md", "install.py", "package.py")]
for directory in ("skills/html-plan", "tests", ".github"):
    files += [p for p in (root / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(files):
        archive.write(file, Path("html-plan") / file.relative_to(root))
print(output)
