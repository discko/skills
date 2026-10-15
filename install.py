#!/usr/bin/env python3
"""Repository shortcut. Example: python3 install.py install"""
from pathlib import Path
import runpy
import sys

scripts = Path(__file__).resolve().parent / "skills/html-plan/scripts"
sys.path.insert(0, str(scripts))
runpy.run_path(str(scripts / "setup.py"), run_name="__main__")
