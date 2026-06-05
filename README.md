# pixi-ubi-micro

Companion repo for the OpenTeams Engineering blog post **"pixi on UBI-micro: A
Safer, Smaller Multi-Stage Container Build."**

It builds the **same** [pixi](https://pixi.sh) (v0.70.1) environment (Python 3.12
+ numpy/pandas/scipy) on three different Red Hat UBI9 bases and scans each with
[Trivy](https://github.com/aquasecurity/trivy) and
[Grype](https://github.com/anchore/grype). The environment is held constant on
purpose, so the base image and how it is patched are the only variables, and the
difference in image size and findings is the OS underneath.

All three images **ship the pixi binary and run via `pixi run`**. They are real
pixi containers, not just a baked environment. The "package manager" column below
refers to the *OS* package manager (dnf/microdnf), which is what drives the
base-OS attack surface:

| File | Base | OS package manager | Shell | Ships pixi |
|------|------|--------------------|-------|------------|
| [`Dockerfile.full`](Dockerfile.full) | `ubi9/ubi` | dnf | yes | yes |
| [`Dockerfile.minimal`](Dockerfile.minimal) | `ubi9/ubi-minimal` | microdnf | yes | yes |
| [`Dockerfile.micro`](Dockerfile.micro) | `ubi9/ubi-micro` | **none** | bash only | yes |

`Dockerfile.micro` is the recommended pattern: a full-UBI **builder** stage runs
`pixi install`, then the `pixi` binary and the solved environment are `COPY`-ed
into `ubi9-micro`. Both are relocatable: a conda-forge environment bundles its own
Python, OpenSSL, libstdc++, etc., and pixi is a single glibc-linked binary, so they
run on a near-empty base. The only shared library it needs from the host is glibc,
which ubi-micro provides. What gets left behind is dnf and nearly 200 base-OS RPMs,
*not* pixi.

**Patching the micro base.** The micro builder intentionally does *not* run
`dnf upgrade`: nothing from the builder's OS reaches the runtime, so it would
patch nothing. (full and minimal *do* upgrade, because their base OS ships to
production.) You keep micro's OS current from the outside, by pinning `ubi-micro`
to a digest and refreshing it on a schedule. Against a current base the residual
16 OS CVEs are all *no-fix* advisories (glibc, libgcc, pcre2, ncurses, coreutils),
so there is nothing to upgrade to.

If you are pinned to an **older** base and cannot re-qualify it yet (a common
enterprise case), you can still apply errata from the outside with
`dnf --installroot`: see [`Dockerfile.micro-patched`](Dockerfile.micro-patched).
dnf in the full-UBI builder patches the micro rootfs even though micro has no
package manager. Measured on `ubi-micro:9.2`: Trivy 67 CVEs (7 HIGH) drops to 16
(0 HIGH), the same floor as `:latest`.

```bash
docker build -f Dockerfile.micro-patched \
  --build-arg MICRO_BASE=registry.access.redhat.com/ubi9/ubi-micro:9.2 \
  -t pixi-ubi:micro-patched .
```

## Results

Built `linux/arm64` with pixi 0.70.1, scanned with Trivy 0.69 and Grype (latest DB).

### Image size

| Variant | Uncompressed size | OS (RPM) packages | Environment packages |
|---------|------------------:|------------------:|---------------------:|
| full    | 803 MB | 188 | 41 |
| minimal | 666 MB | 112 | 41 |
| micro   | **511 MB** | **22** | 41 |

Most of micro's 511 MB is the environment (~466 MB of conda packages + the ~65 MB
pixi binary, identical on every image); only ~45 MB is the micro OS, versus ~337 MB
on full. So the base swap saves a fixed ~290 MB of OS (~36% of the image here, less
as a fraction the heavier your environment gets). The pixi binary adds ~65 MB but,
as the scans below show, **zero** vulnerabilities.

### Vulnerabilities

**Trivy** (`--scanners vuln`):

| Variant | Critical | High | Medium | Low | Total |
|---------|:--------:|:----:|:------:|:---:|:-----:|
| full    | 0 | 1 | 129 | 226 | **356** |
| minimal | 0 | 0 | 67  | 57  | **124** |
| micro   | 0 | 0 | 10  | 6   | **16**  |

**Grype** (includes a Negligible tier Trivy does not have):

| Variant | Critical | High | Medium | Low | Negligible | Total |
|---------|:--------:|:----:|:------:|:---:|:----------:|:-----:|
| full    | 2 | 3 | 135 | 226 | 2 | **368** |
| minimal | 2 | 2 | 76  | 58  | 1 | **139** |
| micro   | 2 | 2 | 21  | 8   | 1 | **34**  |

What matters more than the totals:

- **The real win is attack surface, not the count.** The findings that vanish are
  mostly low-severity, no-fix OS advisories; the smaller image is a smaller blast
  radius (no package manager, no debugger, almost no userland), not "fewer bugs."
- **Every Trivy finding is an OS (RPM) package, and the env is only partly
  visible.** Trivy enumerates the 41 conda/Python packages and reports zero matches
  (read that as "no known advisory," not "audited": conda-forge DB coverage is
  thin, and Grype does not catalog the conda packages at all). Trivy's single HIGH
  on full is `gdb-gdbserver` (CVE-2026-6846, no fix), gone on micro.
- **The high-severity findings live in the interpreter and survive the move.**
  Grype's 2 Critical + 2 High are the CPython binary (`python 3.12.13`) and appear
  on every image. The full base adds one more High in `expat` (an OS RPM), which is
  why full shows 3 High, and which disappears with the base. You clear the CPython
  findings by updating the environment, not by shrinking the base. Run both
  scanners; they disagree because they match the interpreter differently.
- **The pixi binary adds no findings.** Neither scanner flags the ~65 MB pixi
  executable, so keeping pixi in the runtime image costs disk but not CVEs.

Full per-CVE tables (including the `ubi-micro:9.2` before/after for the patched
example) are checked in under [`.scan-results/`](.scan-results/).

### STIG / FIPS (a different axis)

Red Hat also ships `ubi9/ubi-stig` (STIG-hardened full UBI).
[`Dockerfile.stig`](Dockerfile.stig) builds pixi on it. STIG is about
configuration hardening and FIPS, not image size, so it goes the *other* way:
pixi-on-stig is 838 MB with 379 Trivy / 391 Grype findings (more than plain full,
including 4 Trivy HIGH / 7 Grype High vs 1 / 3 on full), because hardening adds
packages. And note the catch: FIPS is enforced by a FIPS-mode host + crypto
policy, but a conda-forge environment links its **own** bundled OpenSSL and does
not consult that policy, so its crypto runs outside the host's FIPS posture
regardless. A STIG base alone does not make a pixi container FIPS-compliant.

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

Two cases:

**Add your own code** with a plain `COPY` ([`examples/Dockerfile.app`](examples/Dockerfile.app)).
Works on all three bases, including micro:

```bash
docker build -f examples/Dockerfile.app --build-arg BASE=pixi-ubi:micro -t my-app .
docker run --rm my-app
```

**Add a dependency** the multi-stage way ([`examples/Dockerfile.app-multistage`](examples/Dockerfile.app-multistage)).
Do not `RUN pixi install` on micro (it re-bloats the slim runtime and drifts from
the lockfile). Instead solve on the full base, then copy the env into micro:

```bash
docker build -f examples/Dockerfile.app-multistage -t pixi-ubi:app-rich .
docker run --rm pixi-ubi:app-rich
```

When you own the base, the cleaner option is to add the dependency to `pixi.toml`
and rebuild the base. The rule: solve dependencies on the full base, run them on
micro.

## Caveats

These images are a focused demo, not a production template. They run as **root**
(add a non-root `USER` for production), they use `:latest` base tags (pin to a
digest), and the build fetches pixi with `curl | bash` (the installer script is
unpinned). The scans are **vulnerability-only**; a real gate should add
misconfiguration and secret scanning and prioritize by exploitability. CVE counts
are a point-in-time snapshot and drift as scanner databases update.

## CI

`.github/workflows/scan.yml` builds and smoke-tests all five variants
(full, minimal, micro, micro-patched, stig) plus the two example images, runs
Trivy + Grype on each, and uploads the Trivy reports. It runs on `linux/amd64`
against a live DB, so it is a gate and a re-run of the comparison, not a
byte-for-byte reproduction of the committed `linux/arm64` results.
