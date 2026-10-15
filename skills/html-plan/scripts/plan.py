#!/usr/bin/env python3
"""Build a new self-contained plan, or read its saved feedback."""
from __future__ import annotations

import argparse
import copy
import html
import json
from pathlib import Path
import re
import sys
import uuid

from components import accepts, default_value, validate_decision, render_decision, render_table
from core import VERSION, PlanError, empty_review, parse_document, safe_json, state_block, validate_review, MAX_MESSAGE

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def escape(value):
    return html.escape(str(value), quote=True)


def validate_spec(spec):
    if not isinstance(spec, dict) or not isinstance(spec.get("title"), str) or not spec["title"].strip():
        raise ValueError("spec 需要非空 title。")
    if not isinstance(spec.get("claims"), list) or not spec["claims"]:
        raise ValueError("spec 需要非空 claims 列表。")
    if spec.get("layout", "cards") not in ("cards", "flat"):
        raise ValueError("layout 支持 cards/flat。")
    ids, claims, decisions, edits = set(), set(), {}, set()

    def register(value):
        if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,79}", value) or value in ids:
            raise ValueError("条目 ID 必须唯一，使用小写字母、数字和连字符：" + str(value))
        ids.add(value)

    def visit(items, depth):
        if not isinstance(items, list) or depth > 3 and items:
            raise ValueError("claims 必须为列表，最多三层。")
        for claim in items:
            register(claim.get("id"))
            claims.add(claim["id"])
            if not isinstance(claim.get("title"), str):
                raise ValueError("每个 claim 需要 title。")
            if claim.get("layout", "cards") not in ("cards", "flat"):
                raise ValueError("layout 支持 cards/flat。")
            for flag in ("expanded", "feedback"):
                if flag in claim and type(claim[flag]) is not bool:
                    raise ValueError(flag + " 必须为布尔值。")
            for decision in claim.get("decisions", []):
                validate_decision(decision, register)
                decisions[decision["id"]] = decision
            table = claim.get("table")
            if table is not None:
                if not isinstance(table, dict) or not isinstance(table.get("columns"), list) or not table["columns"] or not isinstance(table.get("rows"), list):
                    raise ValueError("table 需要非空 columns 和 rows 列表。")
                keys = set()
                for column in table["columns"]:
                    key = column.get("key")
                    if not isinstance(key, str) or not key or key in keys or not isinstance(column.get("label"), str):
                        raise ValueError("表格列需要唯一 key 和 label。")
                    keys.add(key)
                for row in table["rows"]:
                    register(row.get("id"))
                    claims.add(row["id"])
                    if not isinstance(row.get("label"), str) or not isinstance(row.get("cells"), dict) or not set(row["cells"]) <= keys:
                        raise ValueError("表格行需要 label 和匹配列 key 的 cells。")
                    for value in row["cells"].values():
                        if isinstance(value, dict):
                            validate_decision(value, register)
                            decisions[value["id"]] = value
                        elif not isinstance(value, str):
                            raise ValueError("表格单元格为文本或 decision 对象。")
            for exhibit in claim.get("exhibits", []):
                register(exhibit.get("id"))
                if exhibit.get("type", "text") not in ("text", "code", "flow", "mockup"):
                    raise ValueError("exhibit.type 支持 text/code/flow/mockup。")
                if exhibit.get("editable"):
                    edits.add(exhibit["id"])
            visit(claim.get("children", []), depth + 1)
    visit(spec["claims"], 1)
    return claims, decisions, edits


def ground_sources(spec, root):
    """Embed explicit excerpts from real project files; never follow outside root."""
    def visit(claims):
        for claim in claims:
            for exhibit in claim.get("exhibits", []):
                source = exhibit.get("source")
                if source:
                    if root is None:
                        raise ValueError("有 source 的代码片段需要 --root 项目目录。")
                    base = Path(root).resolve()
                    path = (base / source["file"]).resolve(strict=True)
                    if not path.is_relative_to(base):
                        raise ValueError("代码片段必须在项目目录内。")
                    if any(p.startswith(".env") or p in (".git", ".ssh", ".aws") for p in path.relative_to(base).parts) or path.suffix in (".pem", ".key", ".p12"):
                        raise ValueError("不允许嵌入凭据文件。")
                    if path.stat().st_size > 2 * 1024 * 1024:
                        raise ValueError("代码来源文件过大。")
                    lines = path.read_text(encoding="utf-8").splitlines()
                    start, end = source["start"], source["end"]
                    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines) or end - start >= 300:
                        raise ValueError("代码行号不正确或超过 300 行。")
                    exhibit["content"] = "\n".join(lines[start - 1:end])
                    exhibit["label"] = f'{source["file"]}:{start}–{end}'
            visit(claim.get("children", []))
    visit(spec["claims"])


def new_state(spec, previous=None):
    claims, decisions, edits = validate_spec(spec)
    review = empty_review()
    history = []
    if previous:
        old = previous["review"]
        review["comments"] = {k: v for k, v in old["comments"].items() if k in claims}
        review["struck"] = [k for k in old["struck"] if k in claims]
        review["edits"] = {k: v for k, v in old["edits"].items() if k in edits}
        for key, value in old["decisions"].items():
            decision = decisions.get(key)
            if decision and accepts(decision, value):
                review["decisions"][key] = value
        review["note"] = old["note"]
        history = copy.deepcopy(previous.get("previousFeedback", []))
        history.append({"documentId": previous["documentId"], "documentRevision": previous["documentRevision"],
                        "reviewRevision": previous["reviewRevision"], "review": copy.deepcopy(old)})
        if previous.get("feedbackSource") == "clipboard":
            history[-1]["feedbackSource"] = "clipboard"
    return {"schemaVersion": 1, "planId": previous["planId"] if previous else str(uuid.uuid4()),
            "documentId": str(uuid.uuid4()), "documentRevision": previous["documentRevision"] + 1 if previous else 1,
            "reviewRevision": 0, "review": review, "previousFeedback": history,
            "generatorVersion": VERSION, "decisionDefaults": {k: default_value(v) for k, v in decisions.items()}}


def render_claim(claim, number, depth=1, layout="cards"):
    cid = escape(claim["id"])
    layout = claim.get("layout", layout)
    flat = layout == "flat"
    tag = "section" if flat else "details"
    heading = f"h{depth + 1}" if flat else "summary"
    opened = "open" if not flat and claim.get("expanded", depth == 1) else ""
    parts = [f'<{tag} class="claim depth-{depth} {"flat" if flat else ""}" data-claim="{cid}" {opened}>',
             f'<{heading} class="claim-heading"><span class="number">{number}</span><span>{escape(claim["title"])}</span><span class="seen-badge">待查看</span></{heading}>',
             f'<div class="claim-body"><p class="description">{escape(claim.get("description", ""))}</p>']
    parts.extend(render_decision(d) for d in claim.get("decisions", []))
    if claim.get("table"):
        parts.append(render_table(claim["table"]))
    for exhibit in claim.get("exhibits", []):
        eid, content = escape(exhibit["id"]), str(exhibit.get("content", ""))
        parts.append(f'<figure><figcaption>{escape(exhibit.get("label", "设计细节"))}</figcaption>')
        if exhibit.get("editable"):
            parts.append(f'<textarea class="code-edit" aria-label="{escape(exhibit.get("label", "编辑内容"))}" data-edit="{eid}" spellcheck="false">{escape(content)}</textarea>')
        elif exhibit.get("type") == "mockup":
            # Static mockups only: no scripts, same-origin access, navigation or forms.
            parts.append(f'<iframe sandbox="" title="{escape(exhibit.get("label", "界面原型"))}" srcdoc="{escape(content)}"></iframe>')
        else:
            parts.append(f'<pre class="exhibit {escape(exhibit.get("type", "text"))}">{escape(content)}</pre>')
        parts.append('</figure>')
    if claim.get("feedback", True):
        parts.append(f'<div class="feedback"><label>你的意见<textarea data-comment="{cid}" placeholder="补充约束、问题或修改建议…"></textarea></label>'
                 f'<label class="strike-control"><input type="checkbox" data-strike="{cid}">从计划中移除此项</label></div>')
    for i, child in enumerate(claim.get("children", []), 1):
        parts.append(render_claim(child, f"{number}.{i}", depth + 1, layout))
    parts.append(f'</div></{tag}>')
    return "\n".join(parts)


def render(spec, previous=None, root=None):
    spec = copy.deepcopy(spec)
    validate_spec(spec)
    ground_sources(spec, root)
    state = new_state(spec, previous)
    css = (ASSETS / "plan.css").read_text(encoding="utf-8")
    js = (ASSETS / "plan.js").read_text(encoding="utf-8")
    body = "\n".join(render_claim(c, str(i), layout=spec.get("layout", "cards")) for i, c in enumerate(spec["claims"], 1))
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="html-plan" content="1"><title>{escape(spec["title"])}</title>
{state_block(state).decode()}
<style>{css}</style></head><body>
<header><div class="brand">HTML PLAN <span>LOCAL REVIEW</span></div><div class="header-tools"><div class="version">PLAN v{state["documentRevision"]}</div><label class="theme-control" for="theme-mode">主题<select id="theme-mode"><option value="system" selected>跟随系统</option><option value="light">浅色 · Light</option><option value="dark">深色 · Dark</option></select></label></div></header>
<main><section class="intro"><p class="eyebrow">阅读内容，确认待定项</p><h1>{escape(spec["title"])}</h1><p>{escape(spec.get("summary", ""))}</p></section>
<section class="review-guide"><span>01 阅读计划</span><span>02 修改选项与批注</span><span>03 保存或复制反馈回聊天</span></section>
<nav class="toolbar"><button id="expand">展开全部</button><button id="collapse">收起全部</button><button id="next-decision">下一个待确认项</button><span id="review-count"></span></nav>
<section id="claims">{body}</section>
<section class="overall"><h2>整体意见</h2><textarea id="overall-note" placeholder="还有哪些需要调整？"></textarea></section>
<details id="history"><summary>上一轮反馈记录</summary><pre id="history-content"></pre></details>
<footer>反馈只在点击保存时写入本文件。新版计划将生成新的 HTML。</footer></main>
<aside class="savebar"><div><strong id="save-status" role="status" aria-live="polite">正在检查连接…</strong><small id="connection-status">连接浏览器扩展</small></div><div class="actions"><button id="check">检查连接</button><button id="copy-review">复制反馈 JSON</button><button id="download">下载含反馈的 HTML</button><button id="save" class="primary">保存反馈</button></div></aside>
<div id="copy-toast" role="status" aria-live="polite" hidden></div>
<script>{js}</script></body></html>'''


def apply_feedback(previous, feedback_path):
    if previous is None:
        raise ValueError("--feedback 需要同时提供 --previous 对应的 HTML。")
    with Path(feedback_path).open("rb") as source:
        data = source.read(MAX_MESSAGE + 1)
    if len(data) > MAX_MESSAGE:
        raise ValueError("反馈 JSON 超过 4 MiB。")
    feedback = json.loads(data)
    if not isinstance(feedback, dict) or feedback.get("type") != "html-plan-review" or type(feedback.get("schemaVersion")) is not int or feedback["schemaVersion"] != 1:
        raise ValueError("不是支持的 HTML Plan 反馈包。")
    for key in ("planId", "documentId", "documentRevision"):
        if type(feedback.get(key)) is not type(previous[key]) or feedback[key] != previous[key]:
            raise ValueError("反馈与 --previous 的文档不匹配：" + key)
    revision = feedback.get("baseReviewRevision")
    if type(revision) is not int or revision != previous["reviewRevision"]:
        raise ValueError("反馈版本与文件不一致，请先核对差异，不能直接导入。")
    validate_review(feedback.get("review"))
    result = copy.deepcopy(previous)
    result["review"] = copy.deepcopy(feedback["review"])
    result["feedbackSource"] = "clipboard"
    return result


def build(spec, output, previous_path=None, root=None, feedback_path=None):
    previous = parse_document(Path(previous_path).read_bytes())[0] if previous_path else None
    if feedback_path:
        previous = apply_feedback(previous, feedback_path)
    data = render(spec, previous, root).encode("utf-8")
    parse_document(data)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite an earlier plan, even on concurrent generation.
    with output.open("xb") as target:
        target.write(data)
    return output.resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("build")
    create.add_argument("spec", type=Path)
    create.add_argument("output", type=Path)
    create.add_argument("--previous", type=Path)
    create.add_argument("--root", type=Path)
    create.add_argument("--feedback", type=Path, help="从聊天粘贴的反馈 JSON，须与 --previous 的文档和反馈版本匹配")
    read = sub.add_parser("review")
    read.add_argument("html", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        print(build(json.loads(args.spec.read_text(encoding="utf-8")), args.output, args.previous, args.root, args.feedback))
    else:
        print(safe_json(parse_document(args.html.read_bytes())[0]))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, PlanError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
