# NOVA + Hydrat Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated, observable Hydrat integration to NOVA without changing the existing AmneziaWG 3.1 entry point, with production traffic changes disabled by default.

**Architecture:** NOVA gets a small `nova_hydrat.py` adapter and UI/API layer. The adapter talks only to a verified Hydrat local API or an explicit allow-listed service command; it never rewrites `awg0`. Hydrat deployment is separate from `update-panel.sh` and starts in `observe` mode.

**Tech Stack:** Python 3.12, Flask, SQLite, systemd/Docker as required by the verified Hydrat upstream, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-17-hydrat-integration-design.md`

## Global Constraints

- Existing `/etc/amnezia/amneziawg/awg0.conf` and `awg-quick@awg0.service` remain outside the Hydrat control path.
- Default integration mode is `observe`.
- No public Hydrat admin port is introduced by default.
- No `shell=True` and no user-controlled shell fragments.
- VLESS credentials, UUIDs, passwords, Tor bridge secrets, and AWG private keys are never emitted to UI/logs.
- Secret-bearing files use mode `0600`.
- `update-panel.sh` installs NOVA integration only; Hydrat runtime installation is a separate explicit lifecycle command.
- Existing NOVA 11.1 tests and AWG consistency checks must continue to pass.

---

### Task 1: Verify and pin the Hydrat upstream runtime

**Files:**
- Create: `docs/superpowers/hydrat-upstream.md`

**Interfaces:**
- Produces the exact upstream repository URL, immutable commit/tag, build method, runtime API/CLI contract, required privileges, and deployment model consumed by Tasks 2–6.

- [ ] **Step 1: Extract the upstream Git link from the published Hydrat article.**

Use the published article as the source of truth for the link rather than guessing a repository name. The article describes Hydrat as a WireGuard gateway with VLESS/Tor exits, health checks, failover, and Docker-based operation.

- [ ] **Step 2: Clone only the verified repository into a temporary directory and inspect its README, compose/service files, configuration examples, and license.**

Run:
```bash
tmpdir=$(mktemp -d)
git clone --depth 1 <VERIFIED_HYDRAT_REPOSITORY_URL> "$tmpdir/hydrat"
cd "$tmpdir/hydrat"
git rev-parse HEAD
find . -maxdepth 2 -type f | sort
```
The `<VERIFIED_HYDRAT_REPOSITORY_URL>` value must be replaced by the URL obtained from the article; do not infer it from unrelated Hydrat-like projects.

- [ ] **Step 3: Record the exact ref and runtime contract.**

Document the resolved commit SHA, image/build command, exposed local API/CLI, required ports, required capabilities, state directory, configuration directory, and whether Docker is mandatory. If the upstream source cannot be resolved or does not expose a stable management contract, stop implementation and report that fact instead of substituting another project.

- [ ] **Step 4: Commit the pinned upstream record.**

Run:
```bash
git add docs/superpowers/hydrat-upstream.md
git commit -m "docs: pin verified Hydrat upstream"
```

---

### Task 2: Build the NOVA adapter and persistent integration state

**Files:**
- Create: `nova_hydrat.py`
- Create: `tests/test_nova_hydrat.py`
- Modify: `panel_bootstrap.py`

**Interfaces:**
- Produces `HydratAdapter.status() -> dict`, `HydratAdapter.sources() -> list[dict]`, `HydratAdapter.candidates() -> list[dict]`, `HydratAdapter.routes() -> list[dict]`, `HydratAdapter.events() -> list[dict]`, `HydratAdapter.plan() -> dict`, `HydratAdapter.set_mode(mode: str) -> dict`, and `HydratAdapter.validate() -> dict`.
- `mode` is exactly one of `disabled`, `observe`, `active`.

- [ ] **Step 1: Write failing tests for absent Hydrat and mode persistence.**

```python
def test_absent_hydrat_is_safe(monkeypatch, tmp_path):
    adapter = HydratAdapter(db_path=tmp_path / "panel.db", endpoint="http://127.0.0.1:1")
    status = adapter.status()
    assert status["installed"] is False
    assert status["mode"] == "observe"


def test_mode_transition_is_persisted(tmp_path):
    adapter = HydratAdapter(db_path=tmp_path / "panel.db", endpoint="http://127.0.0.1:1")
    assert adapter.set_mode("active")["mode"] == "active"
    assert HydratAdapter(db_path=tmp_path / "panel.db", endpoint="http://127.0.0.1:1").status()["mode"] == "active"
```

- [ ] **Step 2: Run the focused test and confirm failure.**

Run:
```bash
pytest -q tests/test_nova_hydrat.py
```
Expected: import/attribute failure because the adapter does not exist yet.

- [ ] **Step 3: Implement SQLite initialization and the adapter boundary.**

Create the four NOVA-side tables from the spec: `hydrat_settings`, `hydrat_sources`, `hydrat_events`, and `hydrat_plan_snapshots`. Keep Hydrat's own database authoritative for candidate/route state. Use a structured HTTP client or fixed subprocess allow-list from the verified upstream contract. Redact URL credentials before persistence or output.

- [ ] **Step 4: Implement safe status normalization.**

The normalized status must contain `installed`, `controller_state`, `agent_state`, `mode`, `last_health`, `last_plan`, `active_route_count`, `candidate_count`, and `last_error`, with safe scalar values only. An unreachable endpoint must return a structured unhealthy/not-installed state instead of raising into Flask startup.

- [ ] **Step 5: Implement mode enforcement.**

`observe` and `disabled` must reject any traffic mutation operation. `active` may only invoke the verified upstream route-application operation after `validate()` succeeds. Do not add a generic command runner.

- [ ] **Step 6: Run focused tests and commit.**

Run:
```bash
pytest -q tests/test_nova_hydrat.py
python -m py_compile nova_hydrat.py
```
Expected: PASS.

Commit:
```bash
git add nova_hydrat.py tests/test_nova_hydrat.py panel_bootstrap.py
git commit -m "feat: add isolated Hydrat adapter"
```

---

### Task 3: Add authenticated Hydrat API and UI

**Files:**
- Create: `nova_hydrat_ui.py`
- Create: `tests/test_nova_hydrat_ui.py`
- Modify: `panel_bootstrap.py`

**Interfaces:**
- Produces `GET /hydrat`, `GET /api/hydrat/status`, `/sources`, `/candidates`, `/routes`, `/events`, `/plan`, plus `POST /api/hydrat/mode` and `POST /api/hydrat/validate`.
- POST endpoints use the existing NOVA session authentication mechanism.

- [ ] **Step 1: Write failing Flask tests.**

```python
def test_hydrat_page_requires_login():
    client = app.test_client()
    response = client.get("/hydrat")
    assert response.status_code in (302, 401)


def test_hydrat_status_is_safe_when_absent():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["logged"] = 1
    response = client.get("/api/hydrat/status")
    assert response.status_code == 200
    assert response.get_json()["mode"] == "observe"


def test_mode_endpoint_rejects_anonymous_mutation():
    response = app.test_client().post("/api/hydrat/mode", json={"mode": "active"})
    assert response.status_code in (302, 401, 403)
```

- [ ] **Step 2: Run the tests and confirm failure.**

Run:
```bash
pytest -q tests/test_nova_hydrat_ui.py
```

- [ ] **Step 3: Implement the Hydrat page using existing NOVA layout conventions.**

Add a `HYDRAT` navigation item and cards for installation/service state, integration mode, sources, health, route assignments, events, and plan preview. Mask VLESS and Tor credentials. Do not add a subjective server score.

- [ ] **Step 4: Implement the read-mostly API.**

Every GET returns adapter-normalized data. `POST /api/hydrat/mode` accepts only `disabled`, `observe`, `active`; switching to `active` calls validation first and refuses activation on failed validation. `POST /api/hydrat/validate` is read/verify only.

- [ ] **Step 5: Run focused and existing tests.**

Run:
```bash
pytest -q tests/test_nova_hydrat_ui.py tests/test_panel.py tests/test_nova11_1.py
```
Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add nova_hydrat_ui.py tests/test_nova_hydrat_ui.py panel_bootstrap.py
 git commit -m "feat: add Hydrat control panel"
```

---

### Task 4: Add explicit Hydrat lifecycle and rollback tooling

**Files:**
- Create: `hydrat-manager.sh`
- Create: `hydrat.service`
- Create: `tests/test_hydrat_manager.sh`
- Modify: `update-panel.sh`

**Interfaces:**
- `hydrat-manager.sh install|validate|observe|active|rollback|remove|status`.
- `install` creates isolated directories and service account; `observe` is the default; `active` requires successful validation; `rollback` disables active mode and restores the last known-good Hydrat plan.

- [ ] **Step 1: Write shell safety tests.**

```bash
#!/usr/bin/env bash
set -euo pipefail
bash -n hydrat-manager.sh
printf '%s\n' "test-source" | grep -q test-source
! grep -n 'awg-quick@awg0.*stop\|awg-quick@awg0.*disable' hydrat-manager.sh
! grep -n '/etc/amnezia/amneziawg/awg0.conf.*rm\|rm .*awg0.conf' hydrat-manager.sh
```

- [ ] **Step 2: Implement isolated directories and service account.**

Use `/opt/nova-hydrat` for runtime/state and `/etc/nova-hydrat` for configuration. Keep credentials in mode `0600`. The service must not run as the NOVA web process user if the upstream runtime permits a separate account.

- [ ] **Step 3: Implement lifecycle commands from the verified upstream contract.**

`install` installs only the pinned upstream artifact. `validate` checks binaries/images, config permissions, local connectivity, and service health. `observe` starts collection without route mutation. `active` requires a successful validation result. `rollback` restores the last-known-good Hydrat plan. `remove` removes only Hydrat files/services.

- [ ] **Step 4: Add a hard guard against AWG mutation.**

The manager must fail closed if a requested operation would modify `/etc/amnezia/amneziawg/awg0.conf`, change `awg-quick@awg0.service`, or alter the existing AWG listener. The guard is tested with fixture paths, not production files.

- [ ] **Step 5: Modify `update-panel.sh` only to copy the NOVA integration files.**

Do not make the ordinary updater install/start Hydrat. Add `nova_hydrat.py`, `nova_hydrat_ui.py`, and their service-independent assets to the existing runtime copy list, then compile them. Leave Hydrat installation to `hydrat-manager.sh install`.

- [ ] **Step 6: Run shell and Python checks.**

```bash
bash -n hydrat-manager.sh
python -m py_compile nova_hydrat.py nova_hydrat_ui.py
pytest -q
```

- [ ] **Step 7: Commit.**

```bash
git add hydrat-manager.sh hydrat.service tests/test_hydrat_manager.sh update-panel.sh
 git commit -m "feat: add explicit Hydrat lifecycle and rollback"
```

---

### Task 5: Add source validation, redaction, plan snapshots, and failover preview

**Files:**
- Modify: `nova_hydrat.py`
- Modify: `nova_hydrat_ui.py`
- Create: `tests/test_hydrat_security.py`

**Interfaces:**
- `redact_source(value: str) -> str`
- `validate_source(kind: str, value: str) -> dict`
- `snapshot_plan(plan: dict, mode: str, result: str) -> str`

- [ ] **Step 1: Write failing security tests.**

```python
def test_vless_credentials_are_redacted():
    raw = "vless://secret-uuid@example.com:443?security=reality"
    safe = redact_source(raw)
    assert "secret-uuid" not in safe
    assert "example.com" in safe


def test_observe_plan_never_applies(monkeypatch, adapter):
    adapter.set_mode("observe")
    result = adapter.apply_plan({"routes": []})
    assert result["applied"] is False
    assert result["reason"] == "observe-mode"
```

- [ ] **Step 2: Run focused tests and confirm failure.**

```bash
pytest -q tests/test_hydrat_security.py
```

- [ ] **Step 3: Implement strict source validation.**

Accept only the source types defined by the verified Hydrat contract. Enforce a maximum input size, reject control characters and malformed URLs, and store only masked metadata in NOVA-side tables.

- [ ] **Step 4: Implement plan hashing and last-known-good snapshots.**

Canonicalize JSON with sorted keys, hash it with SHA-256, persist hash/mode/result, and mark a plan `last-known-good` only after the upstream validation/apply acknowledgement succeeds.

- [ ] **Step 5: Implement preview-only failover information.**

Show primary, backup, health state, and proposed change reason as factual state. Do not invent a single subjective quality score. In observe mode, the adapter returns the plan but never applies it.

- [ ] **Step 6: Run full tests and commit.**

```bash
pytest -q
```
Expected: PASS.

```bash
git add nova_hydrat.py nova_hydrat_ui.py tests/test_hydrat_security.py
git commit -m "feat: add Hydrat source security and plan snapshots"
```

---

### Task 6: Integrate CI and verify deployment behavior

**Files:**
- Modify: `.github/workflows/python-check.yml`
- Modify: `README.md`
- Create: `docs/superpowers/hydrat-verification.md`

**Interfaces:**
- CI compiles/imports the Hydrat modules, runs all tests, and validates shell syntax.
- Documentation gives exact commands for observe-mode installation, validation, activation, and rollback.

- [ ] **Step 1: Add Hydrat modules to Python compile/import checks.**

Extend the existing Python 3.12 workflow so `nova_hydrat.py` and `nova_hydrat_ui.py` are compiled and imported. Keep the existing NOVA modules and tests unchanged. The current workflow already compiles/imports the panel modules and runs `pytest -q`. fileciteturn70file0

- [ ] **Step 2: Add shell syntax checks.**

Add `hydrat-manager.sh` to the existing `bash -n` step.

- [ ] **Step 3: Add deployment documentation.**

Document:
```bash
cd /root/awg31-panel
git fetch origin nova-hydrat
git checkout nova-hydrat
./hydrat-manager.sh install
./hydrat-manager.sh validate
./hydrat-manager.sh observe
```
Explain that the ordinary `update-panel.sh` does not install Hydrat and that `active` must be explicitly selected only after validation.

- [ ] **Step 4: Document rollback.**

```bash
./hydrat-manager.sh rollback
./hydrat-manager.sh status
systemctl is-active awg-quick@awg0.service
```
The expected result is that the existing AWG service remains active and its configuration is untouched.

- [ ] **Step 5: Run the complete verification suite.**

```bash
python -m py_compile app.py app9.py nova11.py panel_bootstrap.py nova_hydrat.py nova_hydrat_ui.py
bash -n update-panel.sh hydrat-manager.sh
pytest -q
```
Expected: PASS.

- [ ] **Step 6: Commit and push the completed implementation branch.**

```bash
git add .github/workflows/python-check.yml README.md docs/superpowers/hydrat-verification.md
git commit -m "ci: verify Hydrat integration"
git push origin nova-hydrat
```

---

### Task 7: Final verification before PR

**Files:**
- No source changes unless a verification failure requires a targeted fix.

- [ ] **Step 1: Verify the branch contains only the intended Hydrat changes.**

Run:
```bash
git diff --stat main...nova-hydrat
git diff --check main...nova-hydrat
```

- [ ] **Step 2: Verify AWG-sensitive files were not changed by the integration.**

Run:
```bash
git diff main...nova-hydrat -- /etc/amnezia/amneziawg/awg0.conf
grep -R "awg-quick@awg0.*stop\|awg-quick@awg0.*disable\|rm .*awg0.conf" -n hydrat-manager.sh nova_hydrat.py nova_hydrat_ui.py || true
```
The repository must not contain a deployment operation that disables or removes the existing AWG service/configuration.

- [ ] **Step 3: Run CI and inspect the workflow result.**

The branch must have a successful Python check before opening the PR. Do not claim completion while CI is failing or queued.

- [ ] **Step 4: Open a draft PR from `nova-hydrat` to `main`.**

Use title `NOVA: add isolated Hydrat gateway integration` and state explicitly that the first release defaults to observe mode and does not replace `awg0`.

- [ ] **Step 5: Stop before production activation.**

The implementation is complete only when the branch and CI are green. Production `active` mode remains a separate administrator action after observing and validating the real Hydrat runtime.
