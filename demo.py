#!/usr/bin/env python3
"""Run the complete JEP end-to-end demo in one command."""

from jep_core import run_demo


if __name__ == "__main__":
    raise SystemExit(0 if run_demo() else 1)
