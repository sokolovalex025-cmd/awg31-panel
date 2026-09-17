# NOVA + Hydrat Integration Design

**Date:** 2026-09-17  
**Branch:** `nova-hydrat`  
**Status:** Design/specification only; implementation must not start until this spec is reviewed and approved.

## 1. Context

NOVA 11.1 currently operates the existing AmneziaWG 3.1 entry point and has a working AWG profile, diagnostics, nginx integration, and Telegram service. Hydrat is a separate gateway architecture described publicly on 2026-09-15: clients keep a WireGuard entry point while the server selects VLESS/Tor exits, checks candidate quality, and can fail over when an exit degrades. The public description mentions VLESS links/subscriptions, Tor bridges (obfs4/webtunnel), active checks, QoE measurements, weighted rendezvous hashing, sequential route application, and persistence of the last routing plan. These are source-derived capabilities, not assumptions that the Hydrat codebase has been independently audited. citeturn0search0turn0search2

## 2. Goals

1. Integrate Hydrat with NOVA as an isolated subsystem rather than replacing the existing AWG 3.1 service.
2. Keep `/etc/amnezia/amneziawg/awg0.conf` and `awg-quick@awg0.service` outside the Hydrat control path.
3. Add a NOVA Hydrat section showing service state, operating mode, sources, candidates, health, current route assignments, events, and the proposed next routing plan.
4. Start in **observe/validation mode**. Hydrat must not change production traffic automatically on first deployment.
5. Provide explicit enable/disable and rollback controls before any production route mutation is permitted.
6. Make the integration testable in CI without requiring a real VLESS server, Tor bridge, privileged network namespace, or production firewall.
7. Keep secrets and user-provided VLESS/Tor material out of Git history.

## 3. Non-goals

- Do not replace or reconfigure the current AWG 3.1 listener.
- Do not change the current AWG endpoint, keys, MTU, or `awg0` nftables rules as part of the first Hydrat integration.
- Do not expose a new Hydrat administration port publicly by default.
- Do not automatically accept arbitrary remote configuration and execute it as shell commands.
- Do not claim that Hydrat is production-proven or audited. The public article describes the design and implementation, but this integration must validate the actual code/package selected for deployment. citeturn0search0

## 4. Proposed architecture

```text
Client
  |
  | existing AWG 3.1
  v
NOVA / awg0
  |
  | optional, explicitly enabled data path
  v
Hydrat isolation boundary
  +-- controller / manager
  +-- route/health agent
  +-- Xray exits
  +-- Tor exits
  +-- private state DB
```

NOVA remains the control-plane UI. Hydrat is treated as a separately managed subsystem with a narrow adapter/API boundary. The adapter reads status and produces a desired route plan; it must not directly mutate `awg0`.

### 4.1 Isolation

The preferred deployment is a separate service/container or equivalent isolated runtime with its own Unix user, configuration directory, state directory, and logs. If the upstream Hydrat distribution mandates Docker, NOVA should manage the deployment lifecycle without embedding privileged Docker operations into ordinary web requests.

The initial integration should use localhost/private communication only. Any public-facing Hydrat admin endpoint is out of scope for the first release.

### 4.2 NOVA adapter

Add a small Python adapter layer, for example `nova_hydrat.py`, responsible for:

- detecting whether Hydrat is installed;
- reading service/status information;
- validating Hydrat configuration shape;
- exposing a safe read-only status model to the UI;
- generating a route-plan preview;
- recording integration events;
- enforcing the deployment mode (`disabled`, `observe`, `active`);
- refusing production mutations while in `observe` mode.

The adapter must use fixed command allow-lists or structured APIs. User-supplied source strings must never become shell command fragments.

## 5. Hydrat UI

Add a `HYDRAT` section to the existing NOVA navigation without changing the existing AWG pages.

### Status card

Show:

- installed / not installed;
- controller state;
- agent state;
- integration mode;
- last successful health cycle;
- last route-plan application;
- active route count;
- candidate count;
- last error.

### Sources

Display source type and status for:

- VLESS links;
- VLESS subscriptions;
- Tor bridges.

Secrets must be masked. The UI must not print full VLESS URLs or bridge credentials into ordinary logs.

### Health

Show candidate state, last check, latency/quality summary, failure state, and the reason a candidate is or is not eligible. Hydrat's public design describes fast availability checks and a separate QoE loop; the UI should represent these as distinct signals rather than collapsing them into one arbitrary score. citeturn0search2

### Routing

Show:

- current assignments;
- primary and backup candidate;
- proposed changes;
- reason for a proposed failover;
- timestamp of the last applied plan;
- whether the plan is only a preview or has been applied.

The UI must not expose an evaluative "best server" score. It should display factual health/selection inputs and the resulting assignment state.

## 6. API boundary

The first API surface should be small and read-mostly:

- `GET /api/hydrat/status`
- `GET /api/hydrat/sources`
- `GET /api/hydrat/candidates`
- `GET /api/hydrat/routes`
- `GET /api/hydrat/events`
- `GET /api/hydrat/plan`
- `POST /api/hydrat/mode`
- `POST /api/hydrat/validate`

Any endpoint that can affect traffic must require the existing NOVA authentication and an explicit active-mode check. There must be no anonymous route mutation endpoint.

## 7. Data model

NOVA-side state should be minimal and auditable. Proposed records:

- `hydrat_settings`: integration mode and local endpoint metadata;
- `hydrat_sources`: source identifier, type, enabled flag, masked metadata, timestamps;
- `hydrat_events`: event type, timestamp, severity, safe message, correlation id;
- `hydrat_plan_snapshots`: generated/applied plan hash, timestamp, mode, result.

Hydrat's own state database remains authoritative for Hydrat-specific candidate/route state when present. NOVA should not duplicate or rewrite that database directly.

## 8. Safety and security requirements

1. Existing AWG private keys must never be copied into Hydrat logs or UI responses.
2. VLESS credentials, UUIDs, passwords, and Tor bridge secrets must be treated as secrets.
3. Config files containing secrets must be mode `0600` and owned by the service account/root as appropriate.
4. The web layer must validate source type and size before forwarding it to Hydrat.
5. No `shell=True` for values derived from UI/API input.
6. Hydrat must run with the minimum practical privileges.
7. Network/firewall mutations must be performed by a dedicated, auditable mechanism rather than arbitrary web-server commands.
8. Default mode after installation is `observe`.
9. Rollback must be possible without touching `awg0` configuration.
10. Logs must redact credentials and full proxy URLs.

## 9. Traffic transition model

When active mode is eventually enabled, route changes should follow the safe order described by the Hydrat project: create/validate the new exit first, update routing rules second, and remove the old exit last. This ordering is intended to avoid transient client disconnection. citeturn0search2

The NOVA integration must additionally keep a last-known-good plan and require validation before applying a new plan. If validation fails, the previous plan remains active.

## 10. Deployment and rollback

`update-panel.sh` should install only the NOVA-side integration and supporting files unless Hydrat is explicitly requested for installation. A separate, idempotent Hydrat installer/manager is preferred so an ordinary NOVA update cannot unexpectedly introduce a privileged proxy stack.

Proposed lifecycle:

1. `install` — install package/runtime and create isolated directories.
2. `validate` — verify binaries, configuration, local connectivity, and permissions.
3. `observe` — collect status and health without modifying production traffic.
4. `active` — explicitly enabled by an administrator after validation.
5. `rollback` — restore the last known-good Hydrat route plan and disable active mode.
6. `remove` — remove Hydrat components while preserving NOVA/AWG state.

The remove/rollback path must never delete `/etc/amnezia/amneziawg/awg0.conf` or disable `awg-quick@awg0.service`.

## 11. Testing strategy

### Unit tests

- source validation and redaction;
- mode transitions;
- plan hashing and comparison;
- safe command allow-listing;
- adapter behavior when Hydrat is absent;
- adapter behavior when Hydrat is unhealthy;
- rollback decision logic.

### Integration tests

- Flask/API authentication;
- mocked Hydrat status endpoint;
- observe mode cannot mutate traffic;
- active mode requires explicit authorization;
- generated plan can be serialized/deserialized;
- secrets never appear in API output or test logs.

### Static/CI checks

- Python compile/import checks;
- shell syntax checks;
- existing pytest suite;
- new Hydrat tests;
- no changes to existing AWG configuration files during tests.

## 12. Acceptance criteria

The first implementation is accepted only when all of the following are true:

- `nova-hydrat` branch contains the design and implementation with passing CI;
- NOVA starts normally with Hydrat absent;
- NOVA explicitly reports Hydrat as `not installed` rather than failing;
- observe mode can read status and show a route-plan preview;
- no Hydrat deployment step changes `awg0` or the current AWG listener;
- all secrets are redacted from UI and logs;
- active mode is opt-in and auditable;
- rollback leaves the existing AWG 3.1 entry point intact;
- existing NOVA 11.1 tests and verification continue to pass.

## 13. Open decision before implementation

The upstream Hydrat repository/package must be identified and inspected before implementation of the deployment adapter. The public article links to a Git repository but the search result does not expose its repository URL, so the exact upstream artifact should not be guessed. citeturn0search0

Once the upstream source is verified, the implementation plan should pin its repository/ref or release and document the exact build/runtime contract.
