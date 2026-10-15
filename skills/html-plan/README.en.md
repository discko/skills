# HTML Plan 0.3.0

[中文](README.md) | English · [Back to the skill catalog](../../README.en.md)

Turn plans and open questions into one interactive HTML document. Users can review choices and leave comments in one place, then return the feedback to the assistant instead of answering every question separately in chat.

## When to use it

| Use | Suitable content | Example prompt |
| --- | --- | --- |
| Plan review | Proposed behavior, trade-offs, implementation steps, and validation | "Create an HTML Plan for this change. Highlight choices that affect implementation and wait for my confirmation before implementing." |
| Open questions and information checks | Field lists, project ownership, caller mappings, and unclear requirements | "Create an HTML review table for these fields. Prefill known information and leave unknown or conflicting items for me to confirm." |

Both uses can coexist on one page. Three levels of nesting are not required. Prefill known facts, use radio buttons for short choices, and use tables for repeated objects. Default values and "viewed" status do not mean approval.

## Page features

- Flat or collapsible sections and editable tables with search and filters.
- Select menus, radio buttons, boolean checkboxes, multiple-choice checkboxes, text, numeric, and multiline inputs.
- Section and row comments, section removal marks, editable exhibits, and overall feedback.
- Source excerpts, textual flows, and static sandboxed mockups.
- System theme by default, with temporary light/dark overrides and no saved preference.
- Explicit local saving, feedback JSON copying, and HTML downloads containing feedback.
- New HTML files for revisions, with compatible previous feedback prefilled by stable IDs.

## Installation

[Download the 0.3.0 ZIP](https://github.com/discko/skills/releases/download/html-plan%2Fv0.3.0/html-plan-0.3.0.zip). The ZIP includes the complete skill, Chrome extension, Python native host, and installation entry point.

### Ask your assistant to install it

Copy this prompt:

```text
Install HTML Plan 0.3.0 from https://github.com/discko/skills/releases/download/html-plan%2Fv0.3.0/html-plan-0.3.0.zip
Download and extract the ZIP. Read html-plan/skills/html-plan/SKILL.md and install the complete html-plan skill directory into this assistant's skill directory (for Codex, the default is ~/.codex/skills/html-plan).
Follow the skill instructions to initialize local saving. Check for Python 3.9+ and Chrome; explain any missing dependencies first. Provide the stable Chrome extension directory and guide me through loading the extension and enabling "Allow access to file URLs".
Use syntax/format checks and local diagnostics only by default. Do not launch a browser, take screenshots, or perform visual checks. Summarize what was installed and any remaining manual steps.
```

### Manual installation

Full local saving requires **Python 3.9+, Chrome, and macOS or Windows**. The Python runtime uses only the standard library; Node.js is not required for normal use.

Extract the ZIP and enter its outermost `html-plan` directory, then run:

macOS:

```sh
python3 install.py install --skill-dir ~/.codex/skills/html-plan
python3 install.py doctor
```

Windows PowerShell:

```powershell
py -3 install.py install --skill-dir "$env:USERPROFILE\.codex\skills\html-plan"
py -3 install.py doctor
```

For other assistants, replace `--skill-dir` with the supported skill directory. To install only the skill without configuring local saving yet, copy the complete `skills/html-plan` directory to that location.

### Chrome extension

**Saving back into the original HTML requires both the included Chrome extension and the Python native host.** The extension is currently installed using Chrome's "Load unpacked" workflow. There are no current plans to develop extensions for other browsers.

1. Open `chrome://extensions` in Chrome and enable Developer mode.
2. Choose "Load unpacked" and select the installer's `extensionDirectory`, not the temporary extraction folder.
3. Enable "Allow access to file URLs" on the extension's details page.
4. Open the test page returned by the installer, manually enter feedback, save it, and reopen the page to verify it.

The installer copies the extension and host to stable user directories. One installation supports multiple projects. `doctor` checks registration, the launcher, and the protocol; it does not prove that saving works through Chrome. Installation commands do not replace Chrome's extension loading and permission steps.

## Everyday workflow

1. Ask the assistant to generate a plan or organize open questions. HTML defaults to the project's `.plan/` directory; your chosen location takes priority.
2. Open the HTML and enter choices and comments. For in-place saving, open the local file in Chrome with the extension configured.
3. Click "保存反馈" (Save feedback), then return to chat and say what to do next—for example, revise the plan or implement the agreed changes.
4. If the extension is unavailable or an embedded browser cannot save, use "复制反馈 JSON" (Copy feedback JSON) and paste it into chat, or download a copy and tell the assistant where it is. Copying does not update the original file.

Example: "Use HTML Plan to map projects to callers, with one caller per row. Prefill verified information and mark unknown fields as pending confirmation."

Normal generation uses content, syntax, and format checks only. Browser automation, screenshots, and visual verification are considered only when you explicitly request them. The bundled interface and technical reference documents are currently in Chinese; this English README explains the workflow but does not imply a fully localized interface.

## How it works

- **Single-file output:** CSS, JavaScript, and feedback JSON in the HTML head are embedded in one file. Generated pages work offline without a CDN.
- **Local save path:** page → Chrome extension → Python Native Messaging host → current HTML file. The host runs on demand, with no persistent HTTP server or listening port.
- **Transactional writes:** saving occurs only on explicit action. A file lock protects document/review version checks and atomic replacement of the state block in the head. Conflicting saves are rejected while page input is retained.
- **Revision handling:** a new HTML revision gets a new document identity and keeps feedback history. Stable IDs support prefilling; changed meanings require deliberate remapping.
- **Execution boundary:** saving, default choices, or pasted JSON do not automatically authorize implementation. The assistant follows the user's next chat instruction.

See [format.md](references/format.md) for input and feedback schemas, and [setup.md](references/setup.md) for installation details and troubleshooting. These references are currently in Chinese.

## Updates and maintenance

Run the installer again after installing a new version; reload the updated extension in Chrome. Save or download pending feedback before refreshing open pages. Existing HTML files keep their embedded template; new features apply to newly generated files.

The repository's `package.py` builds `dist/html-plan-0.3.0.zip`; its version tag is `html-plan/v0.3.0`. When maintaining the template, run these checks from the repository root:

```sh
python3 -m unittest discover -s tests -v
node --test tests/extension.test.cjs tests/plan.test.cjs
```

These are maintenance tests, not a requirement for each generated plan. Browser testing is an explicit opt-in workflow, separate from default installation and generation.
