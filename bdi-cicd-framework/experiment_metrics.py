"""Compatibility entry point for shared experiment utilities."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.experiment_metrics import *

if __name__ == "__main__": main()
