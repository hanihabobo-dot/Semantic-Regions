"""
Pipeline run logging service.

Provides a RunLogger that:
  - Tees all stdout to a timestamped log file (captures PDDLStream print output)
  - Configures Python logging with file + console handlers
  - Copies input artefacts (boxel_data.json, problem PDDL) into the log directory
  - Supports four verbosity levels via a single parameter

Verbosity levels:
  - 'smart'   (default): Claude-Code-style filtered console output —
                drops PyBullet/PDDLStream boilerplate, dedupes repeated
                blocks, and reformats the surviving lines into a clean
                narrative.  Full raw stream still goes to the log file.
  - 'normal':   Console at INFO level, raw stdout untouched.
  - 'quiet':    Console at WARNING level, raw stdout untouched.
  - 'verbose':  Console at DEBUG level, raw stdout untouched.

Usage::

    logger = RunLogger(verbosity='smart')   # default; or 'normal', 'quiet', 'verbose'
    ...
    logger.save_artefact('boxel_data.json')
    logger.save_artefact('pddl/problem_debug.pddl')
    ...
    logger.close()

Or as a context manager::

    with RunLogger(verbosity='smart') as logger:
        ...
"""

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from smart_filter import SmartConsoleFilter

QUIET = logging.WARNING
NORMAL = logging.INFO
VERBOSE = logging.DEBUG

# 'smart' is a console-presentation mode, not a filter level — the
# console handler still runs at INFO so all narrative ``logging.info``
# calls reach the SmartConsoleFilter, which decides what to render.
_LEVEL_MAP = {
    'quiet':   QUIET,
    'normal':  NORMAL,
    'smart':   NORMAL,
    'verbose': VERBOSE,
}

VALID_VERBOSITIES = ('smart', 'normal', 'quiet', 'verbose')


class _TeeStream:
    """Duplicates writes to both the original stream and a log file."""

    def __init__(self, original, log_file):
        self.original = original
        self.log_file = log_file

    def write(self, text):
        self.original.write(text)
        self.log_file.write(text)
        self.log_file.flush()

    def flush(self):
        self.original.flush()
        self.log_file.flush()

    def fileno(self):
        return self.original.fileno()

    def isatty(self):
        return self.original.isatty()


class RunLogger:
    """
    Pipeline logging service with verbosity control and persistent output.

    Args:
        verbosity: One of ``'smart'`` (default), ``'normal'``, ``'quiet'``,
            ``'verbose'``.  Controls what appears on the console.  The log
            FILE always captures everything (DEBUG and above).
        log_dir: Directory for log files (created if absent).

    Attributes:
        log_path: Path to the current run's log file.
        run_dir:  Per-run subdirectory inside *log_dir* (holds artefacts).
    """

    def __init__(self, verbosity: str = 'smart', log_dir: str = 'logs'):
        if verbosity not in VALID_VERBOSITIES:
            raise ValueError(
                f"verbosity must be one of {VALID_VERBOSITIES}, "
                f"got {verbosity!r}")
        self._verbosity = verbosity
        self._timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

        self.run_dir = Path(log_dir) / f'run_{self._timestamp}'
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.log_path = self.run_dir / f'run_{self._timestamp}.log'

        self._log_file = open(self.log_path, 'w', encoding='utf-8')
        self._original_stdout = sys.stdout

        # In smart mode the console target is wrapped by a filter that
        # rewrites the noisy parts.  Other modes keep the raw stdout so
        # PyBullet/PDDLStream output appears verbatim.  The tee always
        # forks a copy to the log file, untouched, for full fidelity.
        if verbosity == 'smart':
            self._console_target = SmartConsoleFilter(self._original_stdout)
        else:
            self._console_target = self._original_stdout
        sys.stdout = _TeeStream(self._console_target, self._log_file)

        console_level = _LEVEL_MAP.get(verbosity, NORMAL)

        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        for h in root.handlers[:]:
            root.removeHandler(h)

        fh = logging.StreamHandler(self._log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)-7s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'))
        root.addHandler(fh)
        self._file_handler = fh

        ch = logging.StreamHandler(self._console_target)
        ch.setLevel(console_level)
        ch.setFormatter(logging.Formatter('[%(levelname)-7s] %(message)s'))
        root.addHandler(ch)
        self._console_handler = ch

        logging.info('Run started  : %s', self._timestamp)
        logging.info('Log file     : %s', self.log_path)
        logging.info('Verbosity    : %s (console), DEBUG (file)', verbosity)

    # ----- artefact saving ---------------------------------------------------

    def save_artefact(self, src_path: str, dest_name: str = None):
        """
        Copy *src_path* into the run directory for reproducibility.

        Args:
            src_path:  Path to the file to copy.
            dest_name: Optional filename override inside the run directory.
        """
        src = Path(src_path)
        if not src.exists():
            logging.warning('Artefact not found, skipping: %s', src)
            return
        dest = self.run_dir / (dest_name or src.name)
        shutil.copy2(src, dest)
        logging.debug('Saved artefact: %s -> %s', src, dest)

    # ----- lifecycle ---------------------------------------------------------

    def close(self):
        """Restore stdout, flush the log file, and remove handlers."""
        logging.info('Run finished : %s',
                     datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
        logging.info('Full log at  : %s', self.log_path)

        root = logging.getLogger()
        root.removeHandler(self._file_handler)
        root.removeHandler(self._console_handler)

        # Flush the smart filter so any buffered partial line lands on
        # screen before we restore the original stdout.
        if isinstance(self._console_target, SmartConsoleFilter):
            try:
                self._console_target.flush()
            except Exception:
                pass

        sys.stdout = self._original_stdout
        self._log_file.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


# ---------------------------------------------------------------------------
# Run outcome reporting (extracted from test_full_pipeline.py 2026-05-05)
# ---------------------------------------------------------------------------


def report_run_outcome(
    *,
    success: bool,
    exit_reason: Optional[str],
    goal_kind: str,
    goal,
    target_name: Optional[str],
    on_relations: dict,
    belief,
    plan_count: int,
    shadows: list,
    blocked_giveup_shadows: set,
    max_replans: int,
    plan_times: list,
    total_plan_time: float,
    physical_failures: list,
    physics_failures: list,
    run_config: Optional[dict],
    run_logger: Optional["RunLogger"],
):
    """Print success/failure classification, planning timing summary,
    and write timing_summary.json into the run logger's run directory.

    Caller is responsible for computing ``success`` and
    ``physics_failures`` (those depend on goal_kind + domain helpers
    in the orchestrator).  This function only formats and persists
    the result.
    """
    print("\n" + "=" * 60)
    if success:
        print(f"SUCCESS!")
        if goal_kind == 'holding':
            print(f"  Target: {target_name}")
            print(f"  Found in: {belief.target_found_in}")
            print(f"  Plans executed: {plan_count}")
            print(f"  Shadows searched: {len(shadows) - len(belief.get_unknown_shadows())}")
        else:
            print(f"  Stack goal: {goal}")
            print(f"  Final on-relations: {on_relations}")
            print(f"  Plans executed: {plan_count}")
    else:
        remaining = belief.get_unknown_shadows()
        if exit_reason is None:
            exit_reason = "replan_limit"
        if exit_reason == "all_searched":
            if blocked_giveup_shadows:
                # Audit #21: distinguish observed-empty shadows from
                # blocked-unresolved ones so the run report does not
                # claim a complete search when some shadows were never
                # actually observed.
                observed_empty = len(shadows) - len(blocked_giveup_shadows)
                print(f"FAILED: {observed_empty} shadow(s) observed "
                      f"empty, {len(blocked_giveup_shadows)} "
                      f"blocked-unresolved (target may still be there): "
                      f"{sorted(blocked_giveup_shadows)} — see audit #21 "
                      f"(real fix #47 deferred 2026-05-06)")
            else:
                print(f"FAILED: All {len(shadows)} shadows searched — target not found")
        elif exit_reason == "planner_failed":
            print(f"FAILED: Planner returned no plan "
                  f"({len(remaining)} unsearched shadows remaining)")
        elif exit_reason == "drop_failed":
            print(f"FAILED: Could not release held object after retries — "
                  f"aborted to avoid double-grasp "
                  f"({len(remaining)} unsearched shadows remaining)")
        elif exit_reason == "physics_mismatch":
            # Audit S-18: belief says target was found, but the
            # end-of-run physics check disagreed (gripper empty,
            # wrong body welded, or cube not lifted off the table).
            # Details are in physics_failures / the
            # PHYSICAL_FAILURE (goal) line printed earlier.
            print(f"FAILED: Belief said target was found but physics "
                  f"check disagreed (see PHYSICAL_FAILURE above) — "
                  f"audit S-18")
        elif goal_kind == 'stack':
            print(f"FAILED: Stack goal not reached after {plan_count} plans "
                  f"(goal {goal}, achieved {on_relations})")
        else:
            print(f"FAILED: Replan limit reached ({max_replans}) with "
                  f"{len(remaining)} unsearched shadows remaining")
        print(f"  Plans executed: {plan_count}")

    print(f"\n--- Planning timing summary ---")
    print(f"  Total plan() calls       : {len(plan_times)}")
    print(f"  Cumulative planning time : {total_plan_time:.3f}s")
    if plan_times:
        avg = total_plan_time / len(plan_times)
        print(f"  Average per call         : {avg:.3f}s")
        per_call_str = ', '.join(f'{t:.3f}' for t in plan_times)
        print(f"  Per-call (s)             : [{per_call_str}]")

    # Machine-readable summary alongside the full text log so multi-run
    # comparisons (baseline vs. stack feature, GUI vs. no-GUI, etc.)
    # don't require parsing the prose log.
    if run_logger is not None:
        summary_path = run_logger.run_dir / "timing_summary.json"
        try:
            summary_path.write_text(json.dumps({
                "run_config": run_config or {},
                "success": bool(success),
                "exit_reason": exit_reason,
                "plan_count": plan_count,
                "total_planning_time_s": round(total_plan_time, 3),
                "per_call_planning_time_s": [round(t, 3) for t in plan_times],
                # Audit #40: structured physics-vs-symbolic failure log
                # so eval tooling (#9) can filter false-positive successes.
                "physical_failures_per_action": physical_failures,
                "physical_failures_at_goal": physics_failures,
            }, indent=2))
            print(f"  Timing summary written to {summary_path}")
        except Exception as e:
            print(f"  WARNING: could not write timing_summary.json: {e}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Pipeline CLI argument parsing (extracted from test_full_pipeline.py
# 2026-05-05).  Lives here rather than in test_full_pipeline.py so the
# entry-point block stays short; the scene-builder dispatch and main()
# call remain in the orchestrator.
# ---------------------------------------------------------------------------


def parse_pipeline_args(argv=None):
    """Parse the pipeline CLI args and return the validated Namespace.

    Performs post-parse validation (scene auto-promotion under
    --n-hidden / --goal stack, --n-hidden vs --n-occluders/--n-targets
    sanity checks).  ``parser.error`` exits the process on bad input.
    """
    parser = argparse.ArgumentParser(description='Full PDDLStream Pipeline with Replanning')
    parser.add_argument('--no-gui', action='store_true', help='Run without GUI')
    parser.add_argument(
        '--no-boxel-viz',
        action='store_true',
        help='Keep PyBullet GUI but skip drawing boxel AABBs/labels (debug clutter)',
    )
    parser.add_argument(
        '--show-free',
        action='store_true',
        help='Include free-space boxels in the visualisation overlay',
    )
    parser.add_argument('--log-level',
                        choices=['smart', 'normal', 'quiet', 'verbose'],
                        default='smart',
                        help='Console verbosity. "smart" (default) renders a '
                             'Claude-Code-style narrative and drops PyBullet / '
                             'PDDLStream boilerplate. "normal", "quiet", and '
                             '"verbose" leave stdout untouched. The log file '
                             'always captures everything.')
    parser.add_argument('--scene', choices=['default', 'mixed',
                                            'scalability', 'stack'],
                        default='default',
                        help='Scene preset: default (original cubes), mixed (diverse '
                             'shapes), scalability (random for evaluation), '
                             'stack (N identical cubes, no occluders).')
    parser.add_argument('--n-occluders', type=int, default=3,
                        help='Number of occluders (scalability scene only)')
    parser.add_argument('--n-targets', type=int, default=4,
                        help='Number of targets (scalability scene only)')
    parser.add_argument('--n-hidden', type=int, default=0,
                        help='Number of targets that must be hidden from '
                             'the camera at spawn time (scalability + '
                             'holding only, audit #29). 0 = no guarantee '
                             '(emergent from RNG). Capped at --n-targets. '
                             'Requires --n-occluders >= 1.')
    parser.add_argument('--n-objects', type=int, default=3,
                        help='Number of cubes for the stack scene '
                             '(must be >= --stack-height)')
    parser.add_argument('--seed', type=int, default=0,
                        help='Random seed (scalability/mixed/stack scenes). '
                             'Note: --n-hidden > 0 may nudge the seed on '
                             'retry if placement fails; the effective seed '
                             'is logged in run_config.')
    parser.add_argument(
        '--goal',
        choices=['holding', 'stack'],
        default='holding',
        help="Goal kind. 'holding' picks the (hidden or visible) target; "
             "'stack' builds a randomised tower of cubes (audit #30).",
    )
    parser.add_argument(
        '--stack-height',
        type=int,
        default=2,
        help='Stack tower height in cubes (>= 2). Only used with '
             '--goal stack. Defaults to 2 (one stacking action).',
    )
    parser.add_argument(
        '--unit-costs',
        action='store_true',
        help='Pass unit_costs=True to PDDLStream solve(): override the '
             'domain numeric (increase (total-cost) ...) effects so every '
             'action is cost 1. Default off keeps the domain costs '
             '(stack=2, others=1; see THESIS_NOTES section 17). Useful '
             'for evaluation sweeps that compare planner behaviour with '
             'and without the stack-cost bias.',
    )
    args = parser.parse_args(argv)

    # Audit #29: --n-hidden only makes sense on the scalability scene
    # with --goal holding.  Auto-promote --scene default to scalability
    # when the user passes any of the count knobs under --goal holding
    # (mirrors the --goal stack auto-override below).  Reject clearly
    # wrong combinations early so the user sees a CLI error instead of
    # silently running a scene that cannot satisfy the request.
    _holding_counts_explicit = (
        args.n_hidden > 0
        or '--n-occluders' in sys.argv
        or '--n-targets' in sys.argv
    )
    if (args.goal == 'holding'
            and args.scene == 'default'
            and _holding_counts_explicit):
        args.scene = 'scalability'

    if args.n_hidden > 0:
        if args.scene not in ('scalability',):
            parser.error(
                f"--n-hidden > 0 requires --scene scalability "
                f"(got --scene {args.scene}). Hidden-target guarantee "
                f"only applies to the scalability scene."
            )
        if args.goal != 'holding':
            parser.error(
                f"--n-hidden > 0 is only meaningful with --goal holding "
                f"(got --goal {args.goal}). Stack scenes have no "
                f"occluders."
            )
        if args.n_occluders < 1:
            parser.error(
                "--n-hidden > 0 requires --n-occluders >= 1."
            )
        if args.n_hidden > args.n_targets:
            print(f"[warn] --n-hidden={args.n_hidden} > "
                  f"--n-targets={args.n_targets}; capping to "
                  f"{args.n_targets}.", file=sys.stderr)
            args.n_hidden = args.n_targets

    # When --goal stack is requested without an explicit --scene, fall
    # back to stack_scene so the spawned objects are reach-constrained
    # cubes by default.  Explicit --scene overrides this for A/B tests.
    if args.goal == 'stack' and args.scene == 'default':
        args.scene = 'stack'

    return args
