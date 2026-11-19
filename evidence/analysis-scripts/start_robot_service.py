"""Starts the task's real robot service on this machine, for testing a solver through the `robot` command.

usage: start_robot_service.py DRAW PORT RECORD    DRAW 0 is the task's own sensing errors; other numbers draw different ones on the same cell
"""
import os, runpy, sys
SIM = os.environ.get("SIM", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "robot-moving-catch-realistic", "environment", "robot"))
SERVICE = os.environ.get("SERVICE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "robot-moving-catch-realistic", "environment", "robot", "robot_service.py"))
sys.path.insert(0, SIM)
import sensing

draw, port, record = int(sys.argv[1]), sys.argv[2], sys.argv[3]
if draw:
    draw0 = sensing.draw
    sensing.draw = lambda seed: draw0(f"{seed}-{draw}")
sys.argv = ["robot_service.py", "20261119", record, port]
runpy.run_path(SERVICE, run_name="__main__")
