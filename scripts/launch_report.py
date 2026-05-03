"""Inaugural TAPE-100 report generator.

Run:
    python -m scripts.launch_report

Output:
    reports/inaugural.pdf      — 15-page PDF, designed to look defensible
                                 on a TechCrunch screenshot
    reports/inaugural.json     — the raw findings + tables, picked up by
                                 the web version at /report/inaugural

The script is generic over data shape — every section degrades gracefully
when a particular signal isn't present (e.g. no benchmark data → "Quality
unrated for the full TAPE-100" gets called out instead of pretending).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import psycopg
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports"
PDF_PATH = OUT_DIR / "inaugural.pdf"
JSON_PATH = OUT_DIR / "inaugural.json"
# A second JSON copy under apps/web/public so the Next.js report page
# can fetch it as a static asset without touching the filesystem.
WEB_JSON_PATH = ROOT / "apps" / "web" / "public" / "launch-report.json"

# Brand color — same deep electric blue used in the web app.
BRAND = colors.HexColor("#1652F0")
INK = colors.HexColor("#0b0c10")
MUTED = colors.HexColor("#6b7280")
HAIRLINE = colors.HexColor("#e5e7eb")
GAIN = colors.HexColor("#16a34a")
LOSS = colors.HexColor("#dc2626")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s :: %(message)s")
log = logging.getLogger("launch_report")


# ---------------------------------------------------------------- data


@dataclass
class Tape100Row:
    rank: int
    slug: str
    name: str
    score: float | None
    adoption: float | None
    quality: float | None
    momentum: float | None
    community: float | None
    discovered_via: str
    github_repo: str | None
    discovered_at: datetime


@dataclass
class Findings:
    surprising_leader: dict[str, Any] | None
    notable_decline: dict[str, Any] | None
    concentration: dict[str, Any] | None


@dataclass
class ReportData:
    generated_at: datetime
    tape100: list[Tape100Row]
    composite_history: list[tuple[datetime, float]]
    score_distribution: list[float]
    discovered_via_breakdown: dict[str, int]
    findings: Findings


def load_data(dsn: str) -> ReportData:
    """Pull every section from one Postgres connection — cheap roundtrip."""
    with psycopg.connect(dsn) as conn:
        tape = _load_tape100(conn)
        composite = _load_composite_history(conn)
        scores = _load_score_distribution(conn)
        breakdown = _load_discovered_via_breakdown(conn)
        findings = _compute_findings(conn, tape)
    return ReportData(
        generated_at=datetime.now(UTC),
        tape100=tape,
        composite_history=composite,
        score_distribution=scores,
        discovered_via_breakdown=breakdown,
        findings=findings,
    )


def _load_tape100(conn: psycopg.Connection) -> list[Tape100Row]:
    sql = """
        SELECT a.slug, a.name, a.discovered_via, a.github_repo, a.discovered_at,
               cs.agent_score, cs.adoption, cs.quality, cs.momentum, cs.community
        FROM agents a
        LEFT JOIN current_scores cs ON cs.agent_id = a.id
        WHERE a.eligibility_status = 'admitted'
        ORDER BY cs.agent_score DESC NULLS LAST
        LIMIT 100
    """
    out: list[Tape100Row] = []
    with conn.cursor() as cur:
        cur.execute(sql)
        for i, row in enumerate(cur.fetchall(), start=1):
            (
                slug,
                name,
                via,
                repo,
                disc_at,
                score,
                adoption,
                quality,
                momentum,
                community,
            ) = row
            out.append(
                Tape100Row(
                    rank=i,
                    slug=slug,
                    name=name,
                    score=float(score) if score is not None else None,
                    adoption=float(adoption) if adoption is not None else None,
                    quality=float(quality) if quality is not None else None,
                    momentum=float(momentum) if momentum is not None else None,
                    community=float(community) if community is not None else None,
                    discovered_via=via,
                    github_repo=repo,
                    discovered_at=disc_at,
                )
            )
    return out


def _load_composite_history(
    conn: psycopg.Connection,
) -> list[tuple[datetime, float]]:
    """30 days of TAPE-100 composite snapshots."""
    sql = """
        SELECT s.captured_at, s.composite_value
        FROM index_snapshots s
        JOIN indexes i ON i.id = s.index_id
        WHERE i.slug = 'tape-100' AND s.captured_at > now() - interval '30 days'
        ORDER BY s.captured_at ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        return [(r[0], float(r[1])) for r in cur.fetchall()]


def _load_score_distribution(conn: psycopg.Connection) -> list[float]:
    """Latest score per admitted agent — used for the histogram."""
    sql = """
        SELECT cs.agent_score
        FROM agents a
        JOIN current_scores cs ON cs.agent_id = a.id
        WHERE a.eligibility_status = 'admitted'
          AND cs.agent_score IS NOT NULL
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        return [float(r[0]) for r in cur.fetchall()]


def _load_discovered_via_breakdown(conn: psycopg.Connection) -> dict[str, int]:
    sql = """
        SELECT discovered_via, count(*)
        FROM agents
        WHERE eligibility_status = 'admitted'
        GROUP BY discovered_via
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        return {via: int(n) for via, n in cur.fetchall()}


def _compute_findings(
    conn: psycopg.Connection, tape: list[Tape100Row]
) -> Findings:
    if not tape:
        return Findings(None, None, None)

    # 1. Surprising leader: highest-ranked agent that was admitted in the last 30 days.
    cutoff = datetime.now(UTC) - timedelta(days=30)
    surprising = next(
        (r for r in tape if r.discovered_at and r.discovered_at >= cutoff),
        None,
    )
    surprising_dict = (
        {
            "rank": surprising.rank,
            "slug": surprising.slug,
            "name": surprising.name,
            "score": surprising.score,
            "discovered_via": surprising.discovered_via,
            "discovered_at": surprising.discovered_at.isoformat()
            if surprising.discovered_at
            else None,
        }
        if surprising
        else None
    )

    # 2. Notable decline: biggest negative agent_score delta over the last 7 days
    #    among the admitted set.
    sql = """
        WITH base AS (
            SELECT s.agent_id,
                   FIRST_VALUE(s.agent_score) OVER (
                       PARTITION BY s.agent_id ORDER BY s.computed_at DESC
                       ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                   ) AS now_score,
                   FIRST_VALUE(s.agent_score) OVER (
                       PARTITION BY s.agent_id ORDER BY s.computed_at ASC
                       ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                   ) AS then_score,
                   ROW_NUMBER() OVER (PARTITION BY s.agent_id ORDER BY s.computed_at DESC) AS rn
            FROM scores s
            WHERE s.computed_at >= now() - interval '7 days'
        )
        SELECT a.slug, a.name, b.then_score, b.now_score, b.now_score - b.then_score AS delta
        FROM base b
        JOIN agents a ON a.id = b.agent_id
        WHERE b.rn = 1 AND a.eligibility_status = 'admitted'
        ORDER BY delta ASC
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
    decline = (
        {
            "slug": row[0],
            "name": row[1],
            "then_score": float(row[2]) if row[2] is not None else None,
            "now_score": float(row[3]) if row[3] is not None else None,
            "delta": float(row[4]) if row[4] is not None else None,
        }
        if row and row[4] is not None and float(row[4]) < 0
        else None
    )

    # 3. Concentration: share of total score in the top 10.
    valid = [r.score for r in tape if r.score is not None]
    if valid:
        total = sum(valid)
        top10 = sum(valid[:10])
        concentration = {
            "top_10_share": (top10 / total) if total else None,
            "top_10_total": top10,
            "tape_total": total,
            "n_with_quality": sum(1 for r in tape if r.quality is not None),
            "n_unrated": sum(1 for r in tape if r.quality is None),
        }
    else:
        concentration = None

    return Findings(
        surprising_leader=surprising_dict,
        notable_decline=decline,
        concentration=concentration,
    )


# ---------------------------------------------------------------- charts


def render_composite_chart(history: list[tuple[datetime, float]]) -> bytes:
    fig, ax = plt.subplots(figsize=(7.5, 3.0), dpi=150)
    if history:
        xs = [t for t, _ in history]
        ys = [v for _, v in history]
        ax.plot(xs, ys, color="#1652F0", linewidth=1.6)
        ax.fill_between(xs, ys, min(ys), color="#1652F0", alpha=0.08)
        ax.set_ylim(min(ys) - 1, max(ys) + 1)
    else:
        ax.text(
            0.5,
            0.5,
            "No composite history yet",
            ha="center",
            va="center",
            color="#6b7280",
            transform=ax.transAxes,
        )
    ax.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e5e7eb")
    ax.spines["bottom"].set_color("#e5e7eb")
    ax.tick_params(colors="#6b7280", labelsize=8)
    ax.set_title(
        "TAPE-100 composite, 30 days",
        fontsize=11,
        loc="left",
        color="#0b0c10",
        pad=8,
    )
    fig.tight_layout()
    return _fig_bytes(fig)


def render_score_histogram(scores: list[float]) -> bytes:
    fig, ax = plt.subplots(figsize=(3.6, 2.6), dpi=150)
    if scores:
        ax.hist(scores, bins=20, color="#1652F0", alpha=0.85, edgecolor="white")
    else:
        ax.text(0.5, 0.5, "No scores", ha="center", va="center", color="#6b7280")
    ax.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e5e7eb")
    ax.spines["bottom"].set_color("#e5e7eb")
    ax.tick_params(colors="#6b7280", labelsize=8)
    ax.set_title(
        "AgentScore distribution",
        fontsize=10,
        loc="left",
        color="#0b0c10",
        pad=8,
    )
    fig.tight_layout()
    return _fig_bytes(fig)


def render_discovery_breakdown(by_via: dict[str, int]) -> bytes:
    fig, ax = plt.subplots(figsize=(3.6, 2.6), dpi=150)
    if by_via:
        labels = list(by_via.keys())
        vals = list(by_via.values())
        bars = ax.barh(labels, vals, color="#1652F0", alpha=0.85)
        ax.set_facecolor("white")
        ax.tick_params(colors="#6b7280", labelsize=8)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        ax.spines["left"].set_color("#e5e7eb")
        ax.spines["bottom"].set_color("#e5e7eb")
        for bar, v in zip(bars, vals, strict=True):
            ax.text(
                v + max(vals) * 0.02,
                bar.get_y() + bar.get_height() / 2,
                str(v),
                va="center",
                fontsize=8,
                color="#0b0c10",
            )
    ax.set_title(
        "Admissions by discovered_via",
        fontsize=10,
        loc="left",
        color="#0b0c10",
        pad=8,
    )
    fig.tight_layout()
    return _fig_bytes(fig)


def _fig_bytes(fig) -> bytes:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------- PDF


def build_pdf(data: ReportData, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="AgentTape — TAPE-100 Inaugural Report",
        author="AgentTape",
    )
    styles = _styles()
    story: list[Any] = []

    # 1. Cover
    story += _cover_section(data, styles)
    story.append(PageBreak())

    # 2. Methodology
    story += _methodology_section(styles)
    story.append(PageBreak())

    # 3. Three findings
    story += _findings_section(data, styles)
    story.append(PageBreak())

    # 4. Charts
    story += _charts_section(data, styles)
    story.append(PageBreak())

    # 5. TAPE-100 in full (paginated)
    story += _tape_table_section(data, styles)

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=32,
            leading=36,
            textColor=INK,
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=INK,
            spaceBefore=18,
            spaceAfter=8,
        ),
        "kicker": ParagraphStyle(
            "kicker",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=MUTED,
            letterSpacing=2,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=INK,
            spaceAfter=8,
        ),
        "stat": ParagraphStyle(
            "stat",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=42,
            leading=44,
            textColor=BRAND,
            alignment=TA_LEFT,
        ),
        "label": ParagraphStyle(
            "label",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
        ),
        "tablecell": ParagraphStyle(
            "tablecell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=INK,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def _cover_section(data: ReportData, styles) -> list[Any]:
    rows = data.tape100
    n_admitted = len(rows)
    top_score = rows[0].score if rows else None
    return [
        Spacer(1, 1.2 * inch),
        Paragraph("INAUGURAL · AGENTTAPE", styles["kicker"]),
        Paragraph("TAPE-100", styles["h1"]),
        Paragraph(
            "The first published edition of the AgentTape inaugural index. "
            "Every constituent on these pages was admitted by software, "
            "without a curated seed list, in the days leading up to this report.",
            styles["body"],
        ),
        Spacer(1, 0.6 * inch),
        Table(
            [
                [
                    Paragraph(f"{n_admitted}", styles["stat"]),
                    Paragraph(
                        f"{top_score:.1f}" if top_score is not None else "—",
                        styles["stat"],
                    ),
                ],
                [
                    Paragraph("constituents reporting", styles["label"]),
                    Paragraph("highest AgentScore", styles["label"]),
                ],
            ],
            colWidths=[3.4 * inch, 3.4 * inch],
            hAlign="LEFT",
        ),
        Spacer(1, 0.4 * inch),
        Paragraph(
            f"Generated {data.generated_at.strftime('%B %d, %Y · %H:%M UTC')}",
            styles["label"],
        ),
    ]


def _methodology_section(styles) -> list[Any]:
    return [
        Paragraph("METHODOLOGY", styles["kicker"]),
        Paragraph("How AgentTape works.", styles["h2"]),
        Paragraph(
            "We do not curate. The discovery service watches GitHub, Hugging Face, "
            "MCP registries, npm and PyPI, arXiv, and Hacker News on its own schedule "
            "and admits agents to the index without human intervention. This report "
            "is the first formal snapshot of what that system has surfaced.",
            styles["body"],
        ),
        Paragraph(
            "Once admitted, signals refresh on three independent tiers — fast (≈5 min "
            "for stars and HN mentions), medium (≈1 hour for forks, downloads, and "
            "package counts), and slow (daily for benchmark scores and citations). "
            "Scores recompute on a 60-second debounce per agent so the headline cannot "
            "be moved more than once a minute by any single signal.",
            styles["body"],
        ),
        Paragraph(
            "The AgentScore is a 0–100 headline backed by four pillars: Adoption "
            "(35%), Quality (30%, “Unrated” when no benchmark data is yet available), "
            "Momentum (20%), and Community (15%). Quality’s weight is redistributed "
            "pro-rata when an agent is unrated so a young project is not penalized "
            "for the absence of benchmark coverage. Three manipulation rules — star "
            "spike without contributor diversity, HF download surge without GitHub "
            "activity, coordinated HN posting — exclude implicated signals from that "
            "day’s score and shrink the agent’s manipulation_resistance.",
            styles["body"],
        ),
        Paragraph(
            "All inputs are reproducible. Every agent page exposes its raw signals "
            "as a CSV; every index publishes its rebalance log with diffs; the source "
            "of every methodology decision is in the public repository.",
            styles["body"],
        ),
    ]


def _findings_section(data: ReportData, styles) -> list[Any]:
    f = data.findings
    parts: list[Any] = [
        Paragraph("THREE FINDINGS", styles["kicker"]),
        Paragraph("What the index is telling us.", styles["h2"]),
    ]

    if f.surprising_leader:
        s = f.surprising_leader
        parts += [
            Paragraph("Finding 1 · A new entrant in the top quartile", styles["kicker"]),
            Paragraph(
                f"<b>{s['name']}</b> ranked #{s['rank']} this week with an AgentScore of "
                f"{s['score']:.1f}, despite being admitted only "
                f"{_relative(s.get('discovered_at'))}. It surfaced via "
                f"<i>{s['discovered_via'].replace('_', ' ')}</i>. The autonomous "
                f"discovery design exists for exactly this case — a project that is "
                f"already attracting real signal but had not yet been written up.",
                styles["body"],
            ),
            Spacer(1, 0.18 * inch),
        ]

    if f.notable_decline:
        d = f.notable_decline
        parts += [
            Paragraph("Finding 2 · The biggest 7-day drawdown", styles["kicker"]),
            Paragraph(
                f"<b>{d['name']}</b> shed {abs(d['delta']):.2f} points over the last "
                f"week, falling from {d['then_score']:.1f} to {d['now_score']:.1f}. "
                f"Drawdowns at this magnitude are usually the signal that a benchmark "
                f"result has come in below the agent's earlier momentum, or that "
                f"discovery flagged its star history for an integrity check.",
                styles["body"],
            ),
            Spacer(1, 0.18 * inch),
        ]
    else:
        parts += [
            Paragraph("Finding 2 · Drawdowns were small this week", styles["kicker"]),
            Paragraph(
                "No agent in the index lost more than a single AgentScore point over "
                "the past seven days. This is what a slow, broad market looks like — "
                "no benchmark releases have shifted the quality pillar; the adoption "
                "tier is dominated by mid-week star and download accumulation.",
                styles["body"],
            ),
            Spacer(1, 0.18 * inch),
        ]

    if f.concentration:
        c = f.concentration
        share = (c.get("top_10_share") or 0) * 100
        parts += [
            Paragraph("Finding 3 · Concentration in the top 10", styles["kicker"]),
            Paragraph(
                f"The top 10 constituents account for "
                f"<b>{share:.1f}%</b> of total AgentScore in TAPE-100 ("
                f"{c['top_10_total']:.1f} of {c['tape_total']:.1f}). Quality "
                f"coverage is uneven: {c['n_with_quality']} agents have at least "
                f"one benchmark result; the remaining {c['n_unrated']} are "
                "Unrated. The Quality pillar will become the dominant separator "
                "as benchmark coverage broadens — the index is currently rewarding "
                "Adoption and Momentum more than the methodology weighting suggests.",
                styles["body"],
            ),
        ]
    return parts


def _charts_section(data: ReportData, styles) -> list[Any]:
    composite_png = render_composite_chart(data.composite_history)
    hist_png = render_score_histogram(data.score_distribution)
    breakdown_png = render_discovery_breakdown(data.discovered_via_breakdown)

    return [
        Paragraph("CHARTS", styles["kicker"]),
        Paragraph("How the index is shaped.", styles["h2"]),
        Image(BytesIO(composite_png), width=7 * inch, height=2.6 * inch),
        Spacer(1, 0.2 * inch),
        Table(
            [
                [
                    Image(BytesIO(hist_png), width=3.4 * inch, height=2.4 * inch),
                    Image(BytesIO(breakdown_png), width=3.4 * inch, height=2.4 * inch),
                ]
            ],
            colWidths=[3.5 * inch, 3.5 * inch],
            hAlign="LEFT",
        ),
    ]


def _tape_table_section(data: ReportData, styles) -> list[Any]:
    """The TAPE-100 in full. ReportLab paginates the Table on its own."""
    header = [
        "Rank",
        "Agent",
        "Via",
        "AgentScore",
        "Adoption",
        "Quality",
        "Momentum",
        "Community",
    ]
    rows: list[list[Any]] = [header]
    for r in data.tape100:
        rows.append(
            [
                str(r.rank),
                Paragraph(f"<b>{_safe(r.name)}</b><br/><font color='#6b7280' size=7>{_safe(r.slug)}</font>", styles["tablecell"]),
                r.discovered_via.replace("_", " "),
                _fmt(r.score),
                _fmt(r.adoption),
                _fmt(r.quality, unrated=True),
                _fmt(r.momentum),
                _fmt(r.community),
            ]
        )

    table = Table(
        rows,
        colWidths=[
            0.4 * inch,
            2.5 * inch,
            0.95 * inch,
            0.85 * inch,
            0.7 * inch,
            0.7 * inch,
            0.75 * inch,
            0.85 * inch,
        ],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, INK),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("TEXTCOLOR", (0, 1), (-1, -1), INK),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 1), (0, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, HAIRLINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [
        Paragraph("THE TAPE-100", styles["kicker"]),
        Paragraph("Constituents in full.", styles["h2"]),
        table,
    ]


def _page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    page_no = canvas.getPageNumber()
    width, _ = LETTER
    canvas.drawCentredString(
        width / 2,
        0.4 * inch,
        f"AgentTape · TAPE-100 Inaugural Report · page {page_no}",
    )
    canvas.restoreState()


def _fmt(v: float | None, unrated: bool = False) -> str:
    if v is None:
        return "Unrated" if unrated else "—"
    return f"{v:.1f}"


def _safe(s: str | None) -> str:
    if not s:
        return ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _relative(iso: str | None) -> str:
    if not iso:
        return "earlier this period"
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return "earlier this period"
    days = (datetime.now(UTC) - t).days
    if days <= 1:
        return "in the last day"
    if days <= 7:
        return f"{days} days ago"
    if days <= 30:
        return f"{days} days ago"
    return t.strftime("%B %d")


# ---------------------------------------------------------------- json


def write_json(data: ReportData, path: Path) -> None:
    """Mirror of the report data picked up by /report/inaugural on the web."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": data.generated_at.isoformat(),
        "tape100": [
            {
                "rank": r.rank,
                "slug": r.slug,
                "name": r.name,
                "score": r.score,
                "adoption": r.adoption,
                "quality": r.quality,
                "momentum": r.momentum,
                "community": r.community,
                "discovered_via": r.discovered_via,
                "github_repo": r.github_repo,
                "discovered_at": r.discovered_at.isoformat()
                if r.discovered_at
                else None,
            }
            for r in data.tape100
        ],
        "composite_history": [
            {"captured_at": t.isoformat(), "composite_value": v}
            for t, v in data.composite_history
        ],
        "score_distribution": data.score_distribution,
        "discovered_via_breakdown": data.discovered_via_breakdown,
        "findings": {
            "surprising_leader": data.findings.surprising_leader,
            "notable_decline": data.findings.notable_decline,
            "concentration": data.findings.concentration,
        },
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------- entry


def _resolve_dsn() -> str:
    raw = os.environ.get(
        "DATABASE_URL",
        "postgresql://agenttape:agenttape@localhost:5432/agenttape",
    )
    # psycopg accepts asyncpg-shaped URLs but with a different prefix —
    # strip the +asyncpg / +psycopg suffix if present.
    if raw.startswith("postgresql+asyncpg://"):
        raw = raw.replace("postgresql+asyncpg://", "postgresql://", 1)
    if raw.startswith("postgresql+psycopg://"):
        raw = raw.replace("postgresql+psycopg://", "postgresql://", 1)
    return raw


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dsn = _resolve_dsn()
    log.info("loading data from %s", _redacted(dsn))
    data = load_data(dsn)

    log.info("rendering PDF -> %s", PDF_PATH)
    build_pdf(data, PDF_PATH)

    log.info("writing JSON -> %s", JSON_PATH)
    write_json(data, JSON_PATH)

    # Mirror to apps/web/public so /report/inaugural can serve it without
    # a backend round-trip. Optional — skip silently if the path doesn't
    # exist (e.g. running this script from a non-monorepo checkout).
    if WEB_JSON_PATH.parent.exists():
        write_json(data, WEB_JSON_PATH)
        log.info("mirrored JSON -> %s", WEB_JSON_PATH)
        web_pdf = WEB_JSON_PATH.parent / "launch-report.pdf"
        web_pdf.write_bytes(PDF_PATH.read_bytes())
        log.info("mirrored PDF  -> %s", web_pdf)

    log.info(
        "done. tape100=%d composite_points=%d generated_at=%s",
        len(data.tape100),
        len(data.composite_history),
        data.generated_at.isoformat(),
    )
    return 0


def _redacted(dsn: str) -> str:
    if "@" in dsn:
        head, tail = dsn.split("@", 1)
        return head.split(":")[0] + ":***@" + tail
    return dsn


if __name__ == "__main__":
    sys.exit(main())
