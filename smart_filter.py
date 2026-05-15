"""
smart_filter.py — Claude-Code-style console output filter.

Wraps stdout in 'smart' verbosity mode to suppress boilerplate from
PyBullet (X11/GL banner, thread shutdown noise) and PDDLStream
(per-iteration / per-attempt logs), and reformat the surviving lines
into a clean, scroll-friendly narrative.  The full raw output still
lands in the per-run log file unchanged; this only touches what reaches
the console.

The filter is line-buffered — writes are accumulated until a newline,
then each complete line is run through a sequence of rules:

  * DROP rules — pure boilerplate, never shown.
  * DEDUPE rules — collapse repeated identical blocks (shadow blockers).
  * AGGREGATE rules — fold many lines (e.g. PDDLStream iterations)
    into one summary line emitted on a sentinel.
  * TRANSFORM rules — rewrite kept lines with colors/icons.
  * PASS-THROUGH — anything unrecognised falls through unchanged so we
    never lose information silently.

Design intent: a developer watching the run should be able to read the
console top-to-bottom like a story — what was set up, what was planned,
what was executed, what happened — with everything else available in
the file log if they want to go spelunking.
"""

from __future__ import annotations

import io
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

def _supports_color(stream) -> bool:
    """Best-effort detection: only colorize real TTYs that aren't dumb."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    try:
        if not stream.isatty():
            return False
    except Exception:
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    return True


class _Style:
    """Tiny ANSI palette.  Methods are no-ops when colour is disabled."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def _wrap(self, codes: str, text: str) -> str:
        if not self.enabled or not text:
            return text
        return f"\033[{codes}m{text}\033[0m"

    def dim(self, t):     return self._wrap("2", t)
    def bold(self, t):    return self._wrap("1", t)
    def cyan(self, t):    return self._wrap("36", t)
    def bcyan(self, t):   return self._wrap("1;36", t)
    def green(self, t):   return self._wrap("32", t)
    def bgreen(self, t):  return self._wrap("1;32", t)
    def yellow(self, t):  return self._wrap("33", t)
    def red(self, t):     return self._wrap("31", t)
    def magenta(self, t): return self._wrap("35", t)
    def grey(self, t):    return self._wrap("90", t)


# ---------------------------------------------------------------------------
# Line patterns
# ---------------------------------------------------------------------------

# Pure boilerplate — drop unconditionally.  Listed as plain (non-VERBOSE)
# alternations so trailing spaces in patterns ("Vendor = ") match the
# real world output reliably.
_DROP_PATTERNS = (
    r"pybullet build time",
    r"argv\[\d+\]",
    r"argc=\d",
    r"startThreads creating",
    r"starting thread \d",
    r"started thread \d",
    r"ExampleBrowserThreadFunc",
    r"X11 functions",
    r"Creating context\b",
    r"Created GL ",
    r"Direct GLX",
    r"Making context",
    r"GL_(?:VENDOR|RENDERER|VERSION|SHADING)",
    r"pthread_getconcurrency",
    r"Version = ",
    r"Vendor = ",
    r"Renderer = ",
    r"b3Printf",
    r"MotionThreadFunc",
    r"ven = ",
    r"numActiveThreads",
    r"stopping threads",
    r"Thread with taskId",
    r"Thread TERMINATED",
    r"destroy (?:main )?semaphore",
    r"(?:main )?semaphore destroyed",
    r"finished$",
    r"btShutDownExampleBrowser",
    r"Window closing in",
    r"Warning! All actions have no cost",
    r"=====+",
    # Audit-tagged diagnostic prints (e.g. [#60-diag], [#76-diag]).
    # Kept in the log file via the separate RunLogger file handler;
    # dropped from the terminal so smart-mode stays narrative.
    r"\s*\[#\d+-diag\]",
    # Audit #76 confirmation when a hidden target's OBJECT boxel is
    # first registered — purely informational, not part of the user-
    # facing narrative.
    r"\s*->\s+registered OBJECT boxel for ",
)
_DROP = re.compile("^(?:" + "|".join(_DROP_PATTERNS) + ")")

# Section markers from test_full_pipeline.py.
_PHASE = re.compile(r"^---\s*Phase\s+(\d+):\s*(.*?)\s*---\s*$")
_DASHED = re.compile(r"^---\s*(.+?)\s*---\s*$")

# PDDLStream noise — folded into a single summary at plan-end.
_ITER = re.compile(r"^Iteration:\s+(\d+)")
_ATTEMPT = re.compile(r"^Attempt:\s+(\d+)")
_PLAN_NONE = re.compile(r"^(?:Stream|Action) plan \([^)]*\):\s*None\s*$")
_NO_PLAN = re.compile(r"^No plan: increasing complexity from \d+ to \d+")
_STREAM_PLAN_OK = re.compile(r"^Stream plan \([^)]*\):\s*\[")
_ACTION_PLAN_OK = re.compile(r"^Action plan \([^)]*\):\s*\[(?P<body>.*)\]\s*$")
_SUMMARY = re.compile(r"^Summary:\s*\{(?P<body>.*)\}\s*$")
_PLAN_HEADER = re.compile(r"^===\s*PLAN\s*#(\d+)\s*===\s*$")
_TIMING = re.compile(
    r"^\s*\[timing\]\s+planner\.plan\(\)\s+#(\d+):\s+([\d.]+)s")

# Repetition we want to collapse.
_SHADOW_BLOCKERS_HDR = re.compile(r"^\s*Shadow blockers \(audit #\d+\):\s*$")
_SHADOW_BLOCKER_ROW = re.compile(
    r"^\s*(shadow_of_\w+)\s+blocked by:\s+(\[.*\])\s*$")

# Action narrative.
_EXECUTING = re.compile(r"^\s*Executing:\s+(\w+)\s*$")
_MOVING_TO = re.compile(
    r"^\s*Moving to (\S+)\s+\((\d+) waypoints\)\.\.\.\s*$")
_ARRIVED = re.compile(r"^\s*->\s+Arrived at (\S+)\s*$")
_PICKING = re.compile(r"^\s*Picking (\S+) from (\S+)\.\.\.\s*$")
_PICKED = re.compile(r"^\s*\*\*\*\s+(\S+)\s+PICKED UP!\s+\*\*\*\s*$")
_PLACING = re.compile(r"^\s*Placing (\S+) at (\S+)\.\.\.\s*$")
_PLACED = re.compile(r"^\s*\*\*\*\s+(\S+)\s+PLACED at (\S+)!\s+\*\*\*\s*$")
_STACKING = re.compile(r"^\s*Stacking (\S+) on (\S+)\.\.\.\s*$")
_STACKED = re.compile(r"^\s*\*\*\*\s+(\S+)\s+STACKED on (\S+)!\s+\*\*\*\s*$")
_SENSING = re.compile(r"^\s*Sensing (\S+).*$")
_TARGET_FOUND = re.compile(
    r"^\s*\*\*\*\s+TARGET FOUND in (\S+)!.*\*\*\*\s*$")
_TARGET_NOT_IN = re.compile(r"^\s*Target NOT in (\S+)")
_REPLAN = re.compile(r"^\s*->\s+REPLANNING.*$")

# Outer pipeline banner / summary.
_PIPELINE_BANNER = re.compile(r"^FULL PIPELINE: PDDLStream \+ Replanning\s*$")
_SUCCESS = re.compile(r"^SUCCESS!\s*$")
_FAILED_PFX = re.compile(r"^FAILED")

# RunLogger formatted lines: "[INFO   ] message".
_LOG_LINE = re.compile(r"^\[(?P<level>\w+)\s*\]\s+(?P<msg>.*)$")

# Boxel merge progress.
_MERGE_ITER = re.compile(
    r"^\s*Merge iteration (\d+):\s+(\d+) merges,\s+(\d+) boxels remaining")
_MERGE_DONE = re.compile(
    r"^\s*Merging complete:\s+(\d+)\s*->\s*(\d+) boxels")
_BOXELS_CALC = re.compile(r"^\s*Calculated (\d+) boxels")
_BOXELS_SAVED = re.compile(r"^Saved (\d+) boxels to (\S+)")
_BOXEL_REGISTRY_LINE = re.compile(
    r"^\s*(\d+) boxels,\s+(\d+) shadows,\s+(\d+) occluders")

# Initial scene info.
_BOXEL_INIT = re.compile(
    r"^Boxel Test Environment initialized successfully!?\s*$")
_CAMERA_POS = re.compile(r"^Camera position:\s+(\[.*?\])\s*$")
_CAMERA_TGT = re.compile(r"^Camera target:\s+(\[.*?\])\s*$")
_OCCLUDERS = re.compile(r"^Occluders:\s+(\d+)\s*\((.*?)\)\s*$")
_TARGETS = re.compile(r"^Targets:\s+(\d+)\s*\((.*?)\)\s*$")
_OBJECTS = re.compile(r"^Objects in scene:\s+(\[.*\])\s*$")
_ROBOT_ID = re.compile(r"^Robot ID:\s+(\d+)\s*$")

# Scenario lines.
_SCEN_TARGET = re.compile(r"^\s*Target:\s+(\S+)\s*$")
_SCEN_ORACLE = re.compile(
    r"^\s*ORACLE: Actually hidden in (\S+).*$")
_SCEN_MUST_SEARCH = re.compile(r"^\s*Robot must search to find it!?\s*$")
_BOXEL_PB_MAP = re.compile(
    r"^\s*Boxel->PyBullet mapping:\s+(\d+) objects\s*$")
_EXPORTED_PROBLEM = re.compile(r"^\s*Exported initial problem to (\S+)\s*$")
_UNKNOWN_SHADOWS = re.compile(r"^Unknown shadows remaining:\s+(\d+)\s*$")
_STACK_PROGRESS = re.compile(r"^Stack progress:\s+(.*)$")

# Plan listing.
_PLAN_HDR = re.compile(r"^Plan:\s+(\d+)\s+actions\s*$")
_PLAN_STEP = re.compile(r"^\s+(\d+)\.\s+(\w+)\s*$")

# Final summary block / timing block — broad: any "  Key: value" row.
# Allow parens and other punctuation in the key (e.g. "Total plan() calls",
# "Per-call (s)") so the timing summary block renders cleanly.
_RESULT_LINE = re.compile(r"^\s{2,}([A-Za-z][^:]*?)\s*:\s+(.+?)\s*$")


# ---------------------------------------------------------------------------
# Filter state
# ---------------------------------------------------------------------------

@dataclass
class _State:
    """Mutable state threaded through line processing."""

    section: str = ""
    section_emitted: bool = False
    # PDDLStream aggregator
    in_planning: bool = False
    plan_idx: int = 0
    iter_count: int = 0
    attempt_count: int = 0
    pending_plan_steps: List[str] = field(default_factory=list)
    pending_plan_count: int = 0
    pending_plan_announced: bool = False
    # Current action narrative
    current_action: Optional[str] = None
    current_action_args: Dict[str, str] = field(default_factory=dict)
    # Dedup state
    last_shadow_blockers: str = ""
    in_shadow_blockers: bool = False
    shadow_blockers_buf: List[str] = field(default_factory=list)
    # Initial-scene compact summary
    pending_init: Dict[str, str] = field(default_factory=dict)
    init_emitted: bool = False
    # Final result block detection
    in_result_block: bool = False
    result_kind: str = ""  # "success" or "failed"


# ---------------------------------------------------------------------------
# The filter stream
# ---------------------------------------------------------------------------

class SmartConsoleFilter(io.TextIOBase):
    """
    Stream wrapper applied to the console target.

    Receives ``write(text)`` calls (from ``print``, ``logging``, or any
    library that writes to stdout), buffers into complete lines, and
    forwards a Claude-Code-style transcript to the underlying stream.

    Unrecognised lines pass through unchanged so nothing is silently
    swallowed — the rules only need to handle the noisy patterns.
    """

    def __init__(self, target_stream):
        super().__init__()
        self._out = target_stream
        self._buf = ""
        self._t0 = time.perf_counter()
        self._style = _Style(_supports_color(target_stream))
        self._state = _State()

    # io.TextIOBase contract -------------------------------------------------
    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._process(line)
        return len(text)

    def flush(self) -> None:
        if self._buf:
            self._process(self._buf)
            self._buf = ""
        try:
            self._out.flush()
        except Exception:
            pass

    def isatty(self) -> bool:
        try:
            return self._out.isatty()
        except Exception:
            return False

    def fileno(self):
        return self._out.fileno()

    # internal helpers -------------------------------------------------------
    def _emit(self, line: str = "") -> None:
        self._out.write(line + "\n")
        try:
            self._out.flush()
        except Exception:
            pass

    def _passthrough(self, line: str) -> None:
        # Keep unfamiliar lines visible but de-emphasised, so we never
        # silently swallow content that the rules don't recognise.
        self._emit("  " + self._style.dim(line.strip()))

    def _section(self, name: str, *, force: bool = False) -> None:
        if name == self._state.section and not force:
            return
        self._state.section = name
        s = self._style
        self._emit("")
        self._emit(s.bcyan("◆ " + name))

    def _flush_shadow_blockers(self) -> None:
        st = self._state
        if not st.in_shadow_blockers:
            return
        block = "\n".join(r.strip() for r in st.shadow_blockers_buf)
        if block != st.last_shadow_blockers:
            s = self._style
            self._emit("  " + s.dim("shadow blockers:"))
            for row in st.shadow_blockers_buf:
                m = _SHADOW_BLOCKER_ROW.match(row)
                if m:
                    self._emit("    " + s.dim(
                        f"{m.group(1)}  ← {m.group(2)}"))
                else:
                    self._emit("    " + s.dim(row.strip()))
            st.last_shadow_blockers = block
        # else: identical block — drop entirely
        st.in_shadow_blockers = False
        st.shadow_blockers_buf = []

    def _flush_init_summary(self) -> None:
        st = self._state
        if st.init_emitted:
            return
        d = st.pending_init
        if not d:
            return
        s = self._style
        if "init" in d:
            self._emit("  " + s.green("✓") + " " + d["init"])
        if "occ_tgt" in d:
            self._emit("  " + s.dim("• " + d["occ_tgt"]))
        if "robot" in d:
            self._emit("  " + s.dim("• " + d["robot"]))
        if "camera" in d:
            self._emit("  " + s.dim("• " + d["camera"]))
        st.init_emitted = True
        st.pending_init = {}

    # core dispatch ----------------------------------------------------------
    def _process(self, raw: str) -> None:
        st = self._state
        s = self._style
        # Strip trailing CR (Windows line endings).
        line = raw.rstrip("\r")

        # End-of-block flush for shadow-blocker dedupe.  Any line that
        # isn't a shadow row terminates the block.
        if st.in_shadow_blockers and not _SHADOW_BLOCKER_ROW.match(line):
            self._flush_shadow_blockers()

        # ---- pure drops ---------------------------------------------------
        if not line.strip():
            return  # absorb blank lines; we add our own spacing
        if _DROP.match(line):
            return

        # ---- pipeline banner ---------------------------------------------
        if _PIPELINE_BANNER.match(line):
            self._emit(s.bcyan("Semantic Boxels · PDDLStream pipeline"))
            return

        # ---- log-formatted lines from RunLogger --------------------------
        m = _LOG_LINE.match(line)
        if m:
            level = m.group("level").strip()
            msg = m.group("msg")
            if msg.startswith("Verbosity"):
                return
            if msg.startswith("Run started"):
                ts = msg.split(":", 1)[1].strip()
                self._emit(s.dim(f"  started {ts}"))
                return
            if msg.startswith("Run finished"):
                ts = msg.split(":", 1)[1].strip()
                self._emit("")
                self._emit(s.dim(f"  finished {ts}"))
                return
            if msg.startswith("Log file") or msg.startswith("Full log at"):
                path = msg.split(":", 1)[1].strip()
                self._emit(s.dim(f"  log: {path}"))
                return
            if msg.startswith("plan_motion:"):
                # Drop the chatty per-move planner line; the action
                # narrative already shows the move.
                return
            level_to_color = {
                "INFO":    s.dim,
                "DEBUG":   s.dim,
                "WARNING": s.yellow,
                "ERROR":   s.red,
            }
            colour = level_to_color.get(level, s.dim)
            self._emit("  " + colour(msg))
            return

        # ---- section markers ---------------------------------------------
        m = _PHASE.match(line)
        if m:
            self._section(f"Phase {m.group(1)} · {m.group(2)}")
            return
        m = _DASHED.match(line)
        if m:
            label = m.group(1).strip()
            if label.lower() == "run configuration":
                self._section("Configuration")
                return
            if label.lower() == "planning timing summary":
                self._section("Planning timing")
                return

        # ---- run config rows: '  scene              = default' ------------
        cfg_match = re.match(r"^\s{2,}(\w[\w_]*)\s+=\s+(.+)$", line)
        if cfg_match and st.section == "Configuration":
            key, val = cfg_match.group(1), cfg_match.group(2)
            self._emit("  " + s.dim(f"{key:14s}") + "  " + val)
            return

        # ---- env init compact summary ------------------------------------
        if _BOXEL_INIT.match(line):
            st.pending_init["init"] = "boxel test environment initialised"
            return
        m = _CAMERA_POS.match(line)
        if m:
            st.pending_init["_cam_pos"] = m.group(1)
            return
        m = _CAMERA_TGT.match(line)
        if m:
            cam_pos = st.pending_init.pop("_cam_pos", None)
            if cam_pos:
                st.pending_init["camera"] = (
                    f"camera {cam_pos} → {m.group(1)}")
            return
        m = _OCCLUDERS.match(line)
        if m:
            st.pending_init["_occ"] = (
                f"{m.group(1)} occluders ({m.group(2)})")
            return
        m = _TARGETS.match(line)
        if m:
            tg = f"{m.group(1)} targets ({m.group(2)})"
            occ = st.pending_init.pop("_occ", None)
            st.pending_init["occ_tgt"] = (
                f"{occ} · {tg}" if occ else tg)
            return
        m = _OBJECTS.match(line)
        if m:
            try:
                n = len(eval(m.group(1), {"__builtins__": {}}, {}))
                st.pending_init["_objs_n"] = str(n)
            except Exception:
                pass
            return
        m = _ROBOT_ID.match(line)
        if m:
            n = st.pending_init.pop("_objs_n", None)
            extra = f" · {n} bodies in scene" if n else ""
            st.pending_init["robot"] = f"robot id {m.group(1)}{extra}"
            self._flush_init_summary()
            return

        # ---- boxel merge progress (fold) ---------------------------------
        m = _MERGE_ITER.match(line)
        if m:
            return  # suppress per-iteration; emit one line on completion
        m = _MERGE_DONE.match(line)
        if m:
            self._emit("  " + s.green("✓")
                       + f" merged {m.group(1)} → {m.group(2)} boxels")
            return
        m = _BOXELS_CALC.match(line)
        if m:
            self._emit("  " + s.green("✓")
                       + f" computed {m.group(1)} boxels")
            return
        m = _BOXELS_SAVED.match(line)
        if m:
            self._emit("  " + s.dim(
                f"→ saved {m.group(1)} boxels to {m.group(2)}"))
            return
        m = _BOXEL_REGISTRY_LINE.match(line)
        if m:
            self._emit("  " + s.dim(
                f"• {m.group(1)} boxels · {m.group(2)} shadows · "
                f"{m.group(3)} occluders"))
            return

        # ---- result-block lines win over scenario regexes ----------------
        # Once we've entered the success/failure block, "  Target: foo"
        # etc. should render as result rows, not as scenario headers.
        if st.in_result_block:
            m = _RESULT_LINE.match(line)
            if m:
                key = m.group(1).lower().strip()
                val = m.group(2)
                self._emit("  " + s.dim(f"{key:18s}") + " " + val)
                return

        # ---- timing-block lines win over generic patterns ----------------
        if st.section == "Planning timing":
            m = _RESULT_LINE.match(line)
            if m:
                key = m.group(1).lower().strip()
                val = m.group(2)
                self._emit("  " + s.dim(f"{key:24s}") + " " + val)
                return

        # ---- scenario ----------------------------------------------------
        m = _SCEN_TARGET.match(line)
        if m:
            self._emit("  " + s.dim("target  ") + s.bold(m.group(1)))
            return
        m = _SCEN_ORACLE.match(line)
        if m:
            self._emit("  " + s.dim("oracle  hidden in ")
                       + s.bold(m.group(1)))
            return
        if _SCEN_MUST_SEARCH.match(line):
            self._emit("  " + s.dim(
                "        robot must search to find it"))
            return
        m = _BOXEL_PB_MAP.match(line)
        if m:
            self._emit("  " + s.dim(
                f"• boxel→pybullet mapping: {m.group(1)} objects"))
            return
        m = _EXPORTED_PROBLEM.match(line)
        if m:
            self._emit("  " + s.dim(
                f"→ exported pddl problem: {m.group(1)}"))
            return

        # ---- shadow-blocker dedupe ---------------------------------------
        if _SHADOW_BLOCKERS_HDR.match(line):
            st.in_shadow_blockers = True
            st.shadow_blockers_buf = []
            return
        if st.in_shadow_blockers:
            if _SHADOW_BLOCKER_ROW.match(line):
                st.shadow_blockers_buf.append(line)
                return
            self._flush_shadow_blockers()

        # ---- planning iteration aggregator -------------------------------
        m = _PLAN_HEADER.match(line)
        if m:
            st.plan_idx = int(m.group(1))
            st.in_planning = True
            st.iter_count = 0
            st.attempt_count = 0
            st.pending_plan_steps = []
            st.pending_plan_count = 0
            st.pending_plan_announced = False
            self._emit("")
            self._emit(s.bcyan("◆ Planning") + s.dim(f"  #{st.plan_idx}"))
            return
        m = _UNKNOWN_SHADOWS.match(line)
        if m:
            self._emit("  " + s.dim(
                f"unknown shadows remaining: {m.group(1)}"))
            return
        m = _STACK_PROGRESS.match(line)
        if m:
            self._emit("  " + s.dim(f"stack progress: {m.group(1)}"))
            return
        if _ITER.match(line):
            st.iter_count += 1
            return
        if _ATTEMPT.match(line):
            st.attempt_count += 1
            return
        if _PLAN_NONE.match(line) or _NO_PLAN.match(line):
            return
        if _STREAM_PLAN_OK.match(line):
            return  # the action plan line carries the same info
        m = _ACTION_PLAN_OK.match(line)
        if m:
            body = m.group("body").strip()
            steps: List[str] = []
            depth = 0
            cur: List[str] = []
            for ch in body:
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
                if ch == "," and depth == 0:
                    steps.append("".join(cur).strip())
                    cur = []
                else:
                    cur.append(ch)
            if cur:
                steps.append("".join(cur).strip())
            st.pending_plan_steps = steps
            st.pending_plan_count = len(steps)
            return
        m = _SUMMARY.match(line)
        if m:
            body = m.group("body")

            def _grab(key):
                mm = re.search(rf"{key}:\s*([^,}}]+)", body)
                return mm.group(1).strip() if mm else None

            solved = _grab("solved")
            length = _grab("length")
            run_t  = _grab("run_time")
            iters  = _grab("iterations")
            cost   = _grab("cost")
            st.in_planning = False
            if solved == "True":
                self._emit("  " + s.green("✓") + " plan found "
                           + s.dim(
                               f"({length} actions · {iters} iterations · "
                               f"{run_t}s · cost {cost})"))
            else:
                self._emit("  " + s.red("✗") + " no plan "
                           + s.dim(f"({iters} iterations · {run_t}s)"))
            return
        m = _TIMING.match(line)
        if m:
            self._emit("  " + s.dim(
                f"planner.plan() #{m.group(1)}: {m.group(2)}s"))
            return

        # ---- plan listing ------------------------------------------------
        m = _PLAN_HDR.match(line)
        if m:
            self._emit("  " + s.dim(f"plan: {m.group(1)} actions"))
            if st.pending_plan_steps:
                # Render compact action sequence on one line, indented.
                parts = [self._compact_step(t) for t in st.pending_plan_steps]
                # Word-wrap if very long
                rendered = " → ".join(parts)
                self._emit("    " + s.dim(rendered))
                st.pending_plan_announced = True
            return
        m = _PLAN_STEP.match(line)
        if m:
            if st.pending_plan_announced:
                return
            self._emit("    " + s.dim(f"{m.group(1)}. {m.group(2)}"))
            return

        # ---- action narrative --------------------------------------------
        m = _EXECUTING.match(line)
        if m:
            st.current_action = m.group(1)
            st.current_action_args = {}
            return
        m = _MOVING_TO.match(line)
        if m:
            st.current_action_args["dest"] = m.group(1)
            st.current_action_args["wp"] = m.group(2)
            return
        m = _ARRIVED.match(line)
        if m:
            dest = st.current_action_args.get("dest", m.group(1))
            wp = st.current_action_args.get("wp")
            extra = s.dim(f"  ({wp} waypoints)") if wp else ""
            self._emit("  " + s.green("✓") + " "
                       + self._action_label("move") + " → " + dest + extra)
            st.current_action = None
            st.current_action_args = {}
            return
        m = _PICKING.match(line)
        if m:
            st.current_action_args["obj"] = m.group(1)
            st.current_action_args["from"] = m.group(2)
            return
        m = _PICKED.match(line)
        if m:
            obj = m.group(1)
            src = st.current_action_args.get("from")
            extra = s.dim(f"  from {src}") if src and src != obj else ""
            self._emit("  " + s.green("✓") + " "
                       + self._action_label("pick") + " " + obj + extra)
            st.current_action = None
            st.current_action_args = {}
            return
        m = _PLACING.match(line)
        if m:
            st.current_action_args["obj"] = m.group(1)
            st.current_action_args["dest"] = m.group(2)
            return
        m = _PLACED.match(line)
        if m:
            self._emit("  " + s.green("✓") + " "
                       + self._action_label("place") + " " + m.group(1)
                       + s.dim(f"  @ {m.group(2)}"))
            st.current_action = None
            st.current_action_args = {}
            return
        m = _STACKING.match(line)
        if m:
            st.current_action_args["obj"] = m.group(1)
            st.current_action_args["on"] = m.group(2)
            return
        m = _STACKED.match(line)
        if m:
            self._emit("  " + s.green("✓") + " "
                       + self._action_label("stack") + " " + m.group(1)
                       + s.dim(f"  on {m.group(2)}"))
            st.current_action = None
            st.current_action_args = {}
            return
        m = _SENSING.match(line)
        if m:
            st.current_action_args["sensing"] = m.group(1)
            return
        m = _TARGET_FOUND.match(line)
        if m:
            self._emit("  " + s.green("✓") + " "
                       + self._action_label("sense") + " " + m.group(1)
                       + "  " + s.bgreen("TARGET FOUND"))
            st.current_action = None
            st.current_action_args = {}
            return
        m = _TARGET_NOT_IN.match(line)
        if m:
            self._emit("  " + s.yellow("○") + " "
                       + self._action_label("sense") + " " + m.group(1)
                       + s.dim("  target not here"))
            st.current_action = None
            st.current_action_args = {}
            return
        if _REPLAN.match(line):
            self._emit("  " + s.yellow("↺") + s.dim(" replanning…"))
            return

        # ---- final outcome -----------------------------------------------
        if _SUCCESS.match(line):
            self._section("Result")
            self._emit("  " + s.bgreen("✓ SUCCESS"))
            st.in_result_block = True
            st.result_kind = "success"
            return
        if _FAILED_PFX.match(line):
            self._section("Result")
            self._emit("  " + s.red("✗ ") + line.strip())
            st.in_result_block = True
            st.result_kind = "failed"
            return

        # ---- fall-through (don't lose data) ------------------------------
        # Generic key:value rows that don't belong to a known section.
        m = _RESULT_LINE.match(line)
        if m:
            key = m.group(1).lower().strip()
            val = m.group(2)
            self._emit("  " + s.dim(f"{key}: ") + val)
            return
        self._passthrough(line)

    # ----- helpers -----------------------------------------------------
    @staticmethod
    def _compact_step(step: str) -> str:
        """Compact a planner step like 'sample-grasp:(...)->(...)' to its head."""
        head = step.split(":", 1)[0].strip()
        head = head.split("(", 1)[0].strip()
        return head or step

    def _action_label(self, name: str) -> str:
        """5-char left-padded bold label for action lines."""
        return self._style.bold(f"{name:<5}")
