# 计划输入与反馈格式

`scripts/plan.py build` 接受 UTF-8 JSON，输出自包含 HTML。脚本拒绝覆盖已有输出。默认输出目录是项目根 `.plan/`，用户指定位置优先。

最小输入：

```json
{
  "title": "任务标题",
  "summary": "目的与范围",
  "claims": [{
    "id": "queue-limit",
    "title": "用户能同时保留多少待处理任务",
    "description": "约束与失败时的行为。",
    "decisions": [{"id": "max-jobs", "label": "任务上限", "type": "select", "options": ["50", "500"], "default": "50"}],
    "exhibits": [{"id": "queue-flow", "label": "处理流程", "type": "flow", "content": "提交 → 校验 → 入队 → 执行"}],
    "children": []
  }]
}
```

所有 claim、表格 row、decision、exhibit 的 `id` 必须全局唯一，小写字母开头，后接小写字母、数字、连字符，最多 80 字符。ID 表示语义，不用章节位置命名。

- 顶层 `layout` 为 `cards`（默认，保留旧格式）或 `flat`（平铺）；claim 可覆盖并向子条目继承。折叠条目支持 `expanded: true/false`，默认只展开第一层；平铺条目始终可见。
- `claims` 最多嵌套三层，这是上限而非推荐模板。条目默认带评论和划除，可设置 `feedback: false` 关闭容器反馈；表格行各自有备注。
- `decisions` 的 `type`、默认值和反馈类型见下表。所有字段需 `id`、`label`，可选 `hint` 解释默认值或口径。`options` 为不重复的非空字符串列表。

| type | 用途 | default 与反馈值 |
| --- | --- | --- |
| `radio` | 少量互斥选项 | 字符串；默认 `""` 表示未选择，其余需属于 options |
| `select` | 较多或较长候选 | 字符串；缺省选第一项，建议显式设置 default |
| `checkbox` | 是/否开关 | 布尔值；默认 false，不表示“未知” |
| `checkboxes` | 多选 | 不重复的字符串数组；默认 []，成员需属于 options |
| `text`、`number` | 短文本或数值输入 | 字符串，默认 `""`；number 仍按字符串保存以保留空值 |
| `textarea` | 多行补充 | 字符串，默认 `""` |

radio 如需允许回到未定状态，在 options 中加入“待确认”。多选按页面选项顺序收集。不得把布尔值或数组字符串化。
- `exhibits`：`text` 普通说明、`code` 代码、`flow` 文本调用链、`mockup` 静态 HTML 原型。原型在没有脚本权限的 sandbox iframe 中展示，不得依赖外部资源。
- `editable: true` 将 exhibit 显示为可编辑文本；预填的编辑会覆盖本轮 exhibit 的初始文本，模型应核对是否仍适用。
- 真实代码使用 `source: {"file":"src/foo.py","start":10,"end":30}`，配合 `--root`。脚本检查真实路径和行号。`content` 此时被真实摘录替换。
- 任意文本按文本渲染；只有显式 `mockup` 内容作为沙箱 HTML。

基础示例：`assets/example.json`；涵盖两类用途与所有控件的示例：`assets/mixed-review.json`。

## 可编辑表格

claim 可添加 `table`，与普通 decisions/exhibits 并存；建议容器使用 flat。每一行只维护一个对象，同一关系不在多处重复编辑。

```json
{
  "id": "mappings",
  "title": "核对调用关系",
  "layout": "flat",
  "feedback": false,
  "table": {
    "columns": [{"key": "source", "label": "现有证据"}, {"key": "project", "label": "所属项目"}],
    "rows": [{
      "id": "caller-search",
      "label": "search-api",
      "description": "从配置读取，项目归属待核对",
      "cells": {
        "source": "配置项 service.name",
        "project": {"id": "search-project", "label": "项目", "type": "radio", "options": ["项目A", "项目B", "待确认"], "default": "待确认"}
      }
    }]
  }
}
```

`columns` 非空，key 在表内唯一；`rows` 可为空，row.id 全局唯一且可迁移备注和查看状态。`cells` 的键对应列 key，值是只读字符串或一个完整 decision 对象；缺失单元格显示为空。表格带每行备注、搜索以及全部／有修改或评论／未查看筛选，筛选不会丢弃隐藏行反馈。修改筛选相对生成时的 `decisionDefaults` 判断，已保存后仍可查看修改；筛选在用户操作搜索或筛选框时重新应用，编辑中的行不会突然消失。


## 文件中的状态

head 的唯一 `HTMLPLAN_STATE_BEGIN/END` 注释区块内包含：

```json
{
  "schemaVersion": 1,
  "generatorVersion": "0.3.0",
  "decisionDefaults": {},
  "planId": "同一主题各版本共享的 UUID",
  "documentId": "每个新 HTML 独有的 UUID",
  "documentRevision": 1,
  "reviewRevision": 0,
  "review": {
    "decisions": {},
    "comments": {},
    "struck": [],
    "edits": {},
    "seen": [],
    "note": ""
  },
  "previousFeedback": []
}
```

保存时 host 自己递增 `reviewRevision` 并记录 `savedAt` 与 `lastRequest`。客户端不控制落盘版本。`lastRequest` 用于最近一次保存的幂等重试。重试旧请求而文件已被其他请求更新，仍会冲突。

版本绑定通过 planId、documentId、documentRevision、reviewRevision 完成。内容作者必须遵守每轮生成新文件的约定；协议不针对手工修改正文但保留全部版本标识的行为提供检测。

新版本保留完整上一轮反馈，并仅向当前已知的 ID 预填值。删除的条目、失效的选项在历史反馈中可查；不自动进行语义合并。新版 seen 清空，避免把曾看过旧计划当作看过新版。字段类型不兼容或选项失效时不迁移该字段（多选有任一失效选项就不迁移整组），历史中保留原值，由模型核对并设置新版 default。`decisionDefaults` 记录生成时的预设值，不能证明用户批准。

下载副本保留文档身份和当前反馈，但没有改变原文件或向 Codex发送消息。若采用下载副本，明确告知 Codex 实际副本路径。

## 复制到聊天的反馈包

“复制反馈 JSON”始终可用，每次点击收集当前表单，输出以下结构：

```json
{
  "type": "html-plan-review",
  "schemaVersion": 1,
  "title": "计划标题",
  "planId": "主题 UUID",
  "documentId": "当前文档 UUID",
  "documentRevision": 1,
  "baseReviewRevision": 0,
  "review": {"decisions": {}, "comments": {}, "struck": [], "edits": {}, "seen": [], "note": ""}
}
```

baseReviewRevision 是页面最后已知的反馈版本，不表示本次已保存；包不包含 savedAt、lastRequest 或历史反馈。复制操作只提示成功或失败，不改写文件、不清除未保存状态，也不自动发送消息。剪贴板不可用时不展示手动复制框，可重试或下载 HTML 副本。

`build --previous <原HTML> --feedback <反馈.json>` 校验类型、协议版本、文档身份、反馈版本及 review 结构后，将粘贴反馈用于新版预填。旧文件保持不变，新版历史条目增加 `feedbackSource: "clipboard"`，其中 reviewRevision 仍表示反馈所基于的文件版本。版本不一致时拒绝直接导入，由模型核对差异与用户意图后处理，不修改版本号绕过校验。

协议上限：单次反馈消息 4 MiB，HTML 32 MiB。JSON 中 `<` 编码为 `\u003c`，防止用户文本提前关闭 script 标签。

0.2.0 继续使用 schemaVersion 1 与 html-plan/v1 协议；decisions 的值新增布尔值和字符串数组，comments/edits 仍限字符串。host ping 通过 `capabilities: ["typed-decisions"]` 声明支持，旧 host 需重新安装升级；复制反馈不依赖 host。

## 页面主题

页头提供跟随系统／浅色／深色选择。初始通过 `prefers-color-scheme` 跟随系统及其变化，手动选择仅影响当前页面；切回“跟随系统”恢复自动切换。主题不属于 spec 或 review，不使用浏览器存储，保存反馈和下载副本均不记忆手动选择。静态 mockup 的沙箱内容保留其自有配色，打印使用浅色。
