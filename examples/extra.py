"""Downstream "app" code. It is NOT part of the base image -- it is layered
on top of one of the published pixi base images to prove the inherited
conda-forge environment is usable for building custom things."""

import numpy as np


def main() -> None:
    matrix = np.arange(9).reshape(3, 3)
    print("app-on-top works:")
    print(f"  trace of 3x3 matrix = {np.trace(matrix)}")


if __name__ == "__main__":
    main()
