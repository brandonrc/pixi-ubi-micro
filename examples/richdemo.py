"""Downstream app that needs an EXTRA dependency (rich) not in the base image.

Proves that adding a dependency works through a multi-stage app build: the dep is
solved on the full base, and the updated environment runs on ubi-micro."""

import numpy as np
from rich import print as rprint


def main() -> None:
    rprint("[bold green]app-on-top with an extra dependency works[/]")
    rprint({"numpy": np.__version__})


if __name__ == "__main__":
    main()
