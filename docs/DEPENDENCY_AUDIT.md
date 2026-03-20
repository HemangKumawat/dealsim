# Dependency Security Audit

**Date:** 2026-03-19
**Scope:** `pyproject.toml`, `uv.lock`, `Dockerfile`
**Locked versions from uv.lock revision 3**

---

## 1. Direct Dependencies and Version Constraints

### Production

| Package | Constraint | Locked Version | Transitive Deps |
|---------|-----------|----------------|-----------------|
| fastapi | `>=0.110` | 0.135.1 | starlette, pydantic, typing-extensions, annotated-doc |
| uvicorn[standard] | `>=0.27` | 0.42.0 | click, h11, httptools, pyyaml, uvloop, watchfiles, websockets |
| pydantic | `>=2.0` | 2.12.5 | pydantic-core, annotated-types, typing-extensions, typing-inspection |

### Development

| Package | Constraint | Locked Version |
|---------|-----------|----------------|
| pytest | `>=8.0` | 9.0.2 |
| httpx | `>=0.27` | 0.28.1 |

### Build System

| Package | Role |
|---------|------|
| hatchling | Build backend |

---

## 2. Version Constraint Analysis

### fastapi `>=0.110`

**Verdict: Acceptable, but a ceiling would reduce breakage risk.**

The floor is reasonable -- 0.110+ requires Pydantic v2. However, the open ceiling means a future FastAPI 1.0 (which may introduce breaking changes) would be pulled automatically. For a production service, `>=0.110,<1.0` is safer.

### uvicorn[standard] `>=0.27`

**Verdict: Acceptable.** Uvicorn follows semver-ish conventions pre-1.0. The `[standard]` extra correctly pulls in httptools, uvloop, and websockets for production performance. Same ceiling concern applies: `>=0.27,<1.0` is marginally safer.

### pydantic `>=2.0`

**Verdict: Slightly too loose.** The floor at 2.0 admits versions with the ReDoS vulnerability (CVE-2024-3772, fixed in 2.4.0). Should be `>=2.4.0` at minimum to exclude known-vulnerable releases.

### pytest `>=8.0` / httpx `>=0.27`

**Verdict: Fine.** Dev dependencies. Loose floors are acceptable here since they never ship to production.

---

## 3. Known CVEs

### Affecting locked versions directly

| CVE | Package | Affected | Locked | Status |
|-----|---------|----------|--------|--------|
| CVE-2024-3772 | pydantic | <2.4.0 | 2.12.5 | **Not affected** (locked version is patched) |
| CVE-2024-47874 | starlette | <0.40.0 | 0.52.1 | **Not affected** |
| CVE-2020-7695 | uvicorn | <0.11.7 | 0.42.0 | **Not affected** |

### Not affecting this project (different packages)

- CVE-2025-68481 (fastapi-users, not fastapi core)
- CVE-2025-46814, CVE-2025-54365 (fastapi-guard, not used)
- CVE-2025-14546 (fastapi-sso, not used)

### Assessment

**No active CVEs affect the currently locked dependency versions.** The locked versions in `uv.lock` are all recent enough to contain all known patches. However, the `pyproject.toml` floor for pydantic (`>=2.0`) would permit installing a vulnerable version if the lock file were regenerated carelessly.

---

## 4. Unnecessary Dependencies

The dependency set is lean. Three production packages, two dev packages.

| Package | Verdict |
|---------|---------|
| fastapi | Required -- core framework |
| uvicorn[standard] | Required -- ASGI server |
| pydantic | Required -- already a transitive dep of FastAPI, but explicit declaration is correct practice |
| pytest | Required -- test runner |
| httpx | Required -- async test client for FastAPI (used by `TestClient`) |

**No unnecessary dependencies found.** This is a minimal, well-chosen set.

---

## 5. Lock File Assessment

**A `uv.lock` file exists** (revision 3, 600+ lines, covers all transitive dependencies with exact versions and hashes).

However, the Dockerfile runs `uv pip install --system .` which resolves from `pyproject.toml`, **not** from the lock file. This means:

- **Local development:** Reproducible (uv uses the lock file by default).
- **Docker builds:** **NOT reproducible.** Each build can resolve different transitive versions.

**Fix:** Change the Dockerfile install command to:

```dockerfile
COPY uv.lock .
RUN uv pip install --system --locked .
```

Or use `uv sync --system --locked` if the full project is available.

---

## 6. Dev/Production Dependency Separation

**Properly separated.** Dev dependencies (`pytest`, `httpx`) are under `[project.optional-dependencies] dev = [...]` and are not installed during a standard `pip install .` or Docker build. Only explicitly requesting `pip install .[dev]` pulls them in.

---

## 7. Python Version Requirement

**`pyproject.toml` says `>=3.11`; Dockerfile uses `python:3.12-slim`.**

| Factor | Assessment |
|--------|-----------|
| Python 3.11 EOL | October 2027 -- still supported |
| Python 3.12 EOL | October 2028 |
| Python 3.13 | Stable since October 2024 |
| FastAPI 0.135.1 | Supports 3.8+ |
| Pydantic 2.12.5 | Supports 3.9+ |

**Verdict:** The `>=3.11` floor is reasonable -- it gives deployment flexibility while still being modern enough. The Dockerfile correctly pins to 3.12 for the container image. Consider bumping the Dockerfile to `python:3.13-slim` for the latest security patches and performance improvements (3.13 has been stable for over a year).

If the project genuinely only targets containerized deployment, tightening to `>=3.12` in pyproject.toml would match the Dockerfile and avoid testing a matrix you never deploy.

---

## 8. License Audit

| Package | License | Commercial-safe? |
|---------|---------|-----------------|
| fastapi | MIT | Yes |
| uvicorn | BSD-3-Clause | Yes |
| pydantic | MIT | Yes |
| starlette | BSD-3-Clause | Yes |
| anyio | MIT | Yes |
| httptools | MIT | Yes |
| click | BSD-3-Clause | Yes |
| h11 | MIT | Yes |
| pytest | MIT | Yes |
| httpx | BSD-3-Clause | Yes |
| hatchling | MIT | Yes |

**No GPL, AGPL, or copyleft dependencies.** The entire dependency tree uses permissive licenses (MIT/BSD). There are no license conflicts for commercial use.

---

## 9. Dockerfile Security Review

```dockerfile
FROM python:3.12-slim
```

### Strengths
- Uses `-slim` variant (smaller attack surface than full image)
- Creates non-root user (`dealsim`) and switches to it
- Includes a `HEALTHCHECK`
- Single `EXPOSE` on port 8000

### Issues

| Issue | Severity | Detail |
|-------|----------|--------|
| Unpinned base image tag | Medium | `python:3.12-slim` floats to latest patch. Pin to a digest or specific patch (e.g., `python:3.12.9-slim-bookworm`) for reproducibility. |
| uv installed via pip without version pin | Medium | `pip install --no-cache-dir uv` installs latest uv. Pin it: `pip install --no-cache-dir uv==0.6.x`. |
| Lock file not used in build | High | See section 5. `uv pip install --system .` ignores `uv.lock`. |
| Base image OS CVEs | Low | Debian bookworm slim images carry some OS-level CVEs (gnutls, perl). These are typically patched in upstream updates. Rebuilding periodically or pinning to a recent digest mitigates this. |
| No `.dockerignore` verified | Low | Without a `.dockerignore`, `COPY src/ src/` is fine, but `COPY static/ static/` could pull in unintended files. |

---

## 10. Recommendations

### Must-do (security)

1. **Raise pydantic floor to `>=2.4.0`** to exclude CVE-2024-3772-vulnerable versions.
2. **Use the lock file in Docker builds.** Copy `uv.lock` and pass `--locked` to ensure reproducible, auditable builds.
3. **Pin the base Docker image** to a specific digest or patch version.

### Should-do (hardening)

4. **Add version ceilings** to production dependencies: `fastapi>=0.110,<1.0`, `uvicorn>=0.27,<1.0`, `pydantic>=2.4.0,<3.0`.
5. **Pin uv version** in Dockerfile: `pip install --no-cache-dir uv==0.6.6` (or current stable).
6. **Commit `uv.lock` to version control** -- it already exists, verify it is tracked in git.
7. Consider bumping Dockerfile to `python:3.13-slim` for latest security patches.

### Nice-to-have

8. Add a `[dependency-groups]` section (PEP 735) if uv supports it, for cleaner dev dependency management.
9. Set up automated dependency scanning (e.g., `uv pip audit`, Dependabot, or Snyk) in CI.
10. Add a `.dockerignore` if not already present.

---

## Sources

- [Snyk: FastAPI vulnerabilities](https://security.snyk.io/package/pip/fastapi)
- [CVE-2024-3772: Pydantic ReDoS](https://github.com/advisories/GHSA-mr82-8j83-vxmv)
- [CVE-2024-47874: Starlette multipart](https://medium.com/@onurbaskin/critical-security-vulnerability-in-starlette-fastapi-f75adfb86134)
- [Snyk: uvicorn vulnerabilities](https://security.snyk.io/package/pip/uvicorn)
- [Docker Hub: python:3.12-slim vulnerabilities](https://hub.docker.com/layers/library/python/3.12-slim/images/sha256-5eb1d9eb9ef435d2e4aa6bd5cc38bb26b391cb831124e3682c4d191632858b02?context=repo&tab=vulnerabilities)
- [Chainguard: Python image vulnerability comparison](https://edu.chainguard.dev/chainguard/chainguard-images/vuln-comparison/python/)
