"""Typed review controls and compact editable tables; no external dependencies."""
import html


def escape(value):
    return html.escape(str(value), quote=True)


def default_value(decision):
    kind = decision.get("type", "select")
    fallback = decision["options"][0] if kind == "select" else False if kind == "checkbox" else [] if kind == "checkboxes" else ""
    value = decision.get("default", fallback)
    if kind == "checkboxes" and isinstance(value, list) and accepts(decision, value):
        return [option for option in decision["options"] if option in value]
    return value


def accepts(decision, value):
    kind = decision.get("type", "select")
    if kind == "checkbox":
        return type(value) is bool
    if kind == "checkboxes":
        return (isinstance(value, list) and all(isinstance(v, str) and v in decision["options"] for v in value)
                and len(value) == len(set(value)))
    if not isinstance(value, str):
        return False
    if kind in ("select", "radio"):
        return value in decision["options"] or (kind == "radio" and value == "")
    return True


def validate_decision(decision, register):
    if not isinstance(decision, dict):
        raise ValueError("decision 必须为对象。")
    register(decision.get("id"))
    if not isinstance(decision.get("label"), str):
        raise ValueError("decision 需要 label。")
    kind = decision.get("type", "select")
    if kind not in ("select", "radio", "checkbox", "checkboxes", "text", "number", "textarea"):
        raise ValueError("不支持的 decision.type：" + str(kind))
    if kind in ("select", "radio", "checkboxes"):
        options = decision.get("options")
        if (not isinstance(options, list) or not options or len(options) > 2000
                or any(not isinstance(v, str) or not v or len(v) > 200000 for v in options)
                or len(options) != len(set(options))):
            raise ValueError("options 需要唯一的非空文本列表。")
    if not accepts(decision, default_value(decision)):
        raise ValueError("default 的类型或选项不正确：" + decision["id"])


def render_decision(decision, compact=False, context=""):
    did, label = escape(decision["id"]), escape(decision["label"])
    kind, default = decision.get("type", "select"), default_value(decision)
    attrs = f'id="{did}" data-decision="{did}" data-kind="{kind}"'
    accessible = escape((context + " · " if context else "") + decision["label"])
    if kind in ("radio", "checkboxes"):
        inputs = []
        for value in decision["options"]:
            checked = value == default if kind == "radio" else value in default
            inputs.append(f'<label><input type="{"radio" if kind == "radio" else "checkbox"}" name="{did}" value="{escape(value)}" {"checked" if checked else ""}>{escape(value)}</label>')
        control = f'<fieldset {attrs} class="choice-group"><legend>{accessible}</legend><div class="choice-options">' + "".join(inputs) + '</div></fieldset>'
    elif kind == "checkbox":
        control = f'<label class="boolean-choice"><input {attrs} type="checkbox" aria-label="{accessible}" {"checked" if default else ""}>{label}</label>'
    elif kind == "select":
        control = f'<select {attrs} aria-label="{accessible}">' + "".join(
            f'<option value="{escape(v)}" {"selected" if v == default else ""}>{escape(v)}</option>' for v in decision["options"]) + '</select>'
    elif kind == "textarea":
        control = f'<textarea {attrs} aria-label="{accessible}" rows="3">{escape(default)}</textarea>'
    else:
        control = f'<input {attrs} type="{kind}" aria-label="{accessible}" value="{escape(default)}">'
    hint = f'<small class="field-hint">{escape(decision["hint"])}</small>' if decision.get("hint") else ""
    if compact:
        return control + hint
    heading = "" if kind in ("radio", "checkbox", "checkboxes") else f'<label for="{did}">{label}</label>'
    return f'<div class="decision {"decision-options" if not heading else ""}">{heading}<div>{control}{hint}</div></div>'


def render_table(table):
    parts = ['<div class="review-table" data-review-table><div class="table-tools">'
             '<label>搜索<input type="search" data-table-search placeholder="名称、值或备注"></label>'
             '<label>显示<select data-table-filter><option value="all">全部</option><option value="changed">有修改或评论</option>'
             '<option value="unseen">未查看</option></select></label><span data-table-count role="status"></span></div>'
             '<div class="table-scroll" role="region" aria-label="可横向滚动的信息表" tabindex="0"><table><thead><tr><th scope="col">条目</th>']
    parts.extend(f'<th scope="col">{escape(c["label"])}</th>' for c in table["columns"])
    parts.append('<th scope="col">备注</th></tr></thead><tbody>')
    for row in table["rows"]:
        rid = escape(row["id"])
        description = f'<small>{escape(row["description"])}</small>' if row.get("description") else ""
        parts.append(f'<tr data-claim="{rid}" data-review-row><th scope="row"><span class="row-title">{escape(row["label"])}</span>{description}<span class="seen-badge">待查看</span></th>')
        for column in table["columns"]:
            value = row["cells"].get(column["key"], "")
            parts.append('<td>' + (render_decision(value, True, row["label"]) if isinstance(value, dict) else escape(value)) + '</td>')
        parts.append(f'<td><textarea data-comment="{rid}" aria-label="{escape(row["label"])} · 备注" placeholder="补充或解释…" rows="2"></textarea></td></tr>')
    parts.append('</tbody></table></div></div>')
    return "\n".join(parts)
