---
name: workflow
description: Walk through a code audit one issue at a time on Windows with PowerShell, enforcing mandatory before/after preview, explicit user approval per change, individual per-fix commits, and Bash-avoidance (MSYS2 fork emulation can OOM the machine on repeated spawns). Use this skill whenever the user wants to work through a tracked list of code issues from an audit/progress document (AUDIT.md, PROGRESS.md, ISSUES.md, TODO.md, or similar), mentions reviewing fixes "one at a time," asks for turn-by-turn code review with approval gates, or is on Windows and needs strict PowerShell-only tooling. Trigger this even when the user doesn't say the word "audit" — any iterative fix workflow over a pre-identified issue list applies.
---

# Code Audit Workflow

A strict, turn-by-turn workflow for working through a list of pre-identified code issues. Designed for Windows + PowerShell environments where Bash spawning is dangerous, and for users who want full control over every change.

The contract: **one issue per turn, no code written without explicit approval, individual commits, no batching, no scheduled loops.**

---

## Environment rules (read first — violating these has crashed user machines)

**OS: Windows. PowerShell only.**

- **NEVER use the Bash tool.** Git Bash on Windows uses MSYS2 fork emulation, which copies full process memory on every spawn. Repeated spawns OOM the machine. This is not theoretical — it has happened. The Bash tool is unsafe **even when it falls back to PowerShell** on this machine — see "Git on Windows" below.
- For file and directory exploration use **Glob, Grep, Read**. Never run `ls`, `pwd`, `cat`, `head`, `tail`, `find`, or `grep` as shell commands on either shell.
- The working directory is already set. Do **not** run orientation commands like `pwd && ls`. The first action is `Read` on the audit/progress document.
- **No `/loop`, no `ScheduleWakeup`, no cron, no scheduled tasks.** This workflow is strictly turn-by-turn with explicit user approval. If there is an urge to schedule a wake-up, stop.
- **PowerShell syntax:** no heredocs, no `&&` chaining. Use `;` only if sequencing is necessary; prefer separate tool calls.

---

## Git on Windows — fork-bomb hazard (READ BEFORE ANY GIT COMMAND)

Empirical evidence from session 2026-05-12: a single `git ls-files <path>` plus a backgrounded `git branch -a` in this repo spawned **~2500 git.exe processes consuming 93% of RAM and forced a laptop restart**. The Bash tool was set to fall back to PowerShell, yet git still cascaded. Calling git from "PowerShell" does not bypass MSYS2 — the fork emulation lives inside git for Windows itself.

**Mechanisms (from public bug trackers):**

- **MSYS2 sh.exe fork bombs inside git** — hooks / filters / ssh / credential helpers can endlessly spawn `sh.exe`. ([git-for-windows/git#1562](https://github.com/git-for-windows/git/issues/1562))
- **Zombie MSYS children leak RAM** — bash/tee/sed/xargs ~24 KB each, unbounded growth. ([msys2/MSYS2-packages#1335](https://github.com/msys2/MSYS2-packages/issues/1335))
- **IDE git integration amplifies** — VS Code + Copilot reported spawning git.exe to >64 GB RAM; disabling the built-in Git extension stops it. ([microsoft/vscode#271844](https://github.com/microsoft/vscode/issues/271844), [#71085](https://github.com/Microsoft/vscode/issues/71085))
- **Windows Defender real-time scan** serialises every git child spawn; queue grows faster than it drains.
- **fsmonitor daemons** stay running forever (~86 MB each) once `core.fsmonitor=true`. ([microsoft/vscode#161088](https://github.com/microsoft/vscode/issues/161088))

**Operational rules — apply to every git command:**

1. **Use the PowerShell tool for git. Never the Bash tool.** Empirically: PowerShell tool ran `git branch` cleanly in the same session that the Bash tool fork-bombed.
2. **Never background a git command.** No `run_in_background: true` on any git invocation, ever.
3. **One git command at a time.** Never two git invocations in one batched tool-call message; never start a new git command while another is in flight (even if the previous one "looks done" — check task status first).
4. **Avoid working-tree-wide enumerations** in repos with large gitignored subtrees (`wsl_env/`, `node_modules/`, `.venv/`, etc.). Scope `git status`, `git ls-files`, `git diff` to specific paths.
5. **Filesystem reads cover most orientation needs.** Before invoking git for "where am I / what's here," try `Read`, `Glob`, `Grep` first. Many sessions don't need git at all until commit time.
6. **Check `core.fsmonitor` once per repo.** If on, decide deliberately: keep it (good for huge repos with no IDE watcher) or stop it (`git fsmonitor--daemon stop` then `git config --unset core.fsmonitor`).

**Recovery if a cascade starts:**

- Elevated PowerShell: `Get-Process git, sh, bash, perl -ErrorAction SilentlyContinue | Stop-Process -Force`
- `taskkill /im git.exe /t /f` is unreliable for this — don't rely on it.
- If the machine is already thrashing, a hard restart is faster than waiting for recovery.

**One-time user setup to suggest (do not perform — requires admin and is out of scope):**

- Windows Defender path exclusions: `C:\Program Files\Git`, the repo's parent directory, `%LocalAppData%\Git`.
- Defender process exclusions: `git.exe`, `bash.exe`, `sh.exe`.
- Confirm no IDE git integration is actively watching the workspace during long agent sessions (VS Code: `git.enabled: false` workspace setting if needed).

If a fork-bomb occurs in a session, flag it to the user with the recovery command and surface the suggested one-time setup above.

---

## First-run setup (do this once per session)

Before processing any issues, confirm two things with the user:

1. **Which document tracks audit progress?** Use `Glob` to look for likely candidates (`AUDIT.md`, `PROGRESS.md`, `ISSUES.md`, `TODO.md`, `*.audit.md`, or similar). If exactly one obvious match exists, propose it and confirm. If multiple or none, ask the user to name the file.
2. **Which linter should run after each accepted fix?** Ask the user directly — do not auto-detect. Common answers: `eslint`, `ruff`, `flake8`, `pylint`, `tsc --noEmit`, `cargo clippy`, a project-specific npm script, etc. Remember the answer for the rest of the session.

Once both are confirmed, proceed to the workflow.

---

## Workflow (follow exactly, one issue per turn)

### Step 1 — Read the audit document
Use `Read` on the audit document. Identify the next issue **not** marked `[DONE]` (and not marked rejected/skipped if such a state exists). Work in document order unless the user specifies otherwise.

### Step 2 — Read the relevant code
Use `Read` on the file(s) referenced by the issue. If the issue references a function or symbol without a file path, use `Grep` to locate it. Read enough surrounding context to reason about the change properly.

### Step 3 — Show before/after as snippets
Present the proposed change as clearly delimited **before** and **after** code snippets. Do **not** apply anything yet. Keep snippets focused — just the lines that change plus a little context.

### Step 4 — Give a keep/kill recommendation
After the snippets, give a brief reasoned recommendation:
- **Keep** if the fix is sound.
- **Kill** if the issue is wrong, already fixed, or the proposed remedy would introduce regressions.

Include any **consistency risks** that the change could create elsewhere in the codebase — flag them proactively rather than waiting for the user to ask.

### Step 5 — STOP and WAIT for explicit approval
Do **not** write any code until the user replies with an explicit affirmative: `yes`, `keep`, `go`, or `apply`. Anything else — silence, a question, "hmm", a clarifying request, etc. — is **not** approval. Wait.

If the user says `no`, `kill`, or `skip`: record the issue as rejected in the audit doc and loop back to Step 1 on the next user prompt.

### Step 6 — Apply the change (only after approval)
Use `Edit` or `Write` to apply exactly the change shown in the before/after snippets. No surprise extras, no opportunistic refactoring of nearby code.

### Step 7 — Run the linter
Run the linter chosen during first-run setup, via PowerShell. Report results plainly. If the linter flags new problems, surface them to the user and wait for instruction. Do not silently re-edit.

### Step 8 — Consistency check
Quickly re-verify the consistency risks flagged in Step 4 are not realized: use `Grep`/`Read` on the affected areas. Report findings.

### Step 9 — Commit the fix individually
Commit this fix and only this fix. Message format:


```
Fix #<n>: <short description>
```


Never batch multiple fixes into one commit.

### Step 10 — Update the audit document
Mark the issue `[DONE]` in the audit doc (or whatever marker convention that document already uses — match it). Use `Edit` for a minimal, surgical change.

### Step 11 — Summarize and stop
Summarize the accepted/rejected tally so far in one or two lines. **Stop.** Do not start the next issue automatically. Wait for the user to prompt the next loop.

---

## Hard rules

- **ONE issue at a time.** Never queue or batch.
- **Show before/after BEFORE applying anything.** No exceptions.
- **ALWAYS wait for explicit approval.** Never assume "yes" from context, tone, or prior pattern.
- **COMMIT each fix individually.** Never combine fixes into one commit, even small ones.
- **Do NOT push to the remote** unless the user explicitly asks. `git commit` only.
- **No Bash tool, ever — especially for git.** PowerShell tool only. See "Git on Windows" above.
- **No backgrounded git commands.** No `run_in_background: true` on any git invocation.
- **One git command at a time, sequentially.** No parallel git in a single batched message.
- **No shell-based file exploration.** `Glob`/`Grep`/`Read` only.
- **No scheduling.** Turn-by-turn, always.

---

## On rejection

If the user rejects a proposed fix:

1. Record it in the audit document. Default marker: `[REJECTED]`. If the doc already uses `[SKIPPED]` (or another convention) for skipped items, match the existing convention instead.
2. Optionally note the reason if the user gave one.
3. Do **not** commit anything for rejected issues.
4. Loop back to Step 1 only on the next user prompt.

---

## Communication style

- Be terse. The user wants to move fast through a list, not read essays.
- Use snippets, not prose summaries, when showing code.
- Recommendations: one or two sentences of reasoning, max.
- If something feels wrong about an issue (e.g. it references code that no longer exists), say so before showing snippets and recommend `kill`.
