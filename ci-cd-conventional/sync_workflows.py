"""Install conventional workflow sources in GitHub's required directory, or check drift."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    different = []
    for source in sorted((ROOT / 'workflows').glob('*.yml')):
        target = ROOT.parent / '.github/workflows' / source.name
        if not target.exists() or target.read_bytes() != source.read_bytes():
            different.append(source.name)
            if not args.check:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    if args.check and different:
        raise SystemExit('Workflow copies differ: ' + ', '.join(different))
    print('Conventional workflow copies verified' if args.check else 'Conventional workflows installed')


if __name__ == '__main__':
    main()
