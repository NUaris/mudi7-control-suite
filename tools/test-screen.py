"""Offline screen test runner; supports a local font without publishing it."""
import argparse
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'screen-custom'),str(ROOT/'screen-upstream')]
import mudi_ui as ui
p=argparse.ArgumentParser();p.add_argument('--font');args=p.parse_args()
if args.font:ui.FONT_PATH=Path(args.font).resolve();ui.FONTS.clear()
if not ui.FONT_PATH.exists():p.error('Provide --font for offline rendering tests')
tests=unittest.defaultTestLoader.discover(str(ROOT/'screen-custom'),pattern='test_screen.py')
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful())
