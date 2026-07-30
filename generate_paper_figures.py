"""
generate_paper_figures.py

Generates four publication-grade vector SVG figures for the paper:
'A Falsification-First Research Program for Flocking-Coupled Distributed State Estimation'

Figures generated in figures/:
1. figure1_system_architecture.svg
2. figure2_milestone_flowchart.svg
3. figure3_competing_view_geometry.svg
4. figure4_external_replay_utias.svg
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from flockkalman.figure_data import (  # noqa: E402
    FigureDataError,
    load_milestone,
    load_milestones,
    metric_from_scenario_summary,
)

OUTPUT_DIR = Path("figures")
PROJECT_ROOT = Path(__file__).resolve().parent

# M14.6: verdict colours are keyed by the *derived* verdict class, not chosen per
# box by hand, so a verdict that changes on re-analysis cannot keep its old colour.
VERDICT_COLORS = {
    "promoted": "#2ED573",
    "rejected": "#FF4757",
    "partial": "#FFA502",
    "invalid": "#70A1FF",
    "qualified": "#B47EE5",
    "diagnostic": "#A4B0BE",
    "other": "#A4B0BE",
}
OUTPUT_DIR.mkdir(exist_ok=True)

# -----------------------------------------------------------------------------
# FIGURE 1: SYSTEM ARCHITECTURE BLOCK DIAGRAM
# -----------------------------------------------------------------------------
def generate_figure1_svg(path: Path) -> None:
    width, height = 1200, 780
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '  <defs>',
        '    <linearGradient id="targetGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#FF6B6B"/>',
        '      <stop offset="100%" stop-color="#EE5253"/>',
        '    </linearGradient>',
        '    <linearGradient id="kfGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#48DBFB"/>',
        '      <stop offset="100%" stop-color="#0ABDE3"/>',
        '    </linearGradient>',
        '    <linearGradient id="flockGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#1DD1A1"/>',
        '      <stop offset="100%" stop-color="#10AC84"/>',
        '    </linearGradient>',
        '    <linearGradient id="trustGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#FF9F43"/>',
        '      <stop offset="100%" stop-color="#EE5253"/>',
        '    </linearGradient>',
        '    <linearGradient id="policyGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#5F27CD"/>',
        '      <stop offset="100%" stop-color="#341F97"/>',
        '    </linearGradient>',
        '    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '      <path d="M 0 0 L 10 5 L 0 10 z" fill="#485460"/>',
        '    </marker>',
        '    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">',
        '      <feDropShadow dx="2" dy="4" stdDeviation="4" flood-opacity="0.1"/>',
        '    </filter>',
        '  </defs>',
        '  <rect width="100%" height="100%" fill="#F8F9FA"/>',
        '  ',
        '  <!-- Title Banner -->',
        '  <text x="600" y="42" font-family="system-ui, sans-serif" font-size="24" font-weight="800" text-anchor="middle" fill="#1E272C">Figure 1: Flocking-Coupled Distributed State Estimation Architecture (v0.19)</text>',
        '  <text x="600" y="66" font-family="system-ui, sans-serif" font-size="14" text-anchor="middle" fill="#576574">Closed-loop interaction between physical sensing motion, split-admission hypothesis fusion, adversarial trust, and truth-blind output policy</text>',

        '  <!-- SUB-BLOCK 1: PHYSICAL ENVIRONMENT & TARGET -->',
        '  <rect x="40" y="100" width="260" height="220" rx="12" fill="#FFFFFF" stroke="#FF6B6B" stroke-width="2" filter="url(#shadow)"/>',
        '  <rect x="40" y="100" width="260" height="36" rx="12" fill="url(#targetGrad)"/>',
        '  <text x="170" y="124" font-family="system-ui, sans-serif" font-size="15" font-weight="700" text-anchor="middle" fill="#FFFFFF">Physical Environment</text>',
        '  <text x="55" y="160" font-family="system-ui, sans-serif" font-size="13" font-weight="600" fill="#2D3436">• Target State: x = [p_x, p_y, v_x, v_y]ᵀ</text>',
        '  <text x="55" y="185" font-family="system-ui, sans-serif" font-size="13" font-weight="600" fill="#2D3436">• Range-Dependent Noise:</text>',
        '  <text x="75" y="208" font-family="monospace" font-size="12" fill="#D63031">R_i(d) = σ₀²(1 + α d²)</text>',
        '  <text x="55" y="235" font-family="system-ui, sans-serif" font-size="13" font-weight="600" fill="#2D3436">• Mobile Sensors: i ∈ {1...N}</text>',
        '  <text x="55" y="260" font-family="system-ui, sans-serif" font-size="13" font-weight="600" fill="#2D3436">• Dynamic Topology: G_t = (V_t, E_t)</text>',
        '  <text x="55" y="285" font-family="system-ui, sans-serif" font-size="12" fill="#636E72">(Agent outages, partitions, rejoin)</text>',

        '  <!-- SUB-BLOCK 2: LOCAL ESTIMATION & SPLIT ADMISSION -->',
        '  <rect x="340" y="100" width="480" height="220" rx="12" fill="#FFFFFF" stroke="#0ABDE3" stroke-width="2" filter="url(#shadow)"/>',
        '  <rect x="340" y="100" width="480" height="36" rx="12" fill="url(#kfGrad)"/>',
        '  <text x="580" y="124" font-family="system-ui, sans-serif" font-size="15" font-weight="700" text-anchor="middle" fill="#FFFFFF">Local Estimation &amp; Split Admission Channels</text>',
        '  ',
        '  <!-- Channel 1: Raw Measurements -->',
        '  <rect x="360" y="150" width="210" height="150" rx="8" fill="#E0F7FA" stroke="#00ACC1" stroke-width="1.5"/>',
        '  <text x="465" y="172" font-family="system-ui, sans-serif" font-size="13" font-weight="700" text-anchor="middle" fill="#006064">Channel A: Raw Measurements</text>',
        '  <text x="372" y="195" font-family="system-ui, sans-serif" font-size="12" fill="#004D40">• Direct sensor observations</text>',
        '  <text x="372" y="215" font-family="system-ui, sans-serif" font-size="12" fill="#004D40">• Source-local robust trust</text>',
        '  <text x="372" y="235" font-family="system-ui, sans-serif" font-size="12" fill="#004D40">• Covariance flooring active</text>',
        '  <text x="372" y="255" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#00796B">Permissive Admission</text>',

        '  <!-- Channel 2: Recursive Belief Fusion -->',
        '  <rect x="595" y="150" width="210" height="150" rx="8" fill="#F3E5F5" stroke="#8E24AA" stroke-width="1.5"/>',
        '  <text x="700" y="172" font-family="system-ui, sans-serif" font-size="13" font-weight="700" text-anchor="middle" fill="#4A148C">Channel B: Belief Fusion</text>',
        '  <text x="607" y="195" font-family="system-ui, sans-serif" font-size="12" fill="#4A148C">• Peer posteriors {x̂_j, P_j}</text>',
        '  <text x="607" y="215" font-family="system-ui, sans-serif" font-size="12" fill="#4A148C">• Timestamp propagation</text>',
        '  <text x="607" y="235" font-family="system-ui, sans-serif" font-size="12" fill="#4A148C">• Full lifecycle admission</text>',
        '  <text x="607" y="255" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#7B1FA2">Strict Lifecycle Gated</text>',

        '  <!-- SUB-BLOCK 3: HYPOTHESIS FLOCKS & ADVERSARIAL TRUST -->',
        '  <rect x="340" y="360" width="480" height="240" rx="12" fill="#FFFFFF" stroke="#10AC84" stroke-width="2" filter="url(#shadow)"/>',
        '  <rect x="340" y="360" width="480" height="36" rx="12" fill="url(#flockGrad)"/>',
        '  <text x="580" y="384" font-family="system-ui, sans-serif" font-size="15" font-weight="700" text-anchor="middle" fill="#FFFFFF">Hypothesis Flocks &amp; Composed Trust Defense</text>',
        '  ',
        '  <text x="360" y="420" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#10AC84">Covariance Intersection (CI) &amp; Clustering:</text>',
        '  <text x="375" y="442" font-family="monospace" font-size="12" fill="#2D3436">Mahalanobis gating: d² ≤ 9.21 (Subspace position)</text>',
        '  <text x="375" y="462" font-family="system-ui, sans-serif" font-size="12" fill="#2D3436">• Compatible nodes form explicit hypothesis flocks F_k</text>',
        '  <text x="375" y="482" font-family="system-ui, sans-serif" font-size="12" fill="#2D3436">• Preserves alternative modes (displaced minorities quarantined)</text>',

        '  <rect x="360" y="500" width="440" height="80" rx="8" fill="#FFF0F0" stroke="#EE5253" stroke-width="1.5"/>',
        '  <text x="580" y="522" font-family="system-ui, sans-serif" font-size="13" font-weight="700" text-anchor="middle" fill="#C0392B">Composed Adversarial Trust Layer (M10A / M10A.5)</text>',
        '  <text x="375" y="544" font-family="system-ui, sans-serif" font-size="12" fill="#900C3F">1. Assignment-corrected disagreement (median innovation removed)</text>',
        '  <text x="375" y="564" font-family="system-ui, sans-serif" font-size="12" fill="#900C3F">2. Ramp-rate evidence  |  3. Precision budget (≤0.35x raw cap)</text>',

        '  <!-- SUB-BLOCK 4: TRUTH-BLIND OUTPUT POLICY -->',
        '  <rect x="860" y="100" width="300" height="500" rx="12" fill="#FFFFFF" stroke="#341F97" stroke-width="2" filter="url(#shadow)"/>',
        '  <rect x="860" y="100" width="300" height="36" rx="12" fill="url(#policyGrad)"/>',
        '  <text x="1010" y="124" font-family="system-ui, sans-serif" font-size="15" font-weight="700" text-anchor="middle" fill="#FFFFFF">Truth-Blind Output Policy</text>',
        '  ',
        '  <text x="880" y="160" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#341F97">Support Accounting &amp; Actions:</text>',
        '  <text x="880" y="182" font-family="system-ui, sans-serif" font-size="12" fill="#2D3436">• Group nearby Gaussians (&lt; 2.0u)</text>',
        '  <text x="880" y="202" font-family="system-ui, sans-serif" font-size="12" fill="#2D3436">• Support margin ≥ 0.15 required</text>',

        '  <rect x="880" y="220" width="260" height="50" rx="6" fill="#E8F5E9" stroke="#4CAF50" stroke-width="1"/>',
        '  <text x="1010" y="240" font-family="system-ui, sans-serif" font-size="13" font-weight="700" text-anchor="middle" fill="#2E7D32">Action: SELECT</text>',
        '  <text x="1010" y="258" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle" fill="#1B5E20">Clear dominant hypothesis mode</text>',

        '  <rect x="880" y="280" width="260" height="50" rx="6" fill="#E3F2FD" stroke="#2196F3" stroke-width="1"/>',
        '  <text x="1010" y="300" font-family="system-ui, sans-serif" font-size="13" font-weight="700" text-anchor="middle" fill="#1565C0">Action: MIXTURE</text>',
        '  <text x="1010" y="318" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle" fill="#0D47A1">Moment-matched combined posterior</text>',

        '  <rect x="880" y="340" width="260" height="65" rx="6" fill="#FFF3E0" stroke="#FF9800" stroke-width="1"/>',
        '  <text x="1010" y="360" font-family="system-ui, sans-serif" font-size="13" font-weight="700" text-anchor="middle" fill="#E65100">Action: INVESTIGATE</text>',
        '  <text x="1010" y="378" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle" fill="#E65100">Bounded probing (≤8 cycles)</text>',
        '  <text x="1010" y="394" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle" fill="#E65100">Decentralized 2-step VOI motion</text>',

        '  <rect x="880" y="415" width="260" height="50" rx="6" fill="#FFEBEE" stroke="#F44336" stroke-width="1"/>',
        '  <text x="1010" y="435" font-family="system-ui, sans-serif" font-size="13" font-weight="700" text-anchor="middle" fill="#C62828">Action: DEFER (Abstain)</text>',
        '  <text x="1010" y="453" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle" fill="#B71C1C">Declared cost C_defer = 0.75</text>',

        '  <text x="880" y="490" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#576574">Evaluation Loss Model:</text>',
        '  <text x="880" y="510" font-family="monospace" font-size="11" fill="#2D3436">Loss = ||x̂ - x_true|| + C_action</text>',
        '  <text x="880" y="530" font-family="system-ui, sans-serif" font-size="11" fill="#D63031">(Truth isolated; used only in scoring)</text>',

        '  <!-- MOTION FEEDBACK LOOPS & ARROWS -->',
        '  <!-- Arrow: Environment to Estimation -->',
        '  <path d="M 300 210 L 338 210" stroke="#485460" stroke-width="2.5" marker-end="url(#arrow)"/>',
        '  <text x="319" y="200" font-family="system-ui, sans-serif" font-size="11" font-weight="700" text-anchor="middle" fill="#485460">z_i</text>',

        '  <!-- Arrow: Local Estimation to Flock Fusion -->',
        '  <path d="M 580 320 L 580 358" stroke="#485460" stroke-width="2.5" marker-end="url(#arrow)"/>',

        '  <!-- Arrow: Hypothesis Flocks to Policy -->',
        '  <path d="M 820 450 L 858 450" stroke="#485460" stroke-width="2.5" marker-end="url(#arrow)"/>',

        '  <!-- Feedback Arrow: Motion / Active Probing back to Environment -->',
        '  <path d="M 1010 470 L 1010 680 L 170 680 L 170 322" fill="none" stroke="#10AC84" stroke-width="3" stroke-dasharray="6,4" marker-end="url(#arrow)"/>',
        '  <text x="590" y="670" font-family="system-ui, sans-serif" font-size="14" font-weight="800" text-anchor="middle" fill="#10AC84">Recurrent Motion Command: v(t+1) = clip[ ρ v(t) + (1-ρ) u_flock(t) ]</text>',
        '  <text x="590" y="695" font-family="system-ui, sans-serif" font-size="12" text-anchor="middle" fill="#576574">(Fixed investigative momentum ρ = 0.72 alters future sensor distances d_i and measurement variance R_i)</text>',

        '</svg>'
    ]
    path.write_text("\n".join(parts), encoding="utf-8")


# -----------------------------------------------------------------------------
# FIGURE 2: MILESTONE PROGRESSION FLOWCHART
# -----------------------------------------------------------------------------
def generate_figure2_svg(path: Path) -> None:
    width, height = 1200, 850
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '  <defs>',
        '    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '      <path d="M 0 0 L 10 5 L 0 10 z" fill="#2D3436"/>',
        '    </marker>',
        '    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">',
        '      <feDropShadow dx="2" dy="3" stdDeviation="3" flood-opacity="0.12"/>',
        '    </filter>',
        '  </defs>',
        '  <rect width="100%" height="100%" fill="#FAF9F6"/>',
        '  ',
        '  <!-- Title -->',
        '  <text x="600" y="40" font-family="system-ui, sans-serif" font-size="24" font-weight="800" text-anchor="middle" fill="#1E272C">Figure 2: Preregistered Falsification Milestone Trajectory (M4–M13.3)</text>',
        '  <text x="600" y="64" font-family="system-ui, sans-serif" font-size="14" text-anchor="middle" fill="#576574">Hashed protocols, held-out seeds, firewalled diagnostics, and recorded verdicts (GO, NO-GO, PARTIAL-GO, DEVELOPMENT-FAIL, INVALID)</text>',

        '  <!-- LEGEND -->',
        '  <rect x="50" y="85" width="1100" height="40" rx="6" fill="#FFFFFF" stroke="#DFE4EA"/>',
        '  <rect x="70" y="97" width="16" height="16" rx="3" fill="#2ED573"/>',
        '  <text x="94" y="110" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#2D3436">GO (Promoted)</text>',

        '  <rect x="250" y="97" width="16" height="16" rx="3" fill="#FF4757"/>',
        '  <text x="274" y="110" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#2D3436">NO-GO / FAIL (Rejected)</text>',

        '  <rect x="460" y="97" width="16" height="16" rx="3" fill="#FFA502"/>',
        '  <text x="484" y="110" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#2D3436">PARTIAL-GO (Retained/Refused)</text>',

        '  <rect x="720" y="97" width="16" height="16" rx="3" fill="#70A1FF"/>',
        '  <text x="744" y="110" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#2D3436">INVALID (Protocol Boundary)</text>',

        '  <rect x="940" y="97" width="16" height="16" rx="3" fill="#A4B0BE"/>',
        '  <text x="964" y="110" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#2D3436">Diagnostic Firewall</text>',

        '  <!-- MILESTONE BOXES LAYOUT (4 Columns x 5 Rows) -->',
    ]

    # M14.6: (x, y, title, artifact, qualitative prose). The verdict, the colour
    # and the "N/N gates passed" prefix are all read from the artifact. Only the
    # prose remains authored, and it carries no numbers -- see
    # _m14/check_figure_data.py, which enforces that.
    layout = [
        # Col 0: Motion & Fusion
        (50, 150, "M4: Direct Adaptive Motion", "decision_suite",
         "NIS adaptive recurrence worse than fixed; fixed recurrence retained."),
        (50, 280, "M5: Guarded Adaptive Motion", "milestone5_heldout",
         "Corroborated guards safe, but statistically tied with fixed recurrence."),
        (50, 410, "M6: Robust Multi-Flock Fusion", "milestone6_heldout",
         "CI inside hypothesis flocks handles bias and Byzantine sources."),
        (50, 540, "M7: Truth-Blind Output Policy", "milestone7_heldout",
         "Active select/investigate/defer beats every declared baseline."),

        # Col 1: Realism & Active Sensing
        (340, 150, "M8: Realism Ladder Transfer", "milestone8_heldout",
         "Dynamic topology breached margin; investigation gave no decision gain."),
        (340, 280, "M8.1: Endogenous Ambiguity", "milestone8_1_heldout",
         "Engineered positive control: lateral motion resolves binary ambiguity."),
        (340, 410, "M8.2: Mechanism Sweep", "momentum_mechanism_training",
         "Training sweep did not support the spatial-diversity mechanism."),
        (340, 540, "M9B: Static VOI Allocation", "milestone9b_heldout",
         "Receding-horizon VOI beats round-robin where views compete."),

        # Col 2: Topology Resilience & Admission
        (630, 150, "M9A: Topology Evidence Ledger", "milestone9a_heldout",
         "Repaired the NEES calibration pathology; transfer gate failed."),
        (630, 280, "M9A.5: Oracle Floor Diagnosis", "milestone9a5_oracle_floor",
         "Firewalled nested reference; conclusion read directly from the artifact."),
        (630, 410, "M9A.6: Assignment Posterior", "milestone9a6_heldout",
         "Exposed a rare admission-censored missingness tail."),
        (630, 540, "M9A.7: Split Evidence Admission", "milestone9a7_heldout",
         "Split raw/belief admission channels repair the tail risk."),

        # Col 3: Trust, Decentralization & Validation
        (920, 150, "M10A: Composed Trust", "milestone10a_heldout",
         "Causal trust layer collapses attack loss with no false alerts."),
        (920, 280, "M10B: Decentralized Allocation", "milestone10b_heldout",
         "Per-agent asynchronous ownership passes noninferiority."),
        (920, 410, "M11.1: External MR.CLaM Replay", "milestone11_1_heldout",
         "Canonicalized replay after M11 was recorded INVALID on a timestamp jump."),
        (920, 540, "M12: Measured Acceleration", "milestone12_development",
         "Acceleration state strictly worse on real data; filter left frozen."),
    ]

    records = load_milestones([item[3] for item in layout], PROJECT_ROOT)

    milestones = []
    for x, y, title, artifact, prose in layout:
        record = records[artifact]
        gate_prefix = (
            f"{record.gate_summary}. " if record.gates_total else ""
        )
        milestones.append(
            (x, y, title, record.verdict,
             VERDICT_COLORS[record.verdict_class], gate_prefix + prose)
        )

    for x, y, title, verdict, color, desc in milestones:
        parts.append(f'  <g filter="url(#shadow)">')
        parts.append(f'    <rect x="{x}" y="{y}" width="240" height="105" rx="8" fill="#FFFFFF" stroke="{color}" stroke-width="2"/>')
        parts.append(f'    <rect x="{x}" y="{y}" width="240" height="26" rx="8" fill="{color}"/>')
        parts.append(f'    <text x="{x+120}" y="{y+18}" font-family="system-ui, sans-serif" font-size="12" font-weight="800" text-anchor="middle" fill="#FFFFFF">{title}</text>')
        parts.append(f'    <text x="{x+10}" y="{y+45}" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="{color}">Verdict: {verdict}</text>')
        
        words = desc.split()
        line1, line2 = "", ""
        for w in words:
            if len(line1 + " " + w) < 32:
                line1 += (" " if line1 else "") + w
            else:
                line2 += (" " if line2 else "") + w
        parts.append(f'    <text x="{x+10}" y="{y+66}" font-family="system-ui, sans-serif" font-size="10" fill="#2D3436">{line1}</text>')
        if line2:
            parts.append(f'    <text x="{x+10}" y="{y+82}" font-family="system-ui, sans-serif" font-size="10" fill="#2D3436">{line2}</text>')
        parts.append(f'  </g>')

    # Final HIL Box across bottom
    parts.append(f'  <g filter="url(#shadow)">')
    parts.append(f'    <rect x="50" y="680" width="1110" height="110" rx="10" fill="#FFFFFF" stroke="#2ED573" stroke-width="3"/>')
    parts.append(f'    <rect x="50" y="680" width="1110" height="32" rx="10" fill="#2ED573"/>')
    parts.append(f'    <text x="605" y="702" font-family="system-ui, sans-serif" font-size="15" font-weight="800" text-anchor="middle" fill="#FFFFFF">M13.1 Hardware-in-the-Loop Screen &amp; Physical Transition (HIL-PILOT-READY)</text>')
    parts.append(f'    <text x="70" y="732" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#2D3436">• M13.0 Wire &amp; Scorer Boundary: Truth fields structurally isolated; hash-chained evidence ledgers verified.</text>')
    parts.append(f'    <text x="70" y="752" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#2D3436">• M13.1 Independent HIL Screen: 6,000 paired trials; 12/12 gates passed; decentralized loss within -0.0036 of centralized.</text>')
    parts.append(f'    <text x="70" y="772" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#C0392B">• M13.2 / M13.3 Physical Pilot &amp; Holdout: Preregistered 320-run randomized plan sealed; awaiting physical robot bundles.</text>')
    parts.append(f'  </g>')

    # Connecting Arrows
    arrows = [
        (170, 255, 170, 280), (170, 385, 170, 410), (170, 515, 170, 540),
        (290, 202, 340, 202), (460, 255, 460, 280), (460, 515, 460, 540),
        (580, 592, 630, 202), (750, 255, 750, 280), (750, 385, 750, 410), (750, 515, 750, 540),
        (870, 592, 920, 202), (1040, 255, 1040, 280), (1040, 385, 1040, 410), (1040, 515, 1040, 540),
        (1040, 645, 1040, 680)
    ]
    for x1, y1, x2, y2 in arrows:
        parts.append(f'  <path d="M {x1} {y1} L {x2} {y2}" stroke="#2D3436" stroke-width="2" marker-end="url(#arrow)"/>')

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


# -----------------------------------------------------------------------------
# FIGURE 3: COMPETING-VIEW TASK GEOMETRY
# -----------------------------------------------------------------------------
def generate_figure3_svg(path: Path) -> None:
    # M14.6: the two M9B effect sizes are read from the artifact's overall scope.
    def m9b_effect(metric: str) -> float:
        return metric_from_scenario_summary(
            "milestone9b_heldout",
            PROJECT_ROOT,
            column="improvement_mean",
            where={
                "scope": "overall",
                "candidate": "receding_horizon_voi",
                "baseline": "round_robin",
                "metric": metric,
            },
            filename="paired_effects.csv",
        )

    voi_loss_improvement = m9b_effect("total_decision_loss")
    voi_movement_improvement = m9b_effect("movement_cost")

    width, height = 1100, 600
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '  <defs>',
        '    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '      <path d="M 0 0 L 10 5 L 0 10 z" fill="#2D3436"/>',
        '    </marker>',
        '    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">',
        '      <feDropShadow dx="2" dy="3" stdDeviation="3" flood-opacity="0.1"/>',
        '    </filter>',
        '  </defs>',
        '  <rect width="100%" height="100%" fill="#FAF9F6"/>',
        '  ',
        '  <!-- Title -->',
        '  <text x="550" y="38" font-family="system-ui, sans-serif" font-size="22" font-weight="800" text-anchor="middle" fill="#1E272C">Figure 3: Task Geometry &amp; Value-of-Information (VOI) Active Sensing Assays</text>',
        '  <text x="550" y="60" font-family="system-ui, sans-serif" font-size="13" text-anchor="middle" fill="#576574">Contrasting non-competing ambiguity (M8.1) vs competing-view viewpoints under asymmetric movement costs (M9B)</text>',

        '  <!-- PANEL A: M8.1 Binary Ambiguity Assay -->',
        '  <rect x="40" y="90" width="490" height="470" rx="10" fill="#FFFFFF" stroke="#DCDDE1" stroke-width="2" filter="url(#shadow)"/>',
        '  <text x="285" y="120" font-family="system-ui, sans-serif" font-size="16" font-weight="800" text-anchor="middle" fill="#2F3640">(A) M8.1 Binary Range-Only Assay</text>',
        '  <text x="285" y="140" font-family="system-ui, sans-serif" font-size="12" text-anchor="middle" fill="#718093">Passive sensing on bisector is non-discriminable; lateral motion resolves modes</text>',

        '  <!-- Coordinate Grid Panel A -->',
        '  <g transform="translate(40, 150)">',
        '    <line x1="245" y1="30" x2="245" y2="350" stroke="#718093" stroke-width="2" stroke-dasharray="4,4"/>',
        '    <text x="245" y="25" font-family="system-ui, sans-serif" font-size="11" font-weight="700" text-anchor="middle" fill="#718093">Initial Bisector (x = 0)</text>',

        '    <circle cx="95" cy="190" r="14" fill="#EE5253"/>',
        '    <text x="95" y="195" font-family="system-ui, sans-serif" font-size="11" font-weight="800" text-anchor="middle" fill="#FFFFFF">θ₁</text>',
        '    <text x="95" y="220" font-family="system-ui, sans-serif" font-size="12" font-weight="700" text-anchor="middle" fill="#EE5253">Mode 1 (-5, 0)</text>',

        '    <circle cx="395" cy="190" r="14" fill="#EE5253"/>',
        '    <text x="395" y="195" font-family="system-ui, sans-serif" font-size="11" font-weight="800" text-anchor="middle" fill="#FFFFFF">θ₂</text>',
        '    <text x="395" y="220" font-family="system-ui, sans-serif" font-size="12" font-weight="700" text-anchor="middle" fill="#EE5253">Mode 2 (+5, 0)</text>',

        '    <circle cx="245" cy="190" r="8" fill="#0ABDE3"/>',
        '    <circle cx="245" cy="220" r="8" fill="#0ABDE3"/>',
        '    <circle cx="245" cy="160" r="8" fill="#0ABDE3"/>',
        '    <text x="245" y="140" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle" fill="#0ABDE3">Sensors at t=0</text>',

        '    <path d="M 95 190 A 150 150 0 0 0 245 190" fill="none" stroke="#EE5253" stroke-width="1.5" stroke-dasharray="3,3"/>',
        '    <path d="M 395 190 A 150 150 0 0 1 245 190" fill="none" stroke="#EE5253" stroke-width="1.5" stroke-dasharray="3,3"/>',
        '    <text x="245" y="255" font-family="system-ui, sans-serif" font-size="11" font-style="italic" text-anchor="middle" fill="#222">Identical Range d₁ = d₂</text>',

        '    <path d="M 245 190 L 170 190" stroke="#10AC84" stroke-width="3" marker-end="url(#arrow)"/>',
        '    <path d="M 245 190 L 320 190" stroke="#10AC84" stroke-width="3" marker-end="url(#arrow)"/>',
        '    <text x="245" y="310" font-family="system-ui, sans-serif" font-size="12" font-weight="700" text-anchor="middle" fill="#10AC84">Lateral Motion Resolves Ambiguity</text>',
        '    <text x="245" y="330" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle" fill="#576574">Discriminability ∝ Lateral Displacement</text>',
        '  </g>',

        '  <!-- PANEL B: M9B Competing-View Assay -->',
        '  <rect x="570" y="90" width="490" height="470" rx="10" fill="#FFFFFF" stroke="#DCDDE1" stroke-width="2" filter="url(#shadow)"/>',
        '  <text x="815" y="120" font-family="system-ui, sans-serif" font-size="16" font-weight="800" text-anchor="middle" fill="#2F3640">(B) M9B Competing-View Circle Assay</text>',
        '  <text x="815" y="140" font-family="system-ui, sans-serif" font-size="12" text-anchor="middle" fill="#718093">Nonmyopic VOI minimizes (Deferral + Wrong Selection + Movement Cost)</text>',

        '  <g transform="translate(570, 150)">',
        '    <circle cx="245" cy="180" r="120" fill="none" stroke="#C8D6E5" stroke-width="2"/>',
        '    ',
        '    <circle cx="245" cy="60" r="12" fill="#5F27CD"/>',
        '    <text x="245" y="42" font-family="system-ui, sans-serif" font-size="11" font-weight="700" text-anchor="middle" fill="#5F27CD">Mode A (Prior 0.6)</text>',

        '    <circle cx="365" cy="180" r="12" fill="#5F27CD"/>',
        '    <text x="420" y="184" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#5F27CD">Mode B (Prior 0.3)</text>',

        '    <circle cx="125" cy="180" r="12" fill="#5F27CD"/>',
        '    <text x="70" y="184" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#5F27CD">Mode C (Prior 0.1)</text>',

        '    <path d="M 245 180 L 125 180" stroke="#FF4757" stroke-width="2" stroke-dasharray="4,4"/>',
        '    <text x="175" y="170" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#FF4757">High Motion Cost</text>',

        '    <path d="M 245 180 L 245 72" stroke="#10AC84" stroke-width="3" marker-end="url(#arrow)"/>',
        '    <text x="260" y="125" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#10AC84">Optimal 2-Step VOI Probe</text>',

        '    <circle cx="245" cy="180" r="10" fill="#FF9F43"/>',
        '    <text x="245" y="205" font-family="system-ui, sans-serif" font-size="11" font-weight="700" text-anchor="middle" fill="#FF9F43">Sensor Agent</text>',

        '    <rect x="30" y="275" width="430" height="75" rx="6" fill="#F1F2F6" stroke="#CED6E0"/>',
        '    <text x="245" y="295" font-family="system-ui, sans-serif" font-size="12" font-weight="800" text-anchor="middle" fill="#2F3640">Key Empirical Finding (Sec 5.4 / 6.1):</text>',
        f'    <text x="245" y="315" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle" fill="#333">• 2-Step VOI reduced movement-inclusive loss by {voi_loss_improvement:.3f} vs. Round-Robin.</text>',
        f'    <text x="245" y="333" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle" fill="#333">• Gain came from {voi_movement_improvement:.3f} lower movement cost, NOT higher decision accuracy.</text>',
        '  </g>',

        '</svg>'
    ]
    path.write_text("\n".join(parts), encoding="utf-8")


# -----------------------------------------------------------------------------
# FIGURE 4: EXTERNAL REPLAY (UTIAS MR.CLAM DATASET 6)
# -----------------------------------------------------------------------------
def generate_figure4_svg(path: Path) -> None:
    # M14.6: every number below is read from results/milestone11_1_heldout.
    # metric_from_scenario_summary raises if a value or arm is missing, so this
    # figure fails to render rather than silently keeping a stale literal.
    def arm(column: str, arm_name: str) -> float:
        return metric_from_scenario_summary(
            "milestone11_1_heldout",
            PROJECT_ROOT,
            column=column,
            where={"arm": arm_name},
            filename="arm_summary.csv",
        )

    rmse_odometry = arm("position_rmse_mean", "odometry_only")
    rmse_unbounded = arm("position_rmse_mean", "all_landmarks")
    rmse_bounded = arm("position_rmse_mean", "bounded_two")
    nees_unbounded = arm("mean_nees_mean", "all_landmarks")
    nees_bounded = arm("mean_nees_mean", "bounded_two")
    p95_unbounded = arm("p95_nees_mean", "all_landmarks")
    p95_bounded = arm("p95_nees_mean", "bounded_two")

    width, height = 1100, 620
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '  <defs>',
        '    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">',
        '      <feDropShadow dx="2" dy="3" stdDeviation="3" flood-opacity="0.1"/>',
        '    </filter>',
        '  </defs>',
        '  <rect width="100%" height="100%" fill="#FAF9F6"/>',
        '  ',
        '  <!-- Title -->',
        '  <text x="550" y="38" font-family="system-ui, sans-serif" font-size="22" font-weight="800" text-anchor="middle" fill="#1E272C">Figure 4: Real-Data External Replay Results (UTIAS MR.CLaM Dataset 6)</text>',
        '  <text x="550" y="60" font-family="system-ui, sans-serif" font-size="13" text-anchor="middle" fill="#576574">Causal replay of simulator-derived bounded Kalman filter vs. Odometry and Unbounded All-Landmark EKF</text>',

        '  <!-- PANEL 1: RMSE OVER TIME -->',
        '  <rect x="40" y="90" width="490" height="480" rx="10" fill="#FFFFFF" stroke="#DCDDE1" stroke-width="2" filter="url(#shadow)"/>',
        '  <text x="285" y="120" font-family="system-ui, sans-serif" font-size="16" font-weight="800" text-anchor="middle" fill="#2F3640">(A) Robot Localization RMSE (meters)</text>',

        '  <g transform="translate(40, 140)">',
        '    <line x1="50" y1="20" x2="50" y2="350" stroke="#718093" stroke-width="1.5"/>',
        '    <line x1="50" y1="350" x2="450" y2="350" stroke="#718093" stroke-width="1.5"/>',
        '    <text x="45" y="25" font-family="system-ui, sans-serif" font-size="11" text-anchor="end" fill="#718093">3.0m</text>',
        '    <text x="45" y="135" font-family="system-ui, sans-serif" font-size="11" text-anchor="end" fill="#718093">2.0m</text>',
        '    <text x="45" y="245" font-family="system-ui, sans-serif" font-size="11" text-anchor="end" fill="#718093">1.0m</text>',
        '    <text x="45" y="355" font-family="system-ui, sans-serif" font-size="11" text-anchor="end" fill="#718093">0.0m</text>',
        '    <text x="250" y="385" font-family="system-ui, sans-serif" font-size="12" font-weight="700" text-anchor="middle" fill="#718093">Replay Window Time (seconds)</text>',

        '    <line x1="50" y1="130" x2="450" y2="130" stroke="#F1F2F6" stroke-width="1"/>',
        '    <line x1="50" y1="240" x2="450" y2="240" stroke="#F1F2F6" stroke-width="1"/>',

        '    <path d="M 50 330 Q 150 250 250 150 T 450 40" fill="none" stroke="#FF4757" stroke-width="3"/>',
        f'    <text x="410" y="30" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#FF4757">Odometry ({rmse_odometry:.3f}m)</text>',

        '    <path d="M 50 330 Q 150 300 250 290 T 450 280" fill="none" stroke="#FFA502" stroke-width="2.5" stroke-dasharray="5,3"/>',
        f'    <text x="340" y="265" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#FFA502">Unbounded EKF ({rmse_unbounded:.3f}m)</text>',

        '    <path d="M 50 330 Q 150 305 250 298 T 450 292" fill="none" stroke="#2ED573" stroke-width="3.5"/>',
        f'    <text x="310" y="315" font-family="system-ui, sans-serif" font-size="11" font-weight="800" fill="#2ED573">Bounded KF ({rmse_bounded:.3f}m)</text>',
        '  </g>',

        '  <!-- PANEL 2: NEES CALIBRATION & OVERCONFIDENCE -->',
        '  <rect x="570" y="90" width="490" height="480" rx="10" fill="#FFFFFF" stroke="#DCDDE1" stroke-width="2" filter="url(#shadow)"/>',
        '  <text x="815" y="120" font-family="system-ui, sans-serif" font-size="16" font-weight="800" text-anchor="middle" fill="#2F3640">(B) Filter Uncertainty Calibration (NEES)</text>',

        '  <g transform="translate(570, 140)">',
        '    <line x1="50" y1="20" x2="50" y2="350" stroke="#718093" stroke-width="1.5"/>',
        '    <line x1="50" y1="350" x2="450" y2="350" stroke="#718093" stroke-width="1.5"/>',

        '    <rect x="50" y="280" width="400" height="40" fill="#E8F8F5" stroke="#2ECC71" stroke-width="1" stroke-dasharray="3,3"/>',
        '    <text x="250" y="305" font-family="system-ui, sans-serif" font-size="11" font-weight="700" text-anchor="middle" fill="#27AE60">Nominal Calibration Band (NEES ≈ 1.0–2.0)</text>',

        '    <path d="M 50 310 Q 150 240 250 120 T 450 80" fill="none" stroke="#FFA502" stroke-width="2.5" stroke-dasharray="5,3"/>',
        f'    <text x="320" y="70" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#FFA502">Unbounded EKF (NEES {nees_unbounded:.2f}, P95={p95_unbounded:.1f})</text>',

        '    <path d="M 50 310 Q 150 295 250 290 T 450 288" fill="none" stroke="#2ED573" stroke-width="3.5"/>',
        f'    <text x="260" y="270" font-family="system-ui, sans-serif" font-size="11" font-weight="800" fill="#2ED573">Bounded KF (NEES {nees_bounded:.2f}, P95={p95_bounded:.2f})</text>',

        '    <rect x="30" y="375" width="430" height="45" rx="6" fill="#F1F2F6" stroke="#CED6E0"/>',
        '    <text x="245" y="395" font-family="system-ui, sans-serif" font-size="11" font-weight="700" text-anchor="middle" fill="#2F3640">Simulator-derived conservatism transfers to real logs (M11.1):</text>',
        '    <text x="245" y="410" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle" fill="#333">Bounded update cap prevents overconfidence while improving accuracy.</text>',
        '  </g>',

        '</svg>'
    ]
    path.write_text("\n".join(parts), encoding="utf-8")


def main():
    generate_figure1_svg(OUTPUT_DIR / "figure1_system_architecture.svg")
    generate_figure2_svg(OUTPUT_DIR / "figure2_milestone_flowchart.svg")
    generate_figure3_svg(OUTPUT_DIR / "figure3_competing_view_geometry.svg")
    generate_figure4_svg(OUTPUT_DIR / "figure4_external_replay_utias.svg")
    print(f"Successfully generated 4 publication SVG figures in '{OUTPUT_DIR.resolve()}/'")

if __name__ == "__main__":
    main()
