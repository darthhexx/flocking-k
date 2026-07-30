#!/usr/bin/env bash
# M14.1 — initialise version control for the platform repo.
#
# WHY THIS IS A SCRIPT AND NOT ALREADY DONE:
# The cloud session reaches this folder through a file bridge that cannot unlink
# files. git needs to remove .git/index.lock after every index operation, so
# `git add` / `git commit` fail there with:
#     fatal: Unable to create '.../.git/index.lock': File exists.
# `git init` itself succeeded, which is why a stale lock is sitting in the repo.
# Run this on your Mac, where unlink works.
#
# Safe to re-run. Does nothing destructive except removing .git/index.lock.

set -euo pipefail

REPO="${1:-$HOME/AI/Flocking-K - Paper 2/flocking_kalman_research_platform}"
cd "$REPO"
echo "repo: $(pwd)"

# 1. Clear the stale lock left by the cloud session.
if [[ -f .git/index.lock ]]; then
  rm -f .git/index.lock
  echo "removed stale .git/index.lock"
fi

# 2. Initialise if needed (idempotent).
if [[ ! -d .git ]]; then
  git init -q
  echo "git init done"
fi

git config user.name  "David Newman"
git config user.email "david.newman@a8c.com"
git config core.fileMode false

# 3. Two commits, deliberately: the pre-M14 state must exist in history so the
#    historical artifacts' recorded source hashes remain verifiable against the
#    tree that actually produced them. See the note on upstream drift in
#    M14_PROGRESS.md — this commit is what makes that recoverable.
if ! git rev-parse --verify -q HEAD >/dev/null; then
  # Stash the M14 changes, commit the original tree, then restore them.
  M14_FILES=(
    src/flockkalman/provenance.py
    src/flockkalman/simulation.py
    src/flockkalman/adversarial_trust_suite.py
    src/flockkalman/closed_loop_trust.py
    src/flockkalman/closed_loop_trust_suite.py
    .gitignore
  )
  TMP="$(mktemp -d)"
  for f in "${M14_FILES[@]}"; do
    [[ -f "$f" ]] && { mkdir -p "$TMP/$(dirname "$f")"; cp "$f" "$TMP/$f"; }
  done

  # Restore pre-M14 versions where we can (provenance.py and _m14/ are new, so
  # they simply get excluded from the first commit).
  git add -A -- . ':!src/flockkalman/provenance.py' ':!_m14'
  git reset -q -- src/flockkalman/provenance.py _m14 2>/dev/null || true
  git commit -q -m "Initial import: platform v0.19.0 as reviewed (pre-M14)

Imported from the working tree with no history. Recorded artifact hashes in
results/*/suite_config.json refer to THIS tree. Nine milestones have no protocol
file and results/ was previously gitignored; both are recorded as-is rather than
tidied, per the program's verdict semantics.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PQBCJenReG3YDBWsS1bZaL"
  echo "commit 1: pre-M14 import"

  for f in "${M14_FILES[@]}"; do
    [[ -f "$TMP/$f" ]] && cp "$TMP/$f" "$f"
  done
  rm -rf "$TMP"
fi

# 4. Commit the M14 remediation.
git add -A
if ! git diff --cached --quiet; then
  git commit -q -m "M14.2-14.4: environment provenance and replay-gate hardening

- new flockkalman.provenance: environment fingerprinting/comparison, a
  tolerance-based scenario fingerprint (v2-quantized), and three-way replay
  verification (VERIFIED / REPLAY-ENV-MISMATCH / MISMATCH).
- scenario_fingerprint and closed_loop_fingerprint accept an algorithm; the
  default stays v1-raw-bytes so historical artifacts keep verifying bit-exactly.
- M10A and M10A.5 record and compare python/numpy, and no longer collapse an
  environment mismatch into INVALID.
- M14.4: simulation.py, config.py and provenance.py added to the frozen source
  sets whose replay gates depend on them.

Verified: 59/59 tests pass; v1 byte-identical to the pre-M14 implementation
across 22 config/seed pairs; v2 absorbs single- and all-element ULP changes while
rejecting a 1e-6 change; statistics reanalyse byte-identically.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PQBCJenReG3YDBWsS1bZaL"
  echo "commit 2: M14 remediation"
fi

echo
git --no-pager log --oneline
echo
echo "tracked files: $(git ls-files | wc -l | tr -d ' ')"
echo "repo size:     $(du -sh .git | cut -f1)"
echo
echo "NEXT (needs network + your credentials):"
echo "  gh repo create flocking-kalman-platform --private --source=. --push"
echo "  # or: git remote add origin <url> && git push -u origin main"
echo
echo "M14.1 gate requires a third-party host with observable dates."
echo "Until pushed, the gate is NOT met and M15 must not run."
