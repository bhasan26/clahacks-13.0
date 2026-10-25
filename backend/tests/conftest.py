import sys
import os
from pathlib import Path

# Tests must neither consume local credentials nor modify the user's checkpoint.
os.environ["COVERAGEGUARD_STATE_PATH"] = ""
os.environ["COVERAGEGUARD_DISABLE_AI"] = "true"
os.environ["COVERAGEGUARD_WORKER_LOCK"] = f"/tmp/coverageguard-pytest-{os.getpid()}.lock"

# Add backend directory to sys.path so 'app' can be imported cleanly from anywhere
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
