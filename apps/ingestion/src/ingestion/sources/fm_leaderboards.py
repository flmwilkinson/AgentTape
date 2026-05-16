"""Foundation-model benchmark leaderboards.

Two free, no-auth scrapes:

    - LMSys Chatbot Arena: ELO rankings of LLMs from human preference
      pairwise voting. The community gold-standard for "which model
      is actually best to talk to."
    - LiveBench: monthly contamination-free benchmark suite scoring
      models on reasoning, coding, math, and language tasks.

Unlike the application-agent ingestors, these write directly to
``benchmark_results`` because the Quality pillar in scoring reads
that table — emitting them as signals would not actually move FM
quality scores. Each leaderboard becomes a ``benchmarks`` row
(idempotent on name) and each match becomes a ``benchmark_results``
row keyed (agent_id, benchmark_id, captured_at).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.enums import SignalSource
from ingestion.sources.base import AgentRow, Ingestor, SignalReading

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Leaderboard:
    name: str
    url: str
    max_score: float | None  # None = unbounded (e.g. ELO)
    parser: str  # which parse strategy to use


LEADERBOARDS: list[_Leaderboard] = [
    # HuggingFace Open LLM Leaderboard. Their public dataset-server
    # API returns ranked rows as JSON. Stable, no auth. Score is the
    # "Average ⬆️" composite (IFEval / BBH / MATH / GPQA / MUSR /
    # MMLU-PRO weighted average), 0–100.
    #
    # The API caps at 100 rows/page; the dataset is ~4500 rows. The
    # parser paginates internally for "hf_dataset_rows".
    _Leaderboard(
        name="open-llm-leaderboard",
        url=(
            "https://datasets-server.huggingface.co/rows"
            "?dataset=open-llm-leaderboard%2Fcontents"
            "&config=default&split=train"
        ),
        max_score=100.0,
        parser="hf_dataset_rows",
    ),
    # LMSys Chatbot Arena ELO ratings — gold-standard "which model is
    # actually best to talk to" derived from blind pairwise human votes.
    # The original arena site moved to a JS-rendered page, but the
    # community publishes the same data as a HuggingFace dataset
    # (lmsys/chatbot_arena_leaderboard, refreshed weekly). We pull the
    # parquet rows via the same datasets-server endpoint as Open LLM —
    # different parser because the column names differ ("Model" instead
    # of "eval_name", "Arena Score" instead of "Average").
    # LMArena (was LMSys) Chatbot Arena. Bradley-Terry / Elo rating
    # from blind pairwise human votes — community gold-standard for
    # "best model to actually talk to". The dataset rename from
    # lmsys → lmarena-ai also reshaped the schema; correct path is
    # config=text&split=latest. Schema columns: model_name + rating
    # (verified live, ~70 rows on the latest snapshot date).
    _Leaderboard(
        name="lmarena",
        url=(
            "https://datasets-server.huggingface.co/rows"
            "?dataset=lmarena-ai%2Fleaderboard-dataset"
            "&config=text&split=latest"
        ),
        # Elo is unbounded in theory but in practice clusters in
        # 800-1500 for live frontier models. We anchor max_score at
        # 1500 so a top-tier model (e.g. Claude Opus / GPT-5 / Gemini
        # Pro at ~1450-1500 Elo) maps to ~97-100 on the 0-100 quality
        # scale, mid-tier models (~1200) land at ~80, and unrated
        # weak models (~900) at ~60.
        # Was None previously: with NULL max_score, _agent_benchmark_score
        # used the raw Elo as-is, so every agent matched on lmarena got
        # a raw value of 1200+ averaged into their Quality. That swamped
        # other benchmarks and clamped to 100 — visible in the prod
        # data as a "perfect score" cluster for any FM only matched on
        # lmarena (mistral-large, llama-3.3, gemma, etc.).
        max_score=1500.0,
        parser="lmsys_arena_hf",
    ),
    # MMLU-Pro leaderboard (TIGER-Lab community submission). Expanded
    # MMLU with 14 subject categories. Headline score is the "Overall"
    # column on a 0–100 scale.
    _Leaderboard(
        name="mmlu-pro",
        url=(
            "https://datasets-server.huggingface.co/rows"
            "?dataset=TIGER-Lab%2Fmmlu_pro_leaderboard_submission"
            "&config=default&split=train"
        ),
        max_score=100.0,
        parser="mmlu_pro_hf",
    ),
    # SWE-bench leaderboard. Direct JSON from the swe-bench.github.io
    # repo's master branch. Fetches in one shot (~7MB), no pagination.
    # We pull the "Verified" sub-leaderboard since it's the curated
    # quality-controlled split — Test/Lite/Multimodal exist too but
    # Verified is the one teams care about.
    _Leaderboard(
        name="swe-bench-verified",
        url=(
            "https://raw.githubusercontent.com/SWE-bench/"
            "swe-bench.github.io/master/data/leaderboards.json"
        ),
        max_score=100.0,
        parser="swe_bench",
    ),
    # LiveBench would be a great fit here (monthly contam-free eval)
    # but their public CSV URL has changed and the new endpoint isn't
    # documented. _parse_livebench is preserved at the bottom of the
    # file so we can wire it back up the moment we find the new URL.
]

# Patterns we expect to find in slugs / names so we can match a
# leaderboard row to one of our admitted agents. Slugs derive from the
# OpenRouter id, e.g. "openai-gpt-5-3-codex"; LMSys uses display
# names like "GPT-5.3 Codex". We squash both to a comparable form.
_NORM_RE = re.compile(r"[^a-z0-9]+")


def _normalize(name: str) -> str:
    return _NORM_RE.sub("", name.lower())


class FMLeaderboardsIngestor(Ingestor):
    """Custom ingestor — writes benchmark_results, not signals.

    Overrides ``run`` because the SignalReading flow doesn't apply
    here. Each tick: fetch every leaderboard once, match rows against
    the admitted foundation-model agent set, upsert a benchmark_results
    row per match.
    """

    name: ClassVar[str] = "fm_leaderboards"
    source: ClassVar[SignalSource] = SignalSource.BENCHMARK_SCORE
    tier: ClassVar[str] = "slow"

    async def fetch(self, agents: list[AgentRow]) -> list[SignalReading]:
        # Not used — we override run() to write benchmark_results
        # directly instead of the signal pipeline.
        return []

    async def run(
        self,
        session: AsyncSession,
        agents: list[AgentRow],
        redis_client: Any,
    ) -> dict[str, int]:
        # HF datasets-server now gates many "community" datasets behind
        # auth, even for read-only access. Without an HF token in the
        # request headers, lmsys-arena and bigcode-models return 401.
        # Open LLM Leaderboard is still public so it works either way.
        hf_token = self.settings.huggingface_token

        # Build the benchmark-name → id map (idempotent insert).
        bench_ids: dict[str, UUID] = {}
        for board in LEADERBOARDS:
            bench_ids[board.name] = await _ensure_benchmark(
                session, board.name, board.url, board.max_score
            )

        # Build a lookup over admitted agents for fast row-match.
        # Foundation models are the target population; application
        # agents won't appear on these leaderboards.
        norm_to_agent: dict[str, UUID] = {}
        for a in agents:
            norm_to_agent[_normalize(a.slug)] = a.id
            for hf_id in a.hf_model_ids or []:
                norm_to_agent.setdefault(_normalize(hf_id), a.id)

        captured = datetime.now(UTC)
        written = 0
        matched_per_board: dict[str, int] = {}
        for board in LEADERBOARDS:
            try:
                rows = await _fetch_rows(self._http, board, hf_token=hf_token)
            except Exception as e:  # noqa: BLE001
                log.warning("leaderboard %s fetch failed: %s", board.name, e)
                rows = []

            matched = 0
            for model_name, score in rows:
                norm = _normalize(model_name)
                # Try direct match, then suffix match (LMSys often
                # writes "openai/gpt-5.3" while we have "openai-gpt-5-3").
                aid = norm_to_agent.get(norm)
                if aid is None:
                    for k, v in norm_to_agent.items():
                        if len(norm) >= 6 and (norm in k or k in norm):
                            aid = v
                            break
                if aid is None:
                    continue
                # _upsert_result now insert-on-change: returns False
                # when the score is unchanged from the last reading.
                # Count matched whether or not we wrote — match rate
                # is a leaderboard-quality signal, write rate is a
                # storage-cost signal.
                if await _upsert_result(
                    session, aid, bench_ids[board.name], captured, score
                ):
                    written += 1
                matched += 1
            matched_per_board[board.name] = matched
            log.info(
                "leaderboard %s: %d rows fetched, %d matched",
                board.name,
                len(rows),
                matched,
            )

        await session.commit()
        return {
            "fetched": sum(matched_per_board.values()),
            "written": written,
            "spiked": 0,
            "changed": 0,
            **{f"matched_{k}": v for k, v in matched_per_board.items()},
        }


# ----------------------------------------------------------------- helpers


async def _ensure_benchmark(
    session: AsyncSession, name: str, url: str, max_score: float | None
) -> UUID:
    """Insert the benchmarks row if needed, return its id."""
    await session.execute(
        text(
            """
            INSERT INTO benchmarks (id, name, source_url, max_score)
            VALUES (gen_random_uuid(), :n, :u, :m)
            ON CONFLICT (name) DO UPDATE SET
                source_url = EXCLUDED.source_url,
                max_score = EXCLUDED.max_score
            """
        ),
        {"n": name, "u": url, "m": max_score},
    )
    r = await session.execute(text("SELECT id FROM benchmarks WHERE name = :n"), {"n": name})
    return r.scalar_one()


async def _upsert_result(
    session: AsyncSession,
    agent_id: UUID,
    benchmark_id: UUID,
    captured_at: datetime,
    score: float,
) -> bool:
    """Insert-on-change. Returns True if a row was actually written.

    Same dedupe pattern as ``Ingestor.run`` / ``benchmarks._last_benchmark_score``:
    skip the INSERT if the most recent prior score for this
    (agent, benchmark) pair already equals the new one. Without this,
    each daily tick was writing N rows for every (agent, benchmark)
    pair regardless of whether the score had changed — visible in
    prod as Gemini 2.5 Pro with 5 identical lmarena rows and 3
    identical mmlu-pro rows. Storage burn + noisy history.
    """
    r = await session.execute(
        text(
            """
            SELECT score FROM benchmark_results
            WHERE agent_id = :aid AND benchmark_id = :bid
            ORDER BY captured_at DESC LIMIT 1
            """
        ),
        {"aid": agent_id, "bid": benchmark_id},
    )
    row = r.first()
    if row is not None and float(row[0]) == score:
        return False

    await session.execute(
        text(
            """
            INSERT INTO benchmark_results (agent_id, benchmark_id, captured_at, score)
            VALUES (:aid, :bid, :ts, :s)
            ON CONFLICT (agent_id, benchmark_id, captured_at) DO UPDATE SET
                score = EXCLUDED.score
            """
        ),
        {"aid": agent_id, "bid": benchmark_id, "ts": captured_at, "s": score},
    )
    return True


async def _fetch_rows(
    http,
    board: _Leaderboard,
    *,
    hf_token: str | None = None,
) -> list[tuple[str, float]]:
    """Return [(model_name, score), ...] for the given leaderboard."""
    if board.parser in ("hf_dataset_rows", "lmsys_arena_hf", "mmlu_pro_hf"):
        # All three parsers consume HuggingFace datasets-server pages
        # but interpret the row schema differently — pick the per-page
        # parser by name. HF token is forwarded so datasets that
        # require auth don't 401.
        return await _fetch_hf_paginated(
            http, board.url, parser=board.parser, hf_token=hf_token
        )

    try:
        r = await http.get(board.url)
    except Exception as e:  # noqa: BLE001
        log.warning("leaderboard fetch %s: %s", board.url, e)
        return []
    if r.status_code != 200:
        log.warning("leaderboard %s returned %d", board.url, r.status_code)
        return []
    text_body = r.text

    if board.parser == "lmsys":
        return _parse_lmsys(text_body)
    if board.parser == "livebench":
        return _parse_livebench(text_body)
    if board.parser == "swe_bench":
        return _parse_swe_bench(text_body)
    return []


async def _fetch_hf_paginated(
    http,
    base_url: str,
    parser: str = "hf_dataset_rows",
    *,
    hf_token: str | None = None,
) -> list[tuple[str, float]]:
    """Walk every page of a HuggingFace datasets-server `/rows` URL.

    Page size is server-capped at 100. We start at offset 0, read
    ``num_rows_total`` from the first response, and walk all pages.
    Stops on any non-200 to avoid spamming when the API rate-limits.
    The per-page parser is chosen by ``parser``: Open LLM uses
    ``eval_name`` + ``Average``, Arena uses ``Model`` + ``Arena Score``.
    """
    out: list[tuple[str, float]] = []
    page_size = 100
    offset = 0
    total: int | None = None
    page_parser = (
        _parse_lmsys_arena_hf
        if parser == "lmsys_arena_hf"
        else _parse_mmlu_pro_hf
        if parser == "mmlu_pro_hf"
        else _parse_hf_dataset_rows
    )
    headers: dict[str, str] = {}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"
    while True:
        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}offset={offset}&length={page_size}"
        try:
            r = await http.get(url, headers=headers)
        except Exception as e:  # noqa: BLE001
            log.warning("leaderboard page fetch %s: %s", url, e)
            break
        if r.status_code != 200:
            log.warning("leaderboard page %d returned %d", offset, r.status_code)
            break
        page = page_parser(r.text)
        if not page:
            break
        out.extend(page)
        try:
            data = json.loads(r.text)
        except ValueError:
            break
        if total is None:
            total = int(data.get("num_rows_total") or 0)
        offset += page_size
        if total and offset >= total:
            break
        # Safety stop — at most 50 pages (5000 rows).
        if offset >= 5000:
            break
    return out


def _parse_lmsys_arena_hf(body: str) -> list[tuple[str, float]]:
    """LMArena (was LMSys) Chatbot Arena rows from datasets-server.

    Current schema (lmarena-ai/leaderboard-dataset, config=text,
    split=latest):
      {"rows": [{"row": {"model_name": "gpt-5", "rating": 1421.5,
                          "rank": 1, "vote_count": 12000,
                          "organization": "OpenAI"}}]}

    Older schema (lmsys/chatbot_arena_leaderboard) used "Model" /
    "Arena Score" — kept those as fallbacks so a future schema swap
    doesn't immediately break the ingestor.
    """
    try:
        data = json.loads(body)
    except ValueError:
        return []
    out: list[tuple[str, float]] = []
    for entry in data.get("rows") or []:
        row = (entry or {}).get("row") or {}
        name = (
            row.get("model_name")
            or row.get("Model")
            or row.get("model")
            or row.get("Name")
        )
        score = (
            row.get("rating")
            or row.get("Arena Score")
            or row.get("arena_score")
            or row.get("Elo")
        )
        if name is None or score is None:
            continue
        try:
            out.append((str(name), float(score)))
        except (ValueError, TypeError):
            continue
    return out


def _parse_mmlu_pro_hf(body: str) -> list[tuple[str, float]]:
    """MMLU-Pro leaderboard rows from datasets-server.

    Schema (TIGER-Lab/mmlu_pro_leaderboard_submission):
      {"rows": [{"row": {"Models": "gpt-5", "Overall": 78.4,
                          "biology": ..., "business": ..., ...}}]}

    The score column is "Overall" — TIGER-Lab inconsistently reports
    this as either a 0-1 fraction (e.g. 0.86) or a 0-100 percentage
    (e.g. 86.0). We normalise: any value <= 1.5 is treated as a
    fraction and scaled to 0-100. Real MMLU-Pro Overall numbers cluster
    in the 40-95 range so the 1.5 threshold has plenty of headroom.

    Was visible in prod as ``google-gemini-2-5-pro mmlu-pro=0.86`` —
    correct underlying number, wrong scale: the benchmarks row has
    max_score=100, so 0.86 / 100 * 100 = 0.86 ended up as a near-zero
    Quality contribution for the model. Multiplying fractions by 100
    in the parser keeps benchmarks.max_score consistent across every
    entry on this leaderboard.
    """
    try:
        data = json.loads(body)
    except ValueError:
        return []
    out: list[tuple[str, float]] = []
    for entry in data.get("rows") or []:
        row = (entry or {}).get("row") or {}
        name = row.get("Models") or row.get("Model") or row.get("model_name")
        score = row.get("Overall") or row.get("overall") or row.get("Average")
        if name is None or score is None:
            continue
        try:
            v = float(score)
        except (ValueError, TypeError):
            continue
        if v <= 1.5:
            v *= 100.0
        out.append((str(name), v))
    return out


def _parse_swe_bench(body: str) -> list[tuple[str, float]]:
    """SWE-bench leaderboard from swe-bench.github.io.

    Shape:
      {
        "leaderboards": [
          {"name": "Verified", "results": [
            {"name": "Claude Opus 4.7", "resolved": 73.4, ...},
            ...
          ]},
          {"name": "Test", "results": [...]},
          {"name": "Lite", "results": [...]},
          ...
        ]
      }

    We pull only the "Verified" board because it's the curated
    quality-controlled split (the others have known broken instances).
    Score is the ``resolved`` percentage — fraction of issues the
    agent actually fixed, on a 0–100 scale.
    """
    try:
        data = json.loads(body)
    except ValueError:
        return []
    boards = (data or {}).get("leaderboards") or []
    target = next(
        (b for b in boards if (b or {}).get("name") == "Verified"),
        None,
    )
    if not target:
        return []
    out: list[tuple[str, float]] = []
    for r in target.get("results") or []:
        if not isinstance(r, dict):
            continue
        name = r.get("name") or r.get("model")
        score = r.get("resolved") or r.get("score")
        if name is None or score is None:
            continue
        try:
            out.append((str(name), float(score)))
        except (ValueError, TypeError):
            continue
    return out


def _parse_hf_dataset_rows(body: str) -> list[tuple[str, float]]:
    """HuggingFace datasets-server `/rows` response.

    Shape:
      {"rows": [{"row": {"eval_name": "Meta-Llama-3-70B...", "Average": 51.2, ...}}, ...]}

    We use ``eval_name`` (full HF model id) for matching and ``Average``
    for the score. eval_name is more reliable than the human-readable
    ``Model`` field for joining against agent slugs derived from
    OpenRouter ids."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    out: list[tuple[str, float]] = []
    for entry in data.get("rows") or []:
        row = (entry or {}).get("row") or {}
        name = row.get("eval_name") or row.get("fullname") or row.get("Model")
        score = row.get("Average") or row.get("Average ⬆️")
        if name is None or score is None:
            continue
        try:
            out.append((str(name), float(score)))
        except (ValueError, TypeError):
            continue
    return out


def _parse_lmsys(body: str) -> list[tuple[str, float]]:
    """LMSys publishes a JSON file with model names + ELO ratings."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    out: list[tuple[str, float]] = []
    # The shape varies as the leaderboard evolves. We accept either:
    #   [{"model": "...", "rating": 1234.5}, ...]
    #   [{"name":  "...", "elo":    1234.5}, ...]
    items = data if isinstance(data, list) else (data.get("data") or [])
    for it in items:
        if not isinstance(it, dict):
            continue
        name = it.get("model") or it.get("name") or it.get("Model")
        score = (
            it.get("rating")
            or it.get("elo")
            or it.get("Arena Score")
            or it.get("score")
        )
        if name is None or score is None:
            continue
        try:
            out.append((str(name), float(score)))
        except (ValueError, TypeError):
            continue
    return out


def _parse_livebench(body: str) -> list[tuple[str, float]]:
    """LiveBench publishes a CSV per release. First column is the
    model identifier, last column is the global average score."""
    out: list[tuple[str, float]] = []
    lines = [ln for ln in body.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []
    header = [h.strip().lower() for h in _csv_split(lines[0])]
    name_idx = next(
        (i for i, h in enumerate(header) if h in ("model", "model_name", "name")),
        0,
    )
    score_idx = next(
        (
            i
            for i, h in enumerate(header)
            if h in ("global_average", "global average", "average", "score")
        ),
        len(header) - 1,
    )
    for ln in lines[1:]:
        cells = _csv_split(ln)
        if len(cells) <= max(name_idx, score_idx):
            continue
        try:
            out.append((cells[name_idx].strip(), float(cells[score_idx].strip())))
        except ValueError:
            continue
    return out


def _csv_split(line: str) -> list[str]:
    """Tiny CSV split — handles quoted commas. Avoids pulling in the
    csv module just for this one parser."""
    out: list[str] = []
    buf: list[str] = []
    in_quote = False
    for c in line:
        if c == '"':
            in_quote = not in_quote
        elif c == "," and not in_quote:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(c)
    out.append("".join(buf))
    return out
