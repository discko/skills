# Skills

[中文](README.md) | English

A collection of reusable AI assistant skills. Each skill has its own instructions, resources, and version; install only the ones you need.

## Skill catalog

| Skill | Category | Purpose | Current version |
| --- | --- | --- | --- |
| [HTML Plan](skills/html-plan/README.en.md) | Plan review and information gathering | Turn implementation plans or open questions into interactive HTML and collect choices, comments, and edits | 0.3.0 |

HTML Plan supports two uses, which can be combined on one page:

- **Plan review:** present proposed behavior, trade-offs, implementation steps, and validation before work begins.
- **Open questions and information checks:** create prefilled forms or tables for users to complete, correct, and confirm unknown details, mappings, or field lists.

## Install HTML Plan

[Download HTML Plan 0.3.0 ZIP](https://github.com/discko/skills/releases/download/html-plan%2Fv0.3.0/html-plan-0.3.0.zip) · [English guide](skills/html-plan/README.en.md) · [中文使用说明](skills/html-plan/README.md)

Copy this prompt into an AI assistant that can access local files and run commands:

```text
Install HTML Plan 0.3.0 from https://github.com/discko/skills/releases/download/html-plan%2Fv0.3.0/html-plan-0.3.0.zip
Download and extract the ZIP. Read html-plan/skills/html-plan/SKILL.md and install the complete html-plan skill directory into this assistant's skill directory (for Codex, the default is ~/.codex/skills/html-plan).
Follow the skill instructions to initialize local saving. Check for Python 3.9+ and Chrome; explain any missing dependencies first. Provide the stable Chrome extension directory and guide me through loading the extension and enabling "Allow access to file URLs".
Use syntax/format checks and local diagnostics only by default. Do not launch a browser, take screenshots, or perform visual checks. Summarize what was installed and any remaining manual steps.
```

**Full functionality—saving feedback back into the original HTML—requires the Chrome extension included in the skill package and the Python native host.** macOS and Windows are supported. Chrome is the only supported extension target; there are currently no plans to develop extensions for other browsers.

Without the extension, users can still review the HTML, copy feedback JSON into chat, or download an HTML copy containing feedback. Clipboard support depends on the browser environment. If your chat client cannot access local files or run commands, install manually.

## Repository layout

```text
skills/
  html-plan/       # Complete skill: SKILL.md, bilingual READMEs, scripts, extension, templates
README.md         # Chinese catalog
README.en.md      # English catalog
install.py        # Installation shortcut for HTML Plan
package.py        # Release packaging for HTML Plan
tests/            # Maintenance tests for HTML Plan
```

READMEs are for users; `SKILL.md` is for the assistant. Reading every README is not required during normal skill use.

Skills are versioned independently, using tags such as `<skill>/v<version>` (for example, `html-plan/v0.3.0`). Install using the ZIP asset attached to the corresponding Release.
