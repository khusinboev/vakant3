"""
Haftalik statistika uchun matplotlib grafik generatsiyasi.
matplotlib mavjud bo'lmasa None qaytaradi (text-only fallback).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Optional

from src.i18n import DEFAULT_LANG, t

try:
    import matplotlib

    matplotlib.use("Agg")  # Headless — GUI kerak emas
    import matplotlib.pyplot as plt

    _MATPLOTLIB_OK = True
except ImportError:
    _MATPLOTLIB_OK = False


@dataclass
class WeeklyStats:
    week_label: str              # "26-may – 1-iyun 2026"
    new_users: int
    total_users: int
    pro_users: int
    total_saves: int
    new_resumes: int             # builder_ready events this week
    total_vacancies: int         # from API or 0
    avg_salary: int              # so'm

    top_specs: list[str] = field(default_factory=list)
    top_specs_counts: list[int] = field(default_factory=list)

    top_regions: list[str] = field(default_factory=list)
    top_region_counts: list[int] = field(default_factory=list)

    # 4-haftalik trend (eski → yangi)
    weeks_labels: list[str] = field(default_factory=list)
    users_per_week: list[int] = field(default_factory=list)
    avg_salary_per_week: list[int] = field(default_factory=list)

    channel: str = ""            # "@bandlikuz" etc.


def _short_label(name: str, max_len: int = 14) -> str:
    """Uzun nomlarni qisqartiradi."""
    return name[:max_len] + "…" if len(name) > max_len else name


def generate_weekly_stats_chart(
    stats: WeeklyStats, lang: str = DEFAULT_LANG
) -> Optional[bytes]:
    """PNG bytes qaytaradi yoki matplotlib yo'q bo'lsa None."""
    if not _MATPLOTLIB_OK:
        return None

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.patch.set_facecolor("#F8FAFC")
    fig.suptitle(
        t(lang, "chart.title", label=stats.week_label),
        fontsize=14,
        fontweight="bold",
        color="#1E293B",
    )

    COLORS = {
        "blue": "#0EA5E9",
        "green": "#10B981",
        "violet": "#8B5CF6",
        "amber": "#F59E0B",
        "bg": "#F8FAFC",
        "grid": "#E2E8F0",
        "text": "#64748B",
    }

    # ── [0,0] Top sohalar — gorizontal bar ────────────────────────────────────
    ax1 = axes[0, 0]
    if stats.top_specs:
        labels = [_short_label(s) for s in stats.top_specs[:5]]
        values = stats.top_specs_counts[:5]
        bars = ax1.barh(labels[::-1], values[::-1], color=COLORS["blue"], height=0.6)
        ax1.bar_label(bars, fmt="%d", padding=3, fontsize=8, color=COLORS["text"])
        ax1.set_xlim(0, max(values) * 1.25 if values else 1)
    ax1.set_facecolor(COLORS["bg"])
    ax1.set_title(t(lang, "chart.top_specs"), fontsize=10, color=COLORS["text"], pad=8)
    ax1.tick_params(axis="both", colors=COLORS["text"], labelsize=8)
    ax1.xaxis.set_visible(False)
    for spine in ax1.spines.values():
        spine.set_visible(False)

    # ── [0,1] Top hududlar — vertikal bar ────────────────────────────────────
    ax2 = axes[0, 1]
    if stats.top_regions:
        labels2 = [_short_label(r) for r in stats.top_regions[:5]]
        values2 = stats.top_region_counts[:5]
        bars2 = ax2.bar(labels2, values2, color=COLORS["green"], width=0.6)
        ax2.bar_label(bars2, fmt="%d", padding=3, fontsize=8, color=COLORS["text"])
        ax2.set_ylim(0, max(values2) * 1.25 if values2 else 1)
        ax2.tick_params(axis="x", rotation=25, labelsize=8)
    ax2.set_facecolor(COLORS["bg"])
    ax2.set_title(t(lang, "chart.top_regions"), fontsize=10, color=COLORS["text"], pad=8)
    ax2.tick_params(axis="y", colors=COLORS["text"], labelsize=8)
    ax2.yaxis.set_visible(False)
    for spine in ax2.spines.values():
        spine.set_visible(False)

    # ── [1,0] Foydalanuvchi o'sishi — line chart ──────────────────────────────
    ax3 = axes[1, 0]
    if stats.users_per_week and stats.weeks_labels:
        ax3.plot(
            stats.weeks_labels,
            stats.users_per_week,
            marker="o",
            color=COLORS["violet"],
            linewidth=2,
            markersize=6,
        )
        ax3.fill_between(
            stats.weeks_labels,
            stats.users_per_week,
            alpha=0.12,
            color=COLORS["violet"],
        )
        for i, (x, y) in enumerate(zip(stats.weeks_labels, stats.users_per_week)):
            ax3.annotate(str(y), (x, y), textcoords="offset points",
                         xytext=(0, 7), ha="center", fontsize=8, color=COLORS["text"])
    ax3.set_facecolor(COLORS["bg"])
    ax3.set_title(t(lang, "chart.new_users"), fontsize=10, color=COLORS["text"], pad=8)
    ax3.tick_params(axis="both", colors=COLORS["text"], labelsize=8)
    ax3.yaxis.set_visible(False)
    for spine in ax3.spines.values():
        spine.set_color(COLORS["grid"])

    # ── [1,1] O'rtacha maosh trend — line chart ───────────────────────────────
    ax4 = axes[1, 1]
    has_salary_trend = bool(stats.avg_salary_per_week and stats.weeks_labels)
    if has_salary_trend:
        ax4.plot(
            stats.weeks_labels,
            stats.avg_salary_per_week,
            marker="s",
            color=COLORS["amber"],
            linewidth=2,
            markersize=6,
        )
        ax4.fill_between(
            stats.weeks_labels,
            stats.avg_salary_per_week,
            alpha=0.12,
            color=COLORS["amber"],
        )
        for i, (x, y) in enumerate(zip(stats.weeks_labels, stats.avg_salary_per_week)):
            ax4.annotate(f"{y/1_000_000:.1f}M", (x, y), textcoords="offset points",
                         xytext=(0, 7), ha="center", fontsize=8, color=COLORS["text"])
    ax4.set_facecolor(COLORS["bg"])
    ax4.tick_params(axis="both", colors=COLORS["text"], labelsize=8)
    ax4.yaxis.set_visible(False)
    if has_salary_trend:
        ax4.set_title(t(lang, "chart.avg_salary"), fontsize=10, color=COLORS["text"], pad=8)
        for spine in ax4.spines.values():
            spine.set_color(COLORS["grid"])
    else:
        # Ishonchli haftalik maosh tarixi yo'q — bo'sh panelni ko'rsatmaymiz.
        ax4.axis("off")

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    buf = BytesIO()
    plt.savefig(buf, format="PNG", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()
