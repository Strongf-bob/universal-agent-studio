# Slice 0 Foundation Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Slice 0 with reviewed product/security/design foundations, canonical AgentSpec and Run JSON Schemas, valid/invalid fixtures, cross-language conformance checks, and an executable acceptance contract for Slice 1.

**Architecture:** JSON Schema 2020-12 in `contracts/schemas/v0.1.0` is the only contract source. Python `jsonschema` and TypeScript/Ajv validate the same fixture manifest, while documentation records security, frontend provenance, and the exact Slice 1 boundary. No runtime, provider SDK, database, Temporal workflow, or visual canvas is implemented in this plan.

**Tech Stack:** Markdown, YAML, JSON Schema 2020-12, Python 3.12–3.14, uv 0.8–0.11, `jsonschema==4.26.0`, `pytest==9.1.1`, Node.js 22–26, pnpm 10–11, TypeScript 7.0.2, `@types/node` 26.1.1, Ajv 8.20.0, Vitest 4.1.10.

## Global Constraints

- `AgentSpec` is the only source of truth for agent behavior; canvas state is not runtime state.
- Published versions and run snapshots are immutable and content-addressed.
- Secret values are forbidden in AgentSpec, fixtures, events, traces, browser bundles, and repository history.
- Provider-specific configuration may appear only under `extensions.<provider_namespace>`.
- RunEvent delivery is at-least-once; `event_id` deduplicates and `sequence` resumes a stream.
- User-visible requirements and examples cover both `ru-RU` and `en-US`.
- Every coherent task ends with verification, a commit on `main`, a push, and a README audit when documented behavior changes.
- Third-party software is not installed until source, exact version, license, purpose, and upgrade owner are recorded.

---

### Task 1: Close design, security, and frontend provenance documentation

**Files:**
- Create: `tests/contracts/test_authoring_contracts.py`
- Modify: `DESIGN.md`
- Modify: `SECURITY.md`
- Modify: `README.md`
- Modify: `third_party/candidates.yaml`
- Create: `docs/THREAT_MODEL.md`
- Create: `docs/FRONTEND_SOURCES.md`

**Interfaces:**
- Consumes: `PRODUCT.md`, `ARCHITECTURE.md`, `docs/ARCHITECTURAL_INVARIANTS.md`, ADR-0003, ADR-0005, ADR-0006.
- Produces: explicit UX states and responsive/accessibility requirements; trust-boundary threat inventory; approved/rejected frontend-source policy; dependency review records used by later implementation plans.

- [x] **Step 1: Extend the design specification**

Add concrete sections to `DESIGN.md`:

```markdown
## 12. Responsive application shells

- Studio: desktop-first, usable from 1024 CSS px; narrow layouts replace the three-column canvas with Library/Canvas/Inspector tabs.
- Published App: mobile-first from 320 CSS px.
- Runs and Trace: timeline and table remain available without canvas.

## 13. Required interaction states

Every asynchronous interaction defines loading, empty, error, disabled, success, reconnecting and cancelled states. Error copy contains a stable support code but never credentials or raw provider payloads.

## 14. View-model boundary

React Flow nodes and edges are ephemeral view models produced from AgentSpec. Positions, selection, viewport, collapsed groups and panel state live in Studio layout metadata and never alter runtime semantics.

## 15. Slice 1 screens

1. Local owner setup.
2. Agent runner.
3. Run progress.
4. Structured result.
5. Read-only graph.
6. Node trace inspector.
```

- [x] **Step 2: Add a concrete threat model**

Create `docs/THREAT_MODEL.md` with assets, actors, entry points, trust boundaries, STRIDE-oriented threats, mandatory mitigations, deferred risks, and security acceptance tests. Include at minimum:

```markdown
| Boundary | Threat | Required control | First enforced |
|---|---|---|---|
| Browser → Control API | forged identity, CSRF, oversized input | secure session, CSRF token, size limit, schema validation | Slice 1 |
| API → Runtime worker | command tampering, duplicate execution | signed internal identity, immutable version digest, idempotency key | Slice 1 |
| Runtime → Model provider | secret/data leakage | CredentialReference resolution, policy routing, redaction | Slice 1 |
| Runtime → Tool | excessive agency, SSRF, duplicate side effect | typed manifest, scope, egress policy, idempotency | Slice 4 |
| Research → Production | unauthorized mutation | no write credentials, candidate-only API | Slice 8 |
| Code → Host | sandbox escape | separate sandbox service, no host mounts/network | Slice 6 |
```

- [x] **Step 3: Document frontend source decisions**

Create `docs/FRONTEND_SOURCES.md` with:

```markdown
| Area | Decision | Source | License | Boundary |
|---|---|---|---|---|
| Framework | Next.js + React | github.com/vercel/next.js | MIT | application shell only |
| Graph interaction | React Flow | github.com/xyflow/xyflow | MIT | adapter/view model only |
| Accessible primitives | Radix Primitives candidate | github.com/radix-ui/primitives | MIT | evaluate before Slice 2 |
| Styling | first-party tokens + CSS variables | repository | Apache-2.0 | no copied theme |
| Icons | Lucide candidate | github.com/lucide-icons/lucide | ISC | pin subset/version |
| Code editor | CodeMirror candidate | github.com/codemirror/dev | MIT | Slice 2 audit |
```

State that n8n, Langflow, Flowise and similar products may be studied for workflows but their UI/code/assets are not copied or forked without a new ADR and license review.

- [x] **Step 4: Update security baseline and dependency candidates**

Link `SECURITY.md` to `docs/THREAT_MODEL.md`. Add `data_classification`, `redaction_policy_id`, `retention_policy_id`, and `security_owner` as required metadata concepts. Add Next.js/React as approved future implementation candidates and Radix/Lucide/CodeMirror as review-required candidates in `third_party/candidates.yaml`; leave `version: null` because none is installed in this task.

- [x] **Step 5: Verify documentation**

Run:

```bash
git diff --check
ruby -ryaml -e 'YAML.safe_load(File.read("third_party/candidates.yaml"), permitted_classes: [], aliases: false); puts "YAML OK"'
ruby -e 'Dir.glob("**/*.md").each { |f| File.read(f).scan(/\[[^\]]+\]\(([^)]+)\)/).flatten.each { |u| next if u =~ %r{^(https?://|#)}; pth=u.split("#",2)[0]; next if pth.empty?; abort("BROKEN #{f}: #{u}") unless File.exist?(File.expand_path(pth,File.dirname(f))) } }; puts "MARKDOWN LINKS OK"'
python3 /Users/strongf/.codex/skills/beautify-github-readme/scripts/audit_readme.py README.md
```

Expected: `YAML OK`, `MARKDOWN LINKS OK`, README audit `OK`, and no diff errors.

- [x] **Step 6: Commit and push**

```bash
git add DESIGN.md SECURITY.md README.md third_party/candidates.yaml docs/THREAT_MODEL.md docs/FRONTEND_SOURCES.md
git commit -m "docs: close design and security foundations"
git push origin main
```

### Task 2: Establish contract validation toolchains

**Files:**
- Create: `.python-version`
- Create: `pyproject.toml`
- Create: `uv.lock`
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `pnpm-lock.yaml`
- Create: `contracts/conformance/package.json`
- Create: `contracts/conformance/tsconfig.json`
- Create: `contracts/conformance/vitest.config.ts`
- Modify: `.gitignore`
- Modify: `third_party/candidates.yaml`

**Interfaces:**
- Consumes: version boundaries from ADR-0001 and dependency policy.
- Produces: `uv run pytest`, `pnpm test:contracts`, and `pnpm check:contracts` root commands.

- [x] **Step 1: Install the declared Python package manager**

Run:

```bash
brew install uv
uv --version
```

Expected: uv version between 0.8 and 0.11.

- [x] **Step 2: Add Python project metadata**

Create `.python-version`:

```text
3.14
```

Create `pyproject.toml`:

```toml
[project]
name = "universal-agent-studio-contracts"
version = "0.1.0"
requires-python = ">=3.12,<3.15"
dependencies = []

[dependency-groups]
dev = [
  "jsonschema==4.26.0",
  "pytest==9.1.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

Run `uv sync` to create `uv.lock`.

- [x] **Step 3: Add JavaScript workspace metadata**

Create root `package.json`:

```json
{
  "name": "universal-agent-studio",
  "private": true,
  "packageManager": "pnpm@11.7.0",
  "engines": {
    "node": ">=22 <27",
    "pnpm": ">=10 <12"
  },
  "scripts": {
    "test:contracts": "pnpm --filter @universal-agent-studio/contract-conformance test",
    "check:contracts": "pnpm --filter @universal-agent-studio/contract-conformance check"
  }
}
```

Create `pnpm-workspace.yaml`:

```yaml
packages:
  - "apps/*"
  - "libs/typescript/*"
  - "contracts/conformance"
```

Create `contracts/conformance/package.json`:

```json
{
  "name": "@universal-agent-studio/contract-conformance",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "check": "tsc --noEmit"
  },
  "devDependencies": {
    "@types/node": "26.1.1",
    "ajv": "8.20.0",
    "typescript": "7.0.2",
    "vitest": "4.1.10"
  }
}
```

Create `contracts/conformance/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "resolveJsonModule": true,
    "noEmit": true,
    "lib": ["ES2022", "ESNext.Disposable"],
    "types": ["node"]
  },
  "include": ["src/**/*.ts", "tests/**/*.ts", "vitest.config.ts"]
}
```

Create `contracts/conformance/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"]
  }
});
```

Run `pnpm install` to create `pnpm-lock.yaml`.

- [x] **Step 4: Record exact dependencies**

Move the installed package versions, sources, licenses, purpose, security owner and upgrade path into `third_party/candidates.yaml` with status `installed_for_contract_validation`.

- [x] **Step 5: Verify clean toolchain**

Run:

```bash
uv run python --version
pnpm --version
```

Expected: supported Python and pnpm versions.

- [x] **Step 6: Commit and push**

```bash
git add .python-version pyproject.toml uv.lock package.json pnpm-workspace.yaml pnpm-lock.yaml contracts/conformance .gitignore third_party/candidates.yaml
git commit -m "build: add contract validation toolchains"
git push origin main
```

### Task 3: Define AgentSpec authoring contracts and fixtures

**Files:**
- Create: `contracts/schemas/v0.1.0/common.schema.json`
- Create: `contracts/schemas/v0.1.0/node-spec.schema.json`
- Create: `contracts/schemas/v0.1.0/model-profile.schema.json`
- Create: `contracts/schemas/v0.1.0/tool-manifest.schema.json`
- Create: `contracts/schemas/v0.1.0/interface-schema.schema.json`
- Create: `contracts/schemas/v0.1.0/agent-spec.schema.json`
- Create: `contracts/schemas/v0.1.0/agent-version.schema.json`
- Create: `contracts/examples/v0.1.0/valid/agent.calculator.ru-en.json`
- Create: `contracts/examples/v0.1.0/invalid/agent.secret-value.json`
- Create: `contracts/examples/v0.1.0/invalid/agent.dangling-edge.json`

**Interfaces:**
- Produces: schema IDs under `https://schemas.universal-agent.studio/v0.1.0/`; node kinds `input`, `model`, `tool`, `output`; port types expressed as JSON Schema fragments; immutable AgentVersion envelope.
- Invariants: unique node/edge IDs are enforced by conformance checks where JSON Schema cannot express cross-item uniqueness by property; secrets are represented only by `credential_ref`.

- [x] **Step 1: Write authoring contract tests and invalid fixture assertions**

Create `tests/contracts/test_authoring_contracts.py` first. It loads all schemas into a `referencing.Registry`, validates the golden fixture against `agent-spec.schema.json`, and asserts that required-field removal is rejected. Then create the three fixtures. The valid agent graph is:

```text
input:user_request → model:planner → tool:calculator → output:result
```

It includes RU/EN name and description, a deterministic fake model profile, a typed calculator manifest, and a structured result schema. The secret fixture inserts `api_key: "forbidden"` under model configuration. The dangling-edge fixture references `missing_node`.

- [x] **Step 2: Run Python validator before schemas exist**

Run the authoring contract test before schemas exist:

```bash
uv run pytest tests/contracts/test_authoring_contracts.py -q
```

Expected: failure because the test/schema files do not exist.

- [x] **Step 3: Implement authoring schemas**

Every schema uses:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.universal-agent.studio/v0.1.0/<name>.schema.json",
  "type": "object",
  "additionalProperties": false
}
```

`AgentSpec` requires:

```text
schema_version, agent_id, revision, localized_metadata,
nodes, edges, model_profiles, tools, interface, policies, extensions
```

IDs match `^[a-z][a-z0-9_-]{2,63}$`. `schema_version` is exactly `0.1.0`. Extension keys match reverse-DNS/provider namespaces and values are JSON objects.

- [x] **Step 4: Validate schema meta-schemas**

Run:

```bash
uv run python -c 'import json, pathlib; from jsonschema.validators import validator_for; [validator_for(json.loads(p.read_text())).check_schema(json.loads(p.read_text())) for p in pathlib.Path("contracts/schemas/v0.1.0").glob("*.json")]; print("SCHEMAS OK")'
```

Expected: `SCHEMAS OK`.

- [x] **Step 5: Commit and push**

```bash
git add contracts/schemas/v0.1.0 contracts/examples/v0.1.0
git commit -m "feat: define AgentSpec contracts"
git push origin main
```

### Task 4: Define run, event, trace, and error contracts

**Files:**
- Create: `contracts/schemas/v0.1.0/error-envelope.schema.json`
- Create: `contracts/schemas/v0.1.0/run-request.schema.json`
- Create: `contracts/schemas/v0.1.0/run-event.schema.json`
- Create: `contracts/schemas/v0.1.0/run-trace.schema.json`
- Create: `contracts/examples/v0.1.0/valid/run.request.json`
- Create: `contracts/examples/v0.1.0/valid/run.trace.completed.json`
- Create: `contracts/examples/v0.1.0/invalid/run.event.secret.json`
- Create: `contracts/examples/v0.1.0/invalid/run.event.sequence.json`

**Interfaces:**
- Produces: `RunRequest`, event envelope, terminal trace and stable error envelope consumed by Slice 1 API/runtime/web.
- RunEvent types: `run.started`, `node.started`, `model.requested`, `model.completed`, `tool.requested`, `tool.completed`, `node.completed`, `node.failed`, `run.completed`, `run.failed`.

- [ ] **Step 1: Add example lifecycle**

The valid trace contains ordered events with UUID `event_id`, one `run_id`, integer sequences starting at 1, UTC timestamps, causation IDs, redacted payloads, exact `agent_version_digest`, resolved fake model provenance, calculator tool provenance, and terminal structured output.

- [ ] **Step 2: Implement execution schemas**

`RunRequest` requires:

```text
schema_version, request_id, agent_version_id, agent_version_digest,
idempotency_key, input, locale
```

`RunEvent` requires:

```text
schema_version, event_id, run_id, sequence, type, occurred_at,
correlation_id, causation_id, node_id?, payload
```

`ErrorEnvelope` requires stable `code`, localized-safe `message_key`, `retryable`, optional `node_id`, and redacted `details`.

- [ ] **Step 3: Validate all schemas**

Run the meta-schema command from Task 3.

Expected: `SCHEMAS OK`.

- [ ] **Step 4: Commit and push**

```bash
git add contracts/schemas/v0.1.0 contracts/examples/v0.1.0
git commit -m "feat: define run and trace contracts"
git push origin main
```

### Task 5: Implement cross-language conformance tests

**Files:**
- Create: `contracts/examples/v0.1.0/manifest.json`
- Create: `tests/contracts/test_contract_examples.py`
- Create: `contracts/conformance/src/registry.ts`
- Create: `contracts/conformance/src/invariants.ts`
- Create: `contracts/conformance/tests/contracts.test.ts`

**Interfaces:**
- Consumes: fixture manifest entries `{path, schema, valid, expected_error_code}`.
- Produces: identical Python and TypeScript pass/fail results plus custom invariants for node/edge identity, dangling references, monotonic event sequence and forbidden secret-key names.

- [ ] **Step 1: Create the fixture manifest**

Use:

```json
{
  "schema_version": "1.0",
  "cases": [
    {
      "path": "valid/agent.calculator.ru-en.json",
      "schema": "agent-spec.schema.json",
      "valid": true
    },
    {
      "path": "invalid/agent.secret-value.json",
      "schema": "agent-spec.schema.json",
      "valid": false,
      "expected_error_code": "secret_key_forbidden"
    }
  ]
}
```

Include every fixture created in Tasks 3–4.

- [ ] **Step 2: Write Python tests**

Implement:

```python
def test_fixture_matches_declared_validity(case, registry):
    errors = validate_case(case, registry)
    assert (not errors) is case["valid"]

def test_valid_agent_has_no_dangling_edges(valid_agent):
    node_ids = {node["id"] for node in valid_agent["nodes"]}
    assert all(edge["source"]["node_id"] in node_ids for edge in valid_agent["edges"])
    assert all(edge["target"]["node_id"] in node_ids for edge in valid_agent["edges"])
```

Add recursive forbidden-key detection for `api_key`, `token`, `password`, `secret`, and `private_key`, while allowing `credential_ref`.

- [ ] **Step 3: Verify Python red then green**

Run before implementation completion:

```bash
uv run pytest tests/contracts -q
```

Expected initially: failures for custom invalid cases. Complete registry/reference resolution and invariants, rerun, expect all pass.

- [ ] **Step 4: Write TypeScript/Ajv tests**

`registry.ts` loads all schemas into one Ajv 2020 instance. `invariants.ts` returns stable error codes. The Vitest suite iterates the same manifest:

```ts
for (const fixtureCase of manifest.cases) {
  it(`${fixtureCase.valid ? "accepts" : "rejects"} ${fixtureCase.path}`, () => {
    const errors = validateFixture(fixtureCase);
    expect(errors.length === 0).toBe(fixtureCase.valid);
  });
}
```

- [ ] **Step 5: Verify cross-language result**

Run:

```bash
uv run pytest tests/contracts -q
pnpm check:contracts
pnpm test:contracts
```

Expected: all commands pass and both validators classify every manifest entry identically.

- [ ] **Step 6: Commit and push**

```bash
git add contracts/examples/v0.1.0/manifest.json contracts/conformance tests/contracts
git commit -m "test: add cross-language contract conformance"
git push origin main
```

### Task 6: Make Slice 0 continuously verifiable

**Files:**
- Create: `.github/workflows/contracts.yml`
- Create: `docs/acceptance/SLICE_1_EXECUTABLE_SPINE.md`
- Modify: `docs/CONTRACTS.md`
- Modify: `ROADMAP.md`
- Modify: `README.md`
- Modify: `third_party/candidates.yaml`

**Interfaces:**
- Produces: CI gate and the exact black-box contract for planning Slice 1.

- [ ] **Step 1: Add GitHub Actions contract gate**

Create:

```yaml
name: Contract Conformance

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          version: "0.11.32"
      - uses: pnpm/action-setup@v4
        with:
          version: "11.7.0"
      - uses: actions/setup-node@v4
        with:
          node-version: "26"
          cache: pnpm
      - run: uv sync --frozen
      - run: pnpm install --frozen-lockfile
      - run: uv run pytest tests/contracts -q
      - run: pnpm check:contracts
      - run: pnpm test:contracts
```

Record GitHub Actions sources, exact major/version policy and licenses in the dependency registry.

- [ ] **Step 2: Write Slice 1 executable acceptance contract**

`docs/acceptance/SLICE_1_EXECUTABLE_SPINE.md` must define:

- local prerequisites and one start command;
- owner setup;
- import/publish the golden agent;
- Web and API run inputs;
- exact structured output schema;
- expected RunEvent ordering;
- stream reconnect from sequence;
- idempotent request replay;
- node-level trace contents;
- RU/EN behavior;
- forbidden secret locations;
- deterministic CI path and separate BYOK smoke path;
- explicit exclusions.

- [ ] **Step 3: Close Slice 0 documentation**

Mark Slice 0 complete only after local verification and passing remote CI. Update README status to `Slice 0 complete / Slice 1 planning`. Link schemas, acceptance contract, threat model and frontend sources.

- [ ] **Step 4: Run full local verification**

Run:

```bash
git diff --check
uv sync --frozen
pnpm install --frozen-lockfile
uv run pytest tests/contracts -q
pnpm check:contracts
pnpm test:contracts
python3 /Users/strongf/.codex/skills/beautify-github-readme/scripts/audit_readme.py README.md
```

Expected: every command passes.

- [ ] **Step 5: Commit and push**

```bash
git add .github/workflows/contracts.yml docs/acceptance/SLICE_1_EXECUTABLE_SPINE.md docs/CONTRACTS.md ROADMAP.md README.md third_party/candidates.yaml
git commit -m "ci: enforce Slice 0 contract gates"
git push origin main
```

- [ ] **Step 6: Verify remote state**

Run:

```bash
gh run list --workflow contracts.yml --branch main --limit 1
gh run watch --exit-status
git status --short --branch
```

Expected: latest workflow succeeds and local `main` matches `origin/main`.

## Self-review

- Spec coverage: design, security, OSS provenance, canonical schemas, valid/invalid examples, cross-language tests, RU/EN, CI and Slice 1 acceptance are assigned to explicit tasks.
- Scope: no runtime, canvas, provider SDK, database, Temporal workflow, sandbox or autoresearch implementation enters Slice 0.
- Type consistency: schema version is `0.1.0`; event `sequence` is a positive integer; digest is a lowercase SHA-256 hex string; every run binds to `agent_version_id` and `agent_version_digest`.
- Publication boundary: every task uses a focused commit and pushes only after local checks.
