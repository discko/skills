# HTML Plan

中文 | [English](README.en.md) · [返回 Skill 目录](../../README.md)

将需要反复讨论的方案和待确认信息放进一个可交互的 HTML。用户可以集中填写选择与备注，再把反馈交给助手，减少在聊天中逐条来回确认。

## 适合什么场景

| 用法 | 适合的内容 | 示例提示词 |
| --- | --- | --- |
| 计划审阅 | 开发方案、行为变化、取舍、实施步骤与验证方式 | “用 HTML Plan 生成这次改动的计划，把会影响实现的选择列出来，我确认后再实施。” |
| 待确认项与信息核对 | 字段清单、项目归属、调用关系、尚不明确的需求 | “把这些字段整理成 HTML 核对表，预填已知信息，把未知或冲突项留给我确认。” |

两类内容可混合使用；不强制套三层折叠。已知信息先预填，少量短选项用 radio，重复对象用表格。默认值和“已查看”都不表示用户批准实施。

## 页面功能

- 平铺或折叠条目、可编辑表格，支持搜索与筛选。
- 下拉选择、radio 单选、checkbox 开关、多选、短文本、数值和多行输入。
- 条目／表格行备注、条目划除、可编辑展示内容、整体意见。
- 真实源码摘录、流程文本及静态沙箱原型。
- 默认跟随系统主题，可切换浅色／深色，不记忆选择。
- 显式保存反馈、复制反馈 JSON、下载带反馈的 HTML 副本。
- 修订生成新 HTML，通过稳定 ID 预填兼容的上一轮反馈。

## 安装

[下载最新版 ZIP](https://github.com/discko/skills/releases/download/html-plan%2Flatest/html-plan.zip)。ZIP 中包含完整 Skill、Chrome 扩展、Python 保存程序和安装入口。

### 让助手安装

复制以下提示词：

```text
请安装 HTML Plan 最新稳定版：下载并解压 https://github.com/discko/skills/releases/download/html-plan%2Flatest/html-plan.zip
读取压缩包中 html-plan/skills/html-plan/SKILL.md，将完整的 html-plan Skill 目录安装到当前助手的 Skill 目录（Codex 默认是 ~/.codex/skills/html-plan）。
请按 Skill 内的说明初始化本机保存环境，检查 Python 3.9+ 和 Chrome；如果缺少依赖，先说明。提供 Chrome 扩展的稳定安装目录，指导我加载扩展并开启“允许访问文件网址”。
默认只做语法、格式和本机诊断，不启动浏览器、不截图或做视觉检查。安装后说明完成了什么、还有哪些需我手动操作。
```

### 手动安装

完整本地保存功能需要 **Python 3.9+、Chrome，以及 macOS 或 Windows**。Python 运行部分只依赖标准库，无需 Node.js。

解压 ZIP，进入最外层 `html-plan` 目录，然后运行：

macOS：

```sh
python3 install.py install --skill-dir ~/.codex/skills/html-plan
python3 install.py doctor
```

Windows PowerShell：

```powershell
py -3 install.py install --skill-dir "$env:USERPROFILE\.codex\skills\html-plan"
py -3 install.py doctor
```

使用其他助手时，将 `--skill-dir` 替换为该助手支持的 Skill 路径。只安装 Skill、暂不配置保存环境时，可以复制完整的 `skills/html-plan` 目录到目标位置。

### Chrome 扩展

**要将反馈原地保存回 HTML，必须安装包内的 Chrome 扩展及 Python 本地保存程序。** 扩展当前以“加载已解压的扩展”方式安装；暂无其他浏览器插件的开发计划。

1. 在 Chrome 打开 `chrome://extensions`，开启开发者模式。
2. 点击“加载已解压的扩展”，选择安装器输出的 `extensionDirectory`，不要选择临时解压目录。
3. 在该扩展的详情页开启“允许访问文件网址”。
4. 打开安装器输出的测试页面，手动填写、保存并重新打开核对。

安装器将扩展和 host 放在稳定的用户目录，一次安装可用于多个项目。`doctor` 只验证本机注册、入口和协议，不代表 Chrome 中的完整保存链路已验证。安装命令不会替代 Chrome 的加载与授权操作。

## 日常使用

1. 告诉助手生成计划或整理待确认项。HTML 默认放在项目根 `.plan/`，你指定的路径优先。
2. 打开生成的 HTML，填写选择和意见。需要原地保存时，用已配置扩展的 Chrome 打开本地文件。
3. 点击“保存反馈”，然后回到聊天说明下一步，例如“按反馈修改计划”或“按确认后的方案实施”。
4. 无扩展或内置浏览器中无法保存时，点击“复制反馈 JSON”并粘贴回聊天，或下载副本并告诉助手副本位置。复制不会更新原文件。

例如：“用 HTML Plan 整理项目和调用方的对应关系，一行一个调用方，预填你能确认的信息，未知项标为待确认。”

日常生成默认只做内容、语法和格式规则检查。只有你明确要求时，助手才考虑启动浏览器操作、截图或视觉验证。

## 简要技术说明

- **单文件输出**：HTML 内嵌样式、脚本和 head 中的反馈 JSON；生成后离线可用，无 CDN 依赖。
- **本地保存链路**：页面 → Chrome 扩展 → Python Native Messaging host → 当前 HTML。host 按调用启动，没有常驻 HTTP 服务或监听端口。
- **写入边界**：只在显式点击保存时落盘；在文件锁内检查文档身份及反馈版本，并原子替换 head 中的状态区块。版本冲突会拒绝覆盖并保留页面输入。
- **反馈迭代**：新版 HTML 有新的文档身份，保留历史反馈；稳定 ID 用于预填，字段含义改变时需要重新映射。
- **执行边界**：保存、选择默认值或粘贴 JSON 都不自动批准实施；助手根据聊天指令决定后续动作。

详细输入与反馈格式见 [format.md](references/format.md)，安装与故障诊断见 [setup.md](references/setup.md)。这些技术参考目前以中文提供。

## 更新与维护

安装新版本后重新运行安装命令；Chrome 扩展更新后在扩展管理页重新加载。刷新已打开的计划前先保存或下载未保存的反馈。旧 HTML 不自动替换模板，主题等新能力用于新生成的文件。

仓库根的 `package.py` 构建带版本号的 ZIP，并复制为内容相同的 `dist/html-plan.zip`。当前版本为 **0.3.1**，版本标签是 `html-plan/v0.3.1`。发布时保留版本标签和附件，另将 `html-plan/latest` 标签、对应 Release 的版本说明及 `html-plan.zip` 附件更新到同一版本。`latest` 是手动维护的固定入口，不是 GitHub 自动按 Skill 识别的最新版本。维护模板时可在仓库根运行：

```sh
python3 -m unittest discover -s tests -v
node --test tests/extension.test.cjs tests/plan.test.cjs
```

这些是维护测试，不要求每次生成计划都运行。浏览器测试需另行明确选择，不属于默认安装或生成流程。

## 来源与致谢

本项目的交互式计划审阅设计受到 [Thariq Shihipar 的 html-plan](https://github.com/anthropics/claude-plugins-community/tree/main/html-plan) 启发，该项目收录于 Anthropic 的社区插件仓库。感谢其在按行为组织计划、将决策放在相关条目旁，以及通过评论、划除和结构化反馈连接用户与助手方面的探索。

本项目另行实现了 JSON 输入与 Python 生成器、页面运行时、Chrome 扩展和 Native Messaging 本地保存机制，并扩展了信息核对、可编辑表格及反馈预填等用法。本项目并非 Anthropic 官方插件，也不表示获得其认可或背书。
