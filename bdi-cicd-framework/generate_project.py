"""Validate engineer inputs and explicitly regenerate persistent project artifacts."""
import argparse
from pathlib import Path
import sys
from project_artifacts import ROOT, ModelError, generate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', type=Path, default=ROOT)
    parser.add_argument('--pipeline', type=Path, default=ROOT / 'models/01_pipeline.yaml')
    parser.add_argument('--goal', type=Path, default=ROOT / 'models/02_goal.yaml')
    args = parser.parse_args()
    for path in generate(args.project_dir, args.pipeline, args.goal):
        print(path)


if __name__ == '__main__':
    try:
        main()
    except (ModelError, OSError, ValueError) as error:
        print(f'Project generation failed: {error}', file=sys.stderr)
        raise SystemExit(2)
