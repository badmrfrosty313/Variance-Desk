"""PyInstaller entry point that preserves the variancedesk package context."""
from variancedesk.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
