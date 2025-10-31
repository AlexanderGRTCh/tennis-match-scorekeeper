from .cli import main

"""Module entry to run the CLI with python -m.

This delegates to the main function in the CLI module.
"""

if __name__ == "__main__":
    raise SystemExit(main())
