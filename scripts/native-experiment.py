"""Deprecated: use ci-cd-conventional/native-experiment.py."""
import runpy
from pathlib import Path
globals().update(runpy.run_path(str(Path(__file__).resolve().parents[1]/"ci-cd-conventional/native-experiment.py"), run_name=__name__))
