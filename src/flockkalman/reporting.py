"""Dependency-free SVG reports for quick research inspection."""

from __future__ import annotations

from collections import defaultdict
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .config import ExperimentConfig

if TYPE_CHECKING:
    from .metrics import StepRecord


COLORS = {
    "independent_kf": "#4C78A8",
    "consensus_kf": "#59A14F",
    "flocking_only": "#F28E2B",
    "flocking_kf_no_momentum": "#76B7B2",
    "flocking_fixed_momentum": "#B279A2",
    "flocking_adaptive_momentum": "#E15759",
    "flocking_guarded_momentum": "#2F6B4F",
    "flocking_robust_multiflock": "#7B4FA3",
    "flocking_robust_temporal": "#1F8A70",
    "flocking_robust_mixture": "#C76D2E",
    "flocking_robust_defer": "#6B7280",
    "flocking_robust_active_no_investigation": "#D97706",
    "flocking_robust_active": "#B91C5C",
}


def _label(name: str) -> str:
    return name.replace("_", " ").title().replace(" Kf", " KF")


def write_comparison_svg(summary: list[dict[str, object]], path: Path) -> None:
    panels = [
        ("position_rmse_mean", "Team position RMSE", "lower is better"),
        ("coverage95_rate_mean", "95% coverage rate", "target: 0.95"),
        ("information_gain_mean", "Information gain", "higher is better"),
        ("spatial_diversity_mean", "Spatial diversity", "mean pairwise distance"),
        ("recovery_steps_mean", "Recovery after change", "steps; lower is better"),
        ("bytes_sent_mean", "Communication", "bytes; lower is better"),
    ]
    width, height = 1240, 1100
    panel_width, panel_height = 560, 300
    row_spacing = min(25.0, 215.0 / max(len(summary) - 1, 1))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FAFBFC"/>',
        '<text x="50" y="48" font-family="sans-serif" font-size="28" font-weight="700" fill="#17324D">Flocking–Kalman experiment comparison</text>',
        '<text x="50" y="76" font-family="sans-serif" font-size="14" fill="#526170">Means across configured random seeds</text>',
    ]
    for panel_index, (metric, title, subtitle) in enumerate(panels):
        column, row = panel_index % 2, panel_index // 2
        x0 = 50 + column * 600
        y0 = 105 + row * 315
        parts.append(
            f'<rect x="{x0}" y="{y0}" width="{panel_width}" height="{panel_height}" rx="8" fill="#FFFFFF" stroke="#D7DEE7"/>'
        )
        parts.append(
            f'<text x="{x0 + 18}" y="{y0 + 28}" font-family="sans-serif" font-size="17" font-weight="700" fill="#17324D">{escape(title)}</text>'
        )
        parts.append(
            f'<text x="{x0 + 18}" y="{y0 + 49}" font-family="sans-serif" font-size="12" fill="#6A7785">{escape(subtitle)}</text>'
        )
        values = [float(row_data[metric] or 0.0) for row_data in summary]
        maximum = max(values, default=1.0) or 1.0
        for item_index, (row_data, value) in enumerate(zip(summary, values)):
            algorithm = str(row_data["algorithm"])
            y = y0 + 66 + item_index * row_spacing
            bar_width = 235.0 * value / maximum
            parts.append(
                f'<text x="{x0 + 18}" y="{y + 14}" font-family="sans-serif" font-size="11" fill="#334455">{escape(_label(algorithm))}</text>'
            )
            parts.append(
                f'<rect x="{x0 + 205}" y="{y}" width="{bar_width:.2f}" height="17" rx="3" fill="{COLORS.get(algorithm, "#777777")}"/>'
            )
            rendered = f"{value:,.3f}" if abs(value) < 1000 else f"{value:,.0f}"
            parts.append(
                f'<text x="{x0 + 535}" y="{y + 14}" text-anchor="end" font-family="monospace" font-size="11" fill="#334455">{rendered}</text>'
            )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_error_timeseries_svg(
    config: ExperimentConfig, records: list["StepRecord"], path: Path
) -> None:
    grouped: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        grouped[record.algorithm][record.step].append(record.team_position_error)
    width, height = 1100, 660
    left, top, chart_width, chart_height = 80, 90, 950, 440
    maximum = max((record.team_position_error for record in records), default=1.0) * 1.05
    maximum = max(maximum, 1.0)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FAFBFC"/>',
        '<text x="80" y="45" font-family="sans-serif" font-size="27" font-weight="700" fill="#17324D">Team position error through time</text>',
        f'<rect x="{left}" y="{top}" width="{chart_width}" height="{chart_height}" fill="#FFFFFF" stroke="#CBD4DE"/>',
    ]
    for fraction in np.linspace(0.0, 1.0, 6):
        y = top + chart_height * (1.0 - fraction)
        value = maximum * fraction
        parts.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + chart_width}" y2="{y:.2f}" stroke="#E7EBF0"/>'
        )
        parts.append(
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-family="sans-serif" font-size="11" fill="#607080">{value:.1f}</text>'
        )
    change_x = left + chart_width * config.change_step / max(config.steps - 1, 1)
    parts.append(
        f'<line x1="{change_x:.2f}" y1="{top}" x2="{change_x:.2f}" y2="{top + chart_height}" stroke="#202A35" stroke-dasharray="6 5"/>'
    )
    parts.append(
        f'<text x="{change_x + 6:.2f}" y="{top + 18}" font-family="sans-serif" font-size="12" fill="#202A35">target manoeuvre</text>'
    )
    for algorithm, by_step in grouped.items():
        points = []
        for step in sorted(by_step):
            value = float(np.mean(by_step[step]))
            x = left + chart_width * step / max(config.steps - 1, 1)
            y = top + chart_height * (1.0 - value / maximum)
            points.append(f"{x:.2f},{y:.2f}")
        parts.append(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{COLORS.get(algorithm, "#777777")}" stroke-width="2.4" opacity="0.9"/>'
        )
    legend_x, legend_y = 80, 565
    for index, algorithm in enumerate(grouped):
        x = legend_x + (index % 4) * 250
        y = legend_y + (index // 4) * 24
        parts.append(
            f'<line x1="{x}" y1="{y}" x2="{x + 25}" y2="{y}" stroke="{COLORS.get(algorithm, "#777777")}" stroke-width="4"/>'
        )
        parts.append(
            f'<text x="{x + 31}" y="{y + 4}" font-family="sans-serif" font-size="10" fill="#334455">{escape(_label(algorithm))}</text>'
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
