"""Manipulation-rule unit tests.

Pure function tests — no DB, no HTTP. We feed each rule synthetic
numbers and assert it flags / doesn't flag.
"""
from __future__ import annotations

from ingestion.config import Settings
from ingestion.integrity import (
    detect_coordinated_hn_posting,
    detect_hf_surge_without_github,
    detect_star_spike_without_contrib_diversity,
)


def _settings() -> Settings:
    # Use defaults but make sure we have explicit thresholds locked in.
    return Settings(
        spike_multiplier=2.0,
        star_spike_24h_multiplier=10.0,
        min_contributors_for_organic_spike=5,
    )


# ---------------------------------------------------- star spike rule


def test_star_spike_flagged_when_low_contributor_diversity():
    flag = detect_star_spike_without_contrib_diversity(
        stars_now=15_000,
        stars_24h_ago=1_000,  # 15x — well above 10x bar
        contributor_count=2,
        settings=_settings(),
    )
    assert flag is not None
    assert flag.rule == "star_spike_no_contrib_diversity"
    assert flag.details["multiplier"] == 15.0


def test_star_spike_not_flagged_with_organic_contributors():
    """15x with a healthy contributor base = real launch, not a farm."""
    flag = detect_star_spike_without_contrib_diversity(
        stars_now=15_000,
        stars_24h_ago=1_000,
        contributor_count=42,
        settings=_settings(),
    )
    assert flag is None


def test_star_spike_not_flagged_below_threshold():
    flag = detect_star_spike_without_contrib_diversity(
        stars_now=2_500,
        stars_24h_ago=1_000,  # 2.5x — under 10x bar
        contributor_count=2,
        settings=_settings(),
    )
    assert flag is None


def test_star_spike_handles_missing_baseline():
    flag = detect_star_spike_without_contrib_diversity(
        stars_now=10_000,
        stars_24h_ago=None,
        contributor_count=2,
        settings=_settings(),
    )
    assert flag is None


# ----------------------------------------------------- hf surge rule


def test_hf_surge_flagged_when_github_is_quiet():
    flag = detect_hf_surge_without_github(
        hf_downloads_now=20_000,
        hf_downloads_24h_ago=5_000,  # 4x
        stars_now=100,
        stars_24h_ago=100,  # flat
        commits_7d=0,
        settings=_settings(),
    )
    assert flag is not None
    assert flag.rule == "hf_surge_no_github"


def test_hf_surge_not_flagged_with_active_dev():
    flag = detect_hf_surge_without_github(
        hf_downloads_now=20_000,
        hf_downloads_24h_ago=5_000,
        stars_now=100,
        stars_24h_ago=100,
        commits_7d=12,  # active development
        settings=_settings(),
    )
    assert flag is None


def test_hf_surge_not_flagged_when_stars_also_grow():
    flag = detect_hf_surge_without_github(
        hf_downloads_now=20_000,
        hf_downloads_24h_ago=5_000,
        stars_now=200,
        stars_24h_ago=100,  # +100% star growth alongside HF surge — coordinated launch
        commits_7d=0,
        settings=_settings(),
    )
    assert flag is None


# --------------------------------------------------- coordinated HN


def test_hn_coordinated_flagged_on_sharp_jump():
    flag = detect_coordinated_hn_posting(
        hn_mentions_now=80,
        hn_mentions_recent=[10, 12, 11, 9, 10, 11],
        settings=_settings(),
    )
    assert flag is not None
    assert flag.rule == "coordinated_hn_posting"


def test_hn_coordinated_not_flagged_on_steady_climb():
    flag = detect_coordinated_hn_posting(
        hn_mentions_now=15,
        hn_mentions_recent=[10, 11, 12, 13, 14],
        settings=_settings(),
    )
    assert flag is None


def test_hn_coordinated_ignores_noise_at_low_baseline():
    """3 mentions when baseline is 1 isn't manipulation, just noise."""
    flag = detect_coordinated_hn_posting(
        hn_mentions_now=3,
        hn_mentions_recent=[1, 0, 1, 1],
        settings=_settings(),
    )
    assert flag is None
