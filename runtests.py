#!/usr/bin/env python
"""Run djulia's test suite: `python runtests.py` (optionally pass test labels)."""
import os
import sys

import django
from django.conf import settings


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
    django.setup()
    from django.test.utils import get_runner
    runner = get_runner(settings)(verbosity=2)
    failures = runner.run_tests(sys.argv[1:] or ["tests"])
    sys.exit(bool(failures))


if __name__ == "__main__":
    main()
