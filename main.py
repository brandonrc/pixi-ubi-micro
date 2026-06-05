"""Tiny workload that proves the conda-forge environment actually runs.

It does a little real numerical work with numpy/pandas/scipy and prints the
runtime details. If this prints on ubi-micro -- which ships no package
manager and no shell -- then the copied-in environment is genuinely
self-contained.
"""

import platform
import sys

import numpy as np
import pandas as pd
from scipy import stats


def main() -> None:
    rng = np.random.default_rng(42)
    samples = rng.normal(loc=10.0, scale=2.0, size=10_000)

    frame = pd.DataFrame({"value": samples})
    described = frame["value"].describe()
    _, p_value = stats.normaltest(samples)

    print("pixi-ubi-micro demo")
    print(f"  python  : {sys.version.split()[0]} ({platform.machine()})")
    print(f"  numpy   : {np.__version__}")
    print(f"  pandas  : {pd.__version__}")
    print(f"  mean    : {described['mean']:.4f}")
    print(f"  std     : {described['std']:.4f}")
    print(f"  normaltest p-value: {p_value:.4f}")


if __name__ == "__main__":
    main()
