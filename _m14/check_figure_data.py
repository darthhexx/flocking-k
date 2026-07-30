"""M14.6 gate check: figures must be sourced from results/, not transcribed.

Two assertions, and a coverage report that is deliberately honest about what is
still authored by hand.

A. The generator imports the data layer and reads the results tree at all.
B. Regenerating the figures from the artifacts reproduces the numbers currently in
   the committed SVGs. If a figure has drifted from its artifact, this fails.

The coverage report lists every remaining numeric literal in a text position, so
"zero hardcoded numeric literals" is a measured claim rather than an aspiration.
Geometry (coordinates, font sizes, axis tick labels) is excluded: those are layout,
not evidence, and pretending otherwise would make the check meaningless.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "generate_paper_figures.py"
FIGURES = ROOT / "figures"

# Numbers that are layout rather than evidence.
AXIS_LABEL = re.compile(r"^[0-9]+(\.[0-9]+)?m?$")
PRIOR_LABEL = re.compile(r"^Mode [A-Z] \(Prior [0-9.]+\)$")


def check_a_imports_data_layer() -> bool:
    source = GENERATOR.read_text(encoding="utf-8")
    imports = "from flockkalman.figure_data import" in source
    reads_root = "PROJECT_ROOT" in source
    loads = "load_milestones(" in source or "load_milestone(" in source
    metrics = "metric_from_scenario_summary(" in source
    ok = imports and reads_root and loads and metrics
    print(f"[A] generator imports the data layer: {'PASS' if ok else 'FAIL'}")
    print(f"    figure_data import={imports} project_root={reads_root} "
          f"load={loads} metric={metrics}")
    return ok


def check_b_regeneration_is_stable() -> bool:
    """Regenerate and confirm the SVGs are byte-identical.

    Stability under regeneration is the property that matters: it proves the
    committed figures are what the current artifacts produce, so a stale figure
    cannot survive a re-run unnoticed.
    """
    before = {p.name: p.read_bytes() for p in sorted(FIGURES.glob("*.svg"))}
    if not before:
        print("[B] no figures to compare: FAIL")
        return False
    result = subprocess.run(
        [sys.executable, str(GENERATOR)], cwd=ROOT, capture_output=True
    )
    if result.returncode != 0:
        print("[B] generator failed to run: FAIL")
        print("   ", result.stderr.decode()[-400:])
        return False
    after = {p.name: p.read_bytes() for p in sorted(FIGURES.glob("*.svg"))}
    drifted = [name for name in before if before[name] != after.get(name)]
    ok = not drifted
    print(f"[B] figures byte-stable under regeneration: {'PASS' if ok else 'FAIL'}")
    for name in drifted:
        print(f"    DRIFTED: {name} -- committed figure does not match artifacts")
    return ok


#: Values that were hardcoded before M14.6 and must now be absent from the
#: generator source. Each is a datum the artifacts own. Presence of any of these as
#: a literal means that figure element is still transcribed.
FORBIDDEN_LITERALS = [
    # figure 2: verdicts and gate counts
    '"12/12 gates passed', '"18/18 gates passed', '"13/13 powered gates',
    '"PARTIAL-GO", "#FFA502"', '"NO-GO", "#FF4757"', '"GO", "#2ED573"',
    "policy/representation headroom",   # the inverted M9A.5 reading
    # figure 3: M9B effect sizes
    "by 0.574 vs", "0.682 lower movement",
    # figure 4: UTIAS replay metrics
    "2.163m", "0.541m", "0.514m", "NEES 2.84", "NEES 1.93",
]


def check_c_no_forbidden_literals() -> bool:
    """The specific data values that used to be hardcoded must be gone."""
    source = GENERATOR.read_text(encoding="utf-8")
    found = [literal for literal in FORBIDDEN_LITERALS if literal in source]
    ok = not found
    print(f"[C] previously-hardcoded data values absent from generator: "
          f"{'PASS' if ok else 'FAIL'}")
    for literal in found:
        print(f"    STILL PRESENT: {literal!r}")
    return ok


def report_remaining_literals() -> int:
    """Report numeric text in the SVGs that is NOT sourced from an artifact.

    Scans the generator rather than the output, because the output cannot
    distinguish a derived number from a transcribed one -- both render as digits.
    Anything inside an f-string interpolation is derived; a bare digit in a text
    node is authored.
    """
    source = GENERATOR.read_text(encoding="utf-8")
    authored: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped.startswith(("'", 'f\'', '"')):
            continue
        # Only text nodes carry evidence; attributes are geometry.
        for match in re.finditer(r">([^<>]*?[0-9][^<>]*?)<", stripped):
            text = match.group(1)
            if "{" in text:          # interpolated -> derived
                continue
            if AXIS_LABEL.match(text.strip()):
                continue
            authored.append(text.strip())

    print()
    print("COVERAGE -- numeric figure text still authored in the generator:")
    if not authored:
        print("  none")
    for text in authored:
        print(f"  {text[:96]}")
    print()
    print("NOTE: figure 1 is a system-model diagram; its constants (rho=0.72,")
    print("  Mahalanobis 9.21, C_defer=0.75, support margin 0.15, probe cap 8)")
    print("  document the frozen model rather than any run's outcome. They would be")
    print("  better read from config.py, and that is recorded here as a known gap")
    print("  rather than counted as sourced.")
    return len(authored)


if __name__ == "__main__":
    results = [
        check_a_imports_data_layer(),
        check_b_regeneration_is_stable(),
        check_c_no_forbidden_literals(),
    ]
    count = report_remaining_literals()
    print()
    print(f"OVERALL: {'PASS' if all(results) else 'FAIL'} "
          f"({count} authored numeric strings remaining)")
    raise SystemExit(0 if all(results) else 1)
