#!/usr/bin/env bash
# Helper to run pipeline commands inside the WSL venv from PowerShell.
# Usage: wsl bash /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/scripts/_run_in_wsl.sh <args>
# Where <args> are passed verbatim to python.  Two special forms:
#   _run_in_wsl.sh check           -> verify pybullet imports + print versions
#   _run_in_wsl.sh <module> <args> -> python -m <module> <args>
set -e
cd /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels
source wsl_env/bin/activate

if [ "$1" = "check" ]; then
    python - <<'PYEOF'
import sys
print("python:", sys.executable)
print("python version:", sys.version.split()[0])
try:
    import pybullet as p
    print("pybullet:", p.__file__)
except ImportError as e:
    print("pybullet IMPORT FAILED:", e)
    sys.exit(1)
try:
    import pddlstream
    print("pddlstream:", pddlstream.__file__)
except ImportError as e:
    print("pddlstream IMPORT FAILED:", e)
PYEOF
else
    exec python "$@"
fi
