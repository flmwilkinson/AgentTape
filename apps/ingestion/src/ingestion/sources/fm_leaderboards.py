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
    _Leaderboard(
        name="lmsys-arena",
        url=(
            "https://datasets-server.huggingface.co/rows"
            "?dataset=lmsys%2Fchatbot_arena_leaderboard"
            "&config=default&split=train"
        ),
        max_score=None,  # ELO is unbounded
        parser="lmsys_arena_hf",
    ),
    # BigCode Models Leaderboard. Public HF dataset, scores models on
    # HumanEval / MBPP / MultiPL-E. Direct fit for "best AI coding
    # agent" queries since coding-capable FMs are the spine of the
    # CODE-25 / agent-engine selection question. Same datasets-server
    # parser shape as Open LLM (eval_name + Average column).
    _Leaderboard(
        name="bigcode-models",
        url=(
            "https://datasets-server.huggingface.co/rows"
            "?dataset=bigcode%2Fbigcode-models-leaderboard"
            "&config=default&split=train"
        ),
        max_score=100.0,
        parser="hf_dataset_rows",
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
                await _upsert_result(
                    session, aid, bench_ids[board.name], captured, score
                )
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
) -> None:
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


async def _fetch_rows(
    http,
    board: _Leaderboard,
    *,
    hf_token: str | None = None,
) -> list[tuple[str, float]]:
    """Return [(model_name, score), ...] for the given leaderboard."""
    if board.parser in ("hf_dataset_rows", "lmsys_arena_hf"):
        # Both parsers consume HuggingFace datasets-server pages but
        # interpret the row schema differently — pick the per-page
        # parser by name. HF token is forwarded so datasets that
        # require auth (most community-published leaderboards now do)
        # don't 401.
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
        _parse_lmsys_arena_hf if parser == "lmsys_arena_hf" else _parse_hf_dataset_rows
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
    """LMSys Chatbot Arena leaderboard rows from HuggingFace datasets-server.

    Shape:
      {"rows": [{"row": {"Model": "GPT-5", "Arena Score": 1421, ...}}]}

    Match name is taken from ``Model`` (the human-readable display
    name); the FM leaderboard ingestor's normalisation handles the
    "GPT-5" → "openai-gpt-5" join. Score is the ELO rating.
    """
    try:
        data = json.loads(body)
    except ValueError:
        return []
    out: list[tuple[str, float]] = []
    for entry in data.get("rows") or []:
        row = (entry or {}).get("row") or {}
        name = row.get("Model") or row.get("model") or row.get("Name")
        score = (
            row.get("Arena Score")
            or row.get("arena_score")
            or row.get("Elo")
            or row.get("rating")
        )
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
