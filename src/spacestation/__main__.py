"""Entry point: ``python -m spacestation`` or the ``spacestation`` console script."""
from __future__ import annotations


def main() -> None:
    from .ui.app import run
    run()


if __name__ == "__main__":
    main()
