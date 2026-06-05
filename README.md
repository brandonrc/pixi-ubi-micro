# pixi-ubi-micro

Companion repo for the OpenTeams Engineering blog post **"Slimmer, safer pixi
containers: a UBI-micro multi-stage build."**

It builds the **same** [pixi](https://pixi.sh) environment (Python 3.12 +
numpy/pandas/scipy) on three different Red Hat UBI9 bases and scans each with
[Trivy](https://github.com/aquasecurity/trivy) and
[Grype](https://github.com/anchore/grype). The environment is held constant on
purpose, so the only variable is the base image — and the entire difference in
image size and CVE count is attributable to the base OS.

| File | Base | Has package manager? | Has shell? |
|------|------|----------------------|------------|
| [`Dockerfile.full`](Dockerfile.full) | `ubi9/ubi` | dnf | yes |
| [`Dockerfile.minimal`](Dockerfile.minimal) | `ubi9/ubi-minimal` | microdnf | yes |
| [`Dockerfile.micro`](Dockerfile.micro) | `ubi9/ubi-micro` | **none** | bash only |

`Dockerfile.micro` is the recommended pattern: a full-UBI **builder** stage runs
`dnf upgrade` and `pixi install`, then only the solved environment is `COPY`-ed
into `ubi9-micro`. A conda-forge environment bundles its own Python, OpenSSL,
libstdc++, etc., so it runs on a near-empty base — the only host dependency is
glibc, which ubi-micro provides.

## Results

Built `linux/arm64`, scanned with Trivy 0.69 and Grype (latest DB).

### Image size

| Variant | Uncompressed size | OS (RPM) packages | Environment packages |
|---------|------------------:|------------------:|---------------------:|
| full    | 796 MB | 188 | 41 |
| minimal | 659 MB | 112 | 41 |
| micro   | **446 MB** | **22** | 41 |

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
