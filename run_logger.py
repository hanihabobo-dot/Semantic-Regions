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

import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

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
