# M14 progress record — provenance and environment remediation

**Status: PARTIAL. Verdict not yet recorded; M14 is not `GO`, so M15 must not run.**

Work done in the cloud session of 29–30 July 2026. Everything below was executed
and verified against a real copy of the platform (Python 3.11.15 / NumPy 2.4.4;
recorded artifacts declare 3.11.11 / 2.4.6), not merely written.

---

## Gate status

| Gate | Status | Note |
|---|---|---|
| 14.1 version control | **BLOCKED** | `git init` ran; `add`/`commit` cannot. See §1. Handoff script provided. |
| 14.2 environment pinned | **PARTIAL** | Implemented and verified for M10A, M10A.5. Four suites remain. |
| 14.3 replay gate hardened | **PARTIAL** | Implemented and verified for M10A, M10A.5. Four suites remain. |
| 14.4 frozen set complete | **PARTIAL** | Done for M10A, M10A.5. Four remain. Has a side effect — see §3. |
| 14.5 firewall mechanical | **NOT STARTED** | |
| 14.6 figures wired | **NOT STARTED** | |

Remaining suites carrying a `replay` gate: `admission_suite` (M9A.7),
`integration_suite` (M9C), `missing_evidence_suite` (M9A.6),
`topology_suite` (M9A).

---

## 1. M14.1 is blocked from the cloud, and left a stale lock

The cloud session reaches the folder through a file bridge that **cannot unlink
files**. Git removes `.git/index.lock` after every index operation, so:

```
fatal: Unable to create '.../.git/index.lock': File exists.
```

`git init` itself succeeded, which is why a stale `.git/index.lock` is now sitting
in the repo. Nothing else was written to `.git`.

**Fix:** run `_m14/m14_init_git.sh` on your Mac. It clears the lock, makes two
commits (pre-M14 import, then the remediation — the split matters, see §3), and
prints the `gh repo create` line. Pushing needs your credentials, so the gate
stays unmet until you do that step.

`.gitignore` was rewritten on disk: `results/` is now **tracked** (86 MB, 344
files — it is the evidence base, and a provenance repo that ignores it defeats
itself), and `external_data/` is **ignored** (301 MB of third-party UTIAS data,
provenance already preserved via recorded source and canonical hashes).

---

## 2. What 14.2–14.4 actually do

New module `src/flockkalman/provenance.py`:

* `environment_fingerprint()` / `compare_environment()` — record and *compare*
  python/numpy/platform/machine. Previously these were written into
  `suite_config.json` and never read; all 47 `decision.json` files carry no
  environment fields at all.
* `digest_arrays(..., algorithm=)` — two fingerprint algorithms.
  `v1-raw-bytes` is the legacy bit-exact one; `v2-quantized` hashes integers and
  bool exactly and quantizes floats to a 1e-9 absolute quantum.
* `verify_replay(...) -> ReplayVerification` — three-way outcome:
  `VERIFIED` / `REPLAY-ENV-MISMATCH` / `MISMATCH`, with only `MISMATCH` blocking.

**The default stays v1.** Flipping it would invalidate every historical artifact
in the record, which is exactly the kind of silent repair the verdict semantics
exist to prevent. New runs pass `v2` and record
`fingerprint_algorithm` in `suite_config.json`.

### The defect, reproduced and then fixed

```
before:  M10A  M10A-GO  ->  M10A-INVALID          (no diagnostic)
after:   M10A  M10A-GO  ->  M10A-REPLAY-ENV-MISMATCH
                            status        REPLAY-ENV-MISMATCH
                            exact         7740/8250
                            blocks        false
                            adjudicable   false
                            env diffs     numpy 2.4.6 -> 2.4.4
                                          python 3.11.11 -> 3.11.15
```

M10B, which never flipped, still returns `M10B-GO` with zero failing gates.

### Verification performed

`_m14/check_fingerprint.py` — all PASS:

* v1 is byte-identical to the pre-M14 implementation across 22 config/seed pairs;
* v2 absorbs a single-ULP change and an all-element ULP change;
* v2 rejects a 1e-6 change;
* v1 *is* fragile to a single ULP (control, proving the diagnosis);
* NaN/±inf remain distinguishable; the int64 overflow guard raises.

`_m14/check_replay_gate.py` — all PASS:

* statistics (`paired_effects.csv`, `scenario_summary.csv`) reanalyse
  byte-identically;
* a mismatch with a **matching** environment still blocks;
* a **v2** mismatch blocks even when the environment differs.

`pytest`: **59 passed, 21 subtests passed**, before and after.

### Known limitation — do not let a referee find this first

Once the environment differs, a **v1** artifact cannot distinguish last-bit churn
from a *deliberately altered* fingerprint. Both present as "recorded !=
recomputed", and SHA-256 is not invertible. `check_replay_gate.py` check B
demonstrates this explicitly: a tampered row reports `REPLAY-ENV-MISMATCH`, not
`MISMATCH`.

This is a real weakening of the integrity guarantee for the historical artifacts.
The mitigation is migration, not argument — v2 artifacts are environment-invariant
by construction, so for them the excuse branch is unreachable. Any claim resting
on a pre-M14 artifact should say so.

---

## 3. Unplanned consequence of M14.4 — needs your decision

Widening the frozen sets to include `simulation.py`, `config.py` and
`provenance.py` means the chain of custody now *correctly* detects that M14
modified those modules. Concretely, M10A.5's reanalysis reports:

```
failing gates -> ['replay', 'upstream_frozen']
verdict       -> M10A5-INVALID
```

`upstream_frozen` fails because it recomputes M10A's candidate source hash from
the current tree and compares it against what M10A's `suite_config.json` recorded
before M14. **This is the gate working, not breaking.** But it means pre-M14
held-out artifacts cannot be re-certified against the post-M14 tree.

Three options, and this is a genuine judgement call:

1. **Accept and document.** Historical artifacts are certified only against the
   pre-M14 tree, which the first git commit preserves. Cheapest; requires §1 to
   be done first, and makes M14.1 load-bearing rather than hygienic.
2. **Record a `legacy_source_sha256`** alongside the new one, pinning the pre-M14
   hashes so verification is explicit about which tree it refers to. Moderate
   work, no re-runs, and arguably the most honest artifact.
3. **Re-run the affected suites** under M14 code. Cleanest, expensive, and
   partially redundant with M21's integrated confirmatory run.

My recommendation is **2 then 1**: pin the legacy hashes so nothing is ambiguous,
document that historical certification refers to the pre-M14 tree, and let M21
supply the clean post-M14 evidence. Re-running now spends the seeds M21 needs.

---

## 4. Next actions

1. Run `_m14/m14_init_git.sh` locally, then push. **M14.1 is unmet until pushed,
   and M14 gates all downstream milestones.**
2. Decide §3.
3. Wire the four remaining suites (mechanical; the pattern is established in
   `adversarial_trust_suite.py` — signature, gate, verdict branch, both call
   sites, frozen set, `fingerprint_algorithm`).
4. M14.5 firewall, M14.6 figures.
5. Record `results/milestone14_remediation/decision.json` with the verdict.

Files changed on your disk: `src/flockkalman/{provenance,simulation,
adversarial_trust_suite,closed_loop_trust,closed_loop_trust_suite}.py`,
`.gitignore`, and new `_m14/`.
