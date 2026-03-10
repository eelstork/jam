#!/usr/bin/env python3
"""Uninstall jam.

Usage:
    python uninstall.py
"""

import subprocess
import sys

subprocess.run([sys.executable, "-m", "pip", "uninstall", "jam", "-y"], check=True)
