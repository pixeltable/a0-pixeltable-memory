"""Lifecycle hooks for the Pixeltable memory plugin.

install() is invoked by Agent Zero after Git/ZIP install and after updates.
It installs plugin dependencies into the framework Python environment.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent
REQUIREMENTS = PLUGIN_ROOT / "requirements.txt"


def install():
    if not REQUIREMENTS.is_file():
        raise FileNotFoundError(f"Missing {REQUIREMENTS}")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)]
    )


def pre_update():
    return None


def uninstall():
    # Leave Pixeltable and PIXELTABLE_HOME data in place. They may be shared
    # with other work, and Agent Zero deletes this plugin directory after
    # uninstall() returns.
    return None
