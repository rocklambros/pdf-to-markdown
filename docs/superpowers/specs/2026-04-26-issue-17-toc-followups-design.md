# Design — Issue #17 follow-ups (v1.0.4)

**Issue:** https://github.com/rocklambros/any2md/issues/17
**Target release:** v1.0.4
**Branch:** `fix/issue-17-toc-followups`
**Date:** 2026-04-26

## Scope

Two surgical fixes deferred from v1.0.3 (issue #16) and bundled into v1.0.4:

1. **Pipeline (T7)** — `dedupe_toc_table` misses TOC cells whose content includes leader-dot padding (`Purpose..............`). Result: leading TOC tables survive the strip pass and the audit flags `leading-toc-table` on Docling-rendered SafeBreach corpus files.
2. **Audit script** — `leading-toc-table` check fires on documents that have **no** `## ` heading anywhere in the body, because `body.split("\n## ", 1)[0]` returns the entire body and the leading-table regex matches any GFM table — even one that sits at the very end. Pure false positive.

Out of scope: any other v1.0.3 audit-flagged signals, broader TOC-detection refactor, snapshot regeneration of unrelated corpora.

## Code Changes

### A. `any2md/pipeline/text.py` — `dedupe_toc_table`

Normalize leader-dot padding from each cell before comparing against body H2/H3 titles. **Only the table-variant site (`dedupe_toc_table`, line ~263) needs the fix.** The text-block variant at line 182 already extracts the title via `_TOC_LINE_RE` (line 154), whose pattern `(.+?)(?:\s*\.{3,}|\s+)\s*\d+\s*$` consumes the leader-dot run as part of the match — `m.group(1)` is leader-dot-free, so no bug there.

Add a module-level constant:

```python
_LEADER_DOT_RE = re.compile(r"\.{3,}.*$")
```

Replace the cell-normalization step inside `dedupe_toc_table`:

```python
# Before
for cell in cells:
    if cell and not cell.replace(".", "").isdigit():
        toc_titles.add(cell.lower())

# After
for cell in cells:
    normalized = _LEADER_DOT_RE.sub("", cell).strip()
    if normalized and not normalized.replace(".", "").isdigit():
        toc_titles.add(normalized.lower())
```

Body-heading side untouched — Markdown headings don't contain `.{3,}` runs.

**Why:** issue #17 fix sketch. Validated against `Backup.pdf` and `Password.pdf` repro from SafeBreach Security Policies 2025 corpus.

### B. `scripts/audit-outputs.py` — leading-TOC check

**Note:** `scripts/audit-outputs.py` is currently untracked in git (verified via `git status`). The PR adds it to version control as part of this work, then applies the fix below. Issue #17 references the file as if it exists, which it does locally — the gap is just that it was never committed.

Guard the split with an `\n## ` membership check:

```python
# Before
pre_h2 = body.split("\n## ", 1)[0]
if LEADING_TABLE_BEFORE_H2_RE.search(pre_h2):
    flag(path, "leading-toc-table", "body has table before first H2")

# After
if "\n## " in body:
    pre_h2 = body.split("\n## ", 1)[0]
    if LEADING_TABLE_BEFORE_H2_RE.search(pre_h2):
        flag(path, "leading-toc-table", "body has table before first H2")
```

Chosen over a position-based "first 30%" heuristic because:
- Matches the issue's first fix-sketch option literally.
- Zero magic numbers.
- "No H2 in body" already means "no leading-TOC region defined" by the check's own definition.

### C. `any2md/__init__.py`

Bump `__version__` from `"1.0.3"` to `"1.0.4"`.

### D. `CHANGELOG.md`

New section above the v1.0.3 entry, following the established Keep-a-Changelog Added/Changed/Fixes/Tests structure:

```
## [1.0.4] — 2026-04-26

Patch release. Two follow-ups deferred from v1.0.3 (#17): the T7
dedupe_toc_table now normalizes leader-dot padding from TOC cells
before matching against body headings, so Docling-rendered TOC
tables (e.g., "Purpose..........Page") get properly stripped; and
the audit script's leading-toc-table check no longer false-flags
documents whose only GFM table sits at the end (skip when the body
contains no H2).

### Changed
- `pipeline/text.py::dedupe_toc_table` strips leader-dot
  padding (`re.sub(r'\.{3,}.*$', '', cell)`) from each TOC cell
  before lower-casing and matching against body H2/H3 titles.
  (The text-block TOC variant already handles this via
  `_TOC_LINE_RE`'s capture group — only the table-variant site
  needed the fix.)
- `scripts/audit-outputs.py` `leading-toc-table` check is now
  gated on "\n## " being present in the body — when no H2
  exists, no "leading-TOC region" is defined, so the check is
  skipped instead of matching the entire document.

### Fixes
- TOC tables with dotted-page-number padding (typical Docling
  output for SafeBreach-style PDFs — e.g., `Backup.pdf`,
  `Password.pdf`) now get stripped by T7 in aggressive/maximum
  profiles. Previously they survived because the cell content
  `"1.1. Purpose............."` failed string-equality with the
  body heading `"1.1. Purpose"`, dropping overlap below the 70%
  threshold.
- Audit script no longer reports false-positive
  `leading-toc-table` flags on documents whose only GFM table is
  at the end and the body contains no `## ` headings.

### Tests
- New `test_strips_toc_table_with_leader_dot_padding` in
  `tests/unit/pipeline/test_text_dedupe_toc_table.py` — TOC
  table whose cells carry leader-dot padding mirroring later H2
  headings still triggers the strip.
- New `tests/unit/scripts/test_audit_outputs.py` covering the
  audit-script `leading-toc-table` check: no-H2-with-trailing-
  table is NOT flagged; leading-table-before-H2 IS still flagged.

### Other
- `scripts/audit-outputs.py` is now tracked in version control
  (was previously local-only).
```

## Tests

### A. Extend `tests/unit/pipeline/test_text_dedupe_toc_table.py`

Add `test_strips_toc_table_with_leader_dot_padding`. Doc fixture: TOC table with cells like `"1.1. Purpose..........................."` → 4+ entries, body has matching `## 1.1. Purpose` etc. Aggressive profile must strip the table.

### B. New `tests/unit/scripts/test_audit_outputs.py` (and `tests/unit/scripts/__init__.py`)

Two tests against the audit script's `audit_file` function:

1. **No-H2-with-trailing-table is NOT flagged** — body containing only a trailing GFM table → `audit_file` emits zero `leading-toc-table` lines.
2. **Leading table before H2 IS still flagged** — body with table at top followed by `## Heading` → emits exactly one `leading-toc-table` line.

Implementation: write fixture `.md` files into `tmp_path` (with valid frontmatter so `split_frontmatter` succeeds), call `audit_file(path)`, capture stdout via `capsys`, assert presence/absence of the signal string.

### C. Full-suite regression check

`pytest tests/` and `ruff check . && ruff format --check .` must pass before push. Matches CI's `quality` and `smoke` job expectations.

## Parallelization Strategy

Two fixes touch disjoint files → ideal for subagent parallelism.

**Phase A — implementation (parallel, single message)**

- **Agent 1** (`backend-architect`, isolated worktree): implement T7 leader-dot fix in `any2md/pipeline/text.py` (both sites), extend `tests/unit/pipeline/test_text_dedupe_toc_table.py`, run targeted pytest, commit on agent-specific branch.
- **Agent 2** (`backend-architect`, isolated worktree): implement audit-script fix in `scripts/audit-outputs.py`, create `tests/unit/scripts/test_audit_outputs.py` + `__init__.py`, run targeted pytest, commit on agent-specific branch.

After both return, main session merges agent branches into `fix/issue-17-toc-followups` (no conflicts expected — disjoint files), then commits version bump + CHANGELOG (sequential — needs both fixes in place).

**Phase B — verification (sequential, main session)**

1. `pytest tests/` — full suite green.
2. `ruff check . && ruff format --check .` — green.
3. `python scripts/audit-outputs.py output/` against any local corpus available — sanity check.

**Phase C — review (parallel, single message)**

- **Agent 3** (`feature-dev:code-reviewer`): correctness review against issue #17 fix sketches, scope-creep check, regression check.
- **Agent 4** (`security-engineer`): ReDoS check on `\.{3,}.*$` regex, audit-script change review.

Blockers → fix sequentially → re-run Phase B.

## PR & Release Flow

### PR

- Branch: `fix/issue-17-toc-followups` → `main`.
- Title: `fix(v1.0.4): TOC leader-dot dedupe + audit-script H2 guard (#17)`.
- Body includes `Closes #17`, summary, repro snippet, test plan checklist.
- Wait for required CI checks: `quality`, `smoke (3.10)`, `smoke (3.12)`, `smoke (3.13)`, `audit`.
- Resolve all PR conversations.
- Merge with `gh pr merge --squash --admin` — `--admin` overrides the `require_last_push_approval` 0-review setting under `enforce_admins=true`. Squash keeps `main` history clean.

### TestPyPI release (prerelease)

- Tag `v1.0.4-rc1` (validator allows the `-rc1` suffix because `tag.startswith(version + "-")` is true).
- `gh release create v1.0.4-rc1 --prerelease --title "v1.0.4-rc1" --notes "<excerpt from CHANGELOG>"`.
- `publish.yml`'s `publish-testpypi` job fires.
- Smoke install in throwaway venv from TestPyPI with `[high-fidelity]` extras to confirm wheel + docling extras resolve.

### PyPI release (stable)

- Tag `v1.0.4` (matches `__version__` exactly).
- `gh release create v1.0.4 --title "v1.0.4" --notes "..."` (NOT prerelease).
- `publish.yml`'s `publish-pypi` job fires.
- Verify https://pypi.org/project/any2md/1.0.4/.

### System install with high-fidelity extras

```sh
pip install --upgrade 'any2md[high-fidelity]==1.0.4'
any2md --version
python -c "import any2md, docling; print(any2md.__version__, 'docling OK')"
```

Run `any2md` against one local PDF as final sanity check.

### Close-out

- `gh issue close 17 --comment "Shipped in v1.0.4 — see <PR-url> and <release-url>."`
- `git worktree prune` to clean up Phase A worktrees.

## Branch-Protection Compliance

Settings (verified via `gh api repos/.../branches/main/protection`):
- `required_status_checks`: `quality`, `smoke (3.10)`, `smoke (3.12)`, `smoke (3.13)`, `audit` — all must pass before merge.
- `enforce_admins`: true — admin-merge allowed but does NOT bypass status checks.
- `required_conversation_resolution`: true — resolve every PR thread.
- `allow_force_pushes`: false to `main`; force-push to feature branch only if rebasing.
- `require_last_push_approval` with 0 required reviews → `--admin` flag required for self-merge after green checks.

No protection rule will be bypassed. `--admin` is used only to satisfy the self-merge mechanism, never to skip failing checks.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Snapshot tests drift due to T7 now stripping previously-preserved tables | Run full `pytest` in Phase B; if snapshots drift, inspect each diff and either accept (correct new behavior) or narrow the regex |
| ReDoS on `\.{3,}.*$` | Anchored to `$` and applied to single cells (short strings); security agent confirms in Phase C |
| TestPyPI dependency resolution misses `docling` (TestPyPI doesn't always mirror) | `--extra-index-url https://pypi.org/simple/` in the smoke install |
| Release tag mismatch with `__version__` | `publish.yml`'s `validate` job enforces this; verified locally before pushing tag |
| Agent worktrees collide | Each agent uses `isolation: "worktree"`; main session merges sequentially |

## Success Criteria

- v1.0.4 published to PyPI.
- `pip install --upgrade 'any2md[high-fidelity]==1.0.4'` succeeds in user's system Python.
- `any2md --version` prints `1.0.4`.
- Issue #17 closed with reference to PR + release URL.
- Re-running `python scripts/audit-outputs.py` on the SafeBreach corpus shows zero `leading-toc-table` flags from either source (the trailing-table false positives AND the dotted-padding leading-TOC files).
