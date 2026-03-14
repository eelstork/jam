#!/usr/bin/env python3
"""Run jam tests.  No flags = all tests."""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Run jam tests.")
    parser.add_argument("--unit", action="store_true", help="Unit tests only.")
    parser.add_argument("--e2e", action="store_true", help="End-to-end tests only.")
    args = parser.parse_args()

    cmd = [sys.executable, "-m", "pytest", "-v"]

    if args.unit:
        cmd += ["tests/", "--ignore=tests/test_e2e.py"]
    elif args.e2e:
        cmd += ["tests/test_e2e.py"]
    else:
        cmd += ["tests/"]

    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
