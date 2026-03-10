#!/usr/bin/env python3
"""Install jam.

Usage:
    python install.py
"""

import subprocess
import sys

subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
