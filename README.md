# Skills

中文 | [English](README.en.md)

这里收集可复用的 AI 助手 Skills。每个 Skill 有独立的说明、资源和版本；按需安装其中一个即可。

## Skill 目录

| Skill | 分类 | 用途 | 当前版本 |
| --- | --- | --- | --- |
| [HTML Plan](skills/html-plan/README.md) | 计划审阅与信息核对 | 把实施方案或待确认项生成交互式 HTML，收集选择、备注和修改意见 | 0.3.1 |

HTML Plan 支持两类用法，也可以在一页中混合：

- **生成计划**：在开发或实施前展示方案、行为、取舍和验证方式，让用户审阅。
- **生成待确认项**：把未知项、映射关系或字段清单整理成预填表单或表格，让用户逐项补充、纠正和确认。

## 安装 HTML Plan

[下载 HTML Plan 最新版 ZIP](https://github.com/discko/skills/releases/download/html-plan%2Flatest/html-plan.zip) · [中文使用说明](skills/html-plan/README.md) · [English guide](skills/html-plan/README.en.md)

复制下面的提示词到具备本地文件与命令执行能力的 AI 助手中：

```text
请安装 HTML Plan 最新稳定版：下载并解压 https://github.com/discko/skills/releases/download/html-plan%2Flatest/html-plan.zip
读取压缩包中 html-plan/skills/html-plan/SKILL.md，将完整的 html-plan Skill 目录安装到当前助手的 Skill 目录（Codex 默认是 ~/.codex/skills/html-plan）。
请按 Skill 内的说明初始化本机保存环境，检查 Python 3.9+ 和 Chrome；如果缺少依赖，先说明。提供 Chrome 扩展的稳定安装目录，指导我加载扩展并开启“允许访问文件网址”。
默认只做语法、格式和本机诊断，不启动浏览器、不截图或做视觉检查。安装后说明完成了什么、还有哪些需我手动操作。
```

**使用完整功能（将反馈原地保存回 HTML）需要安装 Skill 包内的 Chrome 扩展和 Python 本地保存程序。** 支持 macOS 与 Windows；目前仅提供 Chrome 扩展，暂无其他浏览器插件的开发计划。

没有扩展时仍可打开 HTML 审阅，复制反馈 JSON 回聊天或下载带反馈的 HTML 副本；剪贴板能力取决于浏览器环境。普通网页聊天若不能访问本机文件或执行命令，需要你手动安装。

## 仓库结构

```text
skills/
  html-plan/       # 完整 Skill：SKILL.md、双语 README、脚本、扩展与模板
README.md         # 中文目录
README.en.md      # English catalog
install.py        # 当前 HTML Plan 的安装快捷入口
package.py        # 当前 HTML Plan 的发布包构建入口
tests/            # 当前 HTML Plan 的维护测试
```

README 面向使用者；`SKILL.md` 面向助手。日常使用无需把 README 全部加载到助手上下文。

各 Skill 独立版本发布，标签采用 `<skill>/v<version>`，例如 `html-plan/v0.3.1`。版本标签与历史附件保持不变。每个 Skill 另有一个由维护者更新的 `<skill>/latest` 标签及 Release，使用固定附件名（如 `html-plan.zip`），供安装提示词使用。它不是 GitHub 仓库级的 Latest 标记；多个 Skill 可以各自维护这一入口。需要锁定版本时使用对应版本 Release 的 ZIP。

## 来源与致谢

HTML Plan 的交互式计划审阅设计受到 [Thariq Shihipar 的 html-plan](https://github.com/anthropics/claude-plugins-community/tree/main/html-plan) 启发。感谢其对计划组织与人机反馈流程的探索；本项目另行实现了生成器、页面运行时和本地保存机制。详见 [HTML Plan 来源说明](skills/html-plan/README.md#来源与致谢)。
