"""Allow ``python -m taskvane``."""
from taskvane.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
