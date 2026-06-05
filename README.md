# pixi-ubi-micro

Companion repo for the OpenTeams Engineering blog post **"pixi on UBI-micro: A
Smaller, Safer Multi-Stage Container Build."**

It builds the **same** [pixi](https://pixi.sh) (v0.70.1) environment (Python 3.12
+ numpy/pandas/scipy) on three different Red Hat UBI9 bases and scans each with
[Trivy](https://github.com/aquasecurity/trivy) and
[Grype](https://github.com/anchore/grype). The environment is held constant on
purpose, so the only variable is the base image — and the entire difference in
image size and CVE count is attributable to the base OS.

All three images **ship the pixi binary and run via `pixi run`** — they are real
pixi containers, not just a baked environment. The "package manager" column below
refers to the *OS* package manager (dnf/microdnf), which is what drives the
base-OS attack surface:

| File | Base | OS package manager | Shell | Ships pixi |
|------|------|--------------------|-------|------------|
| [`Dockerfile.full`](Dockerfile.full) | `ubi9/ubi` | dnf | yes | yes |
| [`Dockerfile.minimal`](Dockerfile.minimal) | `ubi9/ubi-minimal` | microdnf | yes | yes |
| [`Dockerfile.micro`](Dockerfile.micro) | `ubi9/ubi-micro` | **none** | bash only | yes |

`Dockerfile.micro` is the recommended pattern: a full-UBI **builder** stage runs
`dnf upgrade` and `pixi install`, then the `pixi` binary and the solved
environment are `COPY`-ed into `ubi9-micro`. Both are relocatable — a conda-forge
environment bundles its own Python, OpenSSL, libstdc++, etc., and pixi is a single
glibc-linked binary — so they run on a near-empty base. The only host dependency
is glibc, which ubi-micro provides. What gets left behind is dnf and a few hundred
base-OS RPMs, *not* pixi.

## Results

Built `linux/arm64` with pixi 0.70.1, scanned with Trivy 0.69 and Grype (latest DB).

### Image size

| Variant | Uncompressed size | OS (RPM) packages | Environment packages |
|---------|------------------:|------------------:|---------------------:|
| full    | 803 MB | 188 | 41 |
| minimal | 666 MB | 112 | 41 |
| micro   | **511 MB** | **22** | 41 |

Micro is ~36% smaller than the full base. (The pixi binary itself adds ~65 MB to
each image but, as the scans below show, **zero** vulnerabilities.)

### Vulnerabilities

**Trivy** (`--scanners vuln`):

| Variant | Critical | High | Medium | Low | Total |
|---------|:--------:|:----:|:------:|:---:|:-----:|
| full    | 0 | 1 | 129 | 226 | **356** |
| minimal | 0 | 0 | 67  | 57  | **124** |
| micro   | 0 | 0 | 10  | 6   | **16**  |

**Grype:**

| Variant | Critical | High | Medium | Low | Total |
|---------|:--------:|:----:|:------:|:---:|:-----:|
| full    | 2 | 3 | 135 | 226 | **368** |
| minimal | 2 | 2 | 76  | 58  | **139** |
| micro   | 2 | 2 | 21  | 8   | **34**  |

Two things worth understanding before you act on these numbers:

- **Every Trivy finding is an OS (RPM) package.** The environment scans clean in
  Trivy, so the 356 → 16 drop is purely the shrinking base OS. Trivy's single
  HIGH on the full base is `gdb-gdbserver` (CVE-2026-6846, no fix) — a debugger
  with no business in production, gone on micro.
- **Grype's constant 2 Critical + 2 High are the CPython binary itself**
  (`python 3.12.13`), so they appear identically on all three images. Shrinking
  the base does not touch them — you fix those by updating the environment. This
  is also why the two scanners disagree: they read different databases and match
  the interpreter differently. Run both.
- **The pixi binary adds no findings.** Neither scanner flags the ~65 MB pixi
  executable, so keeping pixi in the runtime image costs disk but not CVEs.

Full per-CVE tables are checked in under [`.scan-results/`](.scan-results/).

## Usage

```bash
# Build a variant
docker build -f Dockerfile.micro -t pixi-ubi:micro .

# Run it (prints the demo workload)
docker run --rm pixi-ubi:micro

# Scan it
trivy image pixi-ubi:micro
grype pixi-ubi:micro
```

### Building a custom app on top

All three images are usable as a base for your own app — see
[`examples/Dockerfile.app`](examples/Dockerfile.app):

```bash
docker build -f examples/Dockerfile.app --build-arg BASE=pixi-ubi:micro -t my-app .
docker run --rm my-app
```

The catch on **micro**: there is no package manager, so you extend it by `COPY`
only. You cannot `RUN dnf install ...`. If a layer needs OS packages, build on
the full/minimal base — or, better, add the dependency to `pixi.toml` and rebuild
the base.

CI (`.github/workflows/scan.yml`) builds all three, smoke-tests them, and runs
both scanners on every push.
