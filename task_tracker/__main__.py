"""Allow ``python -m task_tracker``."""

from task_tracker.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
