#!/usr/bin/env python3
"""Run integrated LeKiwi teleoperation with both cameras and no recording."""

import runpy
import sys
from pathlib import Path


TARGET = Path(__file__).with_name("lekiwi_leader_gamepad_teleop.py")
sys.argv[1:1] = ["--practice-ui"]
runpy.run_path(str(TARGET), run_name="__main__")
