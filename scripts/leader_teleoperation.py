#!/usr/bin/env python3
"""Start full six-axis leader/follower teleoperation."""

import runpy
import sys
from pathlib import Path


TARGET = Path(__file__).with_name("leader_body_3joint_test.py")
sys.argv[1:1] = ["--mode", "teleop"]
runpy.run_path(str(TARGET), run_name="__main__")
