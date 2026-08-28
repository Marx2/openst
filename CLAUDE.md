## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- ALWAYS read graphify-out/GRAPH_REPORT.md before reading any source files, running grep/glob searches, or answering codebase questions. The graph is your primary map of the codebase.
- IF graphify-out/wiki/index.md EXISTS, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Dev workflow: fix → test → push → deploy

### 1. Fix / develop
- Edit files under `src/`
- Use `uvicorn.access` is OFF-LIMITS as a logger — it has a custom formatter expecting exactly 5 positional args; using it with f-strings or wrong arg counts raises `ValueError`. Use `logging.getLogger("openst")` with an explicit `StreamHandler` instead.

### 2. Test (always via docker compose)
```bash
docker compose --profile test run --rm test
```
- Tests require Redis — always use the compose test profile, never plain `pytest` locally.
- All 44 tests must pass before committing. The `test` profile in `docker-compose.yml` spins up Redis automatically.

### 3. Commit & push
- Follow Conventional Commits: `feat`, `fix`, `chore`, etc.
- Stage specific files, never `git add -A`.
```bash
git add src/... tests/...
git commit -m "type(scope): imperative summary"
git push origin main
```

### 4. Wait for GHA build
- GHA workflow (`.github/workflows/*.yml`) runs on push to `main`:
  1. `release` job — bumps patch version tag (e.g. `v1.0.14`)
  2. `build` job — builds and pushes Docker image to `ghcr.io/marx2/openst:<tag>`
- Poll until complete:
```bash
RUN_ID=$(gh run list --repo Marx2/openst --limit 1 --json databaseId -q '.[0].databaseId')
gh run view $RUN_ID --repo Marx2/openst --json status,conclusion -q '.status + " " + .conclusion'
```
- If runner fails with "not acquired by hosted runner" → GitHub infra issue. Check https://www.githubstatus.com, then rerun:
```bash
gh run rerun $RUN_ID --repo Marx2/openst --failed
```
- Get new version tag after success:
```bash
gh release list --repo Marx2/openst --limit 1
```

### 5. Deploy (update helmrelease)
Helmrelease path: `/Users/i318088/prv/homelab/homelab/cluster/apps/pfire/openst/app/helmrelease.yaml`

Update `tag:` field under `ghcr.io/marx2/openst`, then:
```bash
cd /Users/i318088/prv/homelab/homelab
git add cluster/apps/pfire/openst/app/helmrelease.yaml
git commit -m "chore(container): update image ghcr.io/marx2/openst to <tag>"
git pull --rebase && git push
```
- Remote may have diverged (Renovate bot commits frequently) — always `pull --rebase` before push.

### 6. Verify in cluster
Load kubeconfig before any `kubectl` commands:
```bash
export KUBECONFIG=$HOME/.kube/homylab
```
Check logs:
```bash
kubectl logs -n pfire -l app.kubernetes.io/name=openst --tail=50
```
Expected log format per request:
```
INFO:     GET /dividend/yield/XTB.WA -> 200 (623.4ms) 2.01
```
