#!/usr/bin/env python3
"""Install jam.

Usage:
    python install.py
"""

import shutil
import site
import subprocess
import sys
import os

subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)

if shutil.which("jam"):
    print("jam is ready to use.")
else:
    # Figure out where pip put the script
    candidates = [
        os.path.join(site.getusersitepackages().replace("site-packages", "Scripts")),
        os.path.join(site.getusersitepackages().replace("site-packages", "bin")),
        os.path.join(sys.prefix, "Scripts"),
        os.path.join(sys.prefix, "bin"),
    ]
    scripts_dir = None
    for d in candidates:
        if os.path.isdir(d) and any(f.startswith("jam") for f in os.listdir(d)):
            scripts_dir = d
            break

    print()
    if scripts_dir:
        print(f"jam was installed to: {scripts_dir}")
        print(f"Add this directory to your PATH to use the jam command.")
    else:
        print("jam was installed but isn't on your PATH.")
        print("Check your Python Scripts directory and add it to PATH.")
