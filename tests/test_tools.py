"""
Tests for search_listings — no mocking, runs against the real
data/listings.json via load_listings().
"""

import pytest

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


@pytest.fixture(scope="module")
def sample_item():
    results = search_listings("vintage graphic tee", None, 50)
    assert results, "expected at least one listing to test against"
    return results[0]


def test_vintage_graphic_tee_returns_nonempty():
    results = search_listings("vintage graphic tee", None, 50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_no_match_returns_empty_without_raising():
    results = search_listings("designer ballgown", "XXS", 5)
    assert results == []


def test_price_filter_respected():
    results = search_listings("jacket", None, 30)
    assert all(float(item["price"]) <= 30.0 for item in results)


def test_size_filter_case_insensitive():
    results = search_listings("top", "M", None)
    assert all("m" in item["size"].lower() for item in results)


def test_empty_description_returns_list_without_raising():
    results = search_listings("", None, None)
    assert isinstance(results, list)


# ── suggest_outfit / create_fit_card (real Groq API calls) ──────────────────


def test_suggest_outfit_with_example_wardrobe(sample_item):
    result = suggest_outfit(sample_item, get_example_wardrobe())
    assert isinstance(result, str)
    assert result.strip()


def test_suggest_outfit_with_empty_wardrobe(sample_item):
    result = suggest_outfit(sample_item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert result.strip()


def test_create_fit_card_from_outfit(sample_item):
    outfit = suggest_outfit(sample_item, get_example_wardrobe())
    result = create_fit_card(outfit, sample_item)
    assert isinstance(result, str)
    assert result.strip()


def test_create_fit_card_empty_outfit(sample_item):
    result = create_fit_card("", sample_item)
    assert isinstance(result, str)
    assert result.strip()


def test_create_fit_card_whitespace_outfit(sample_item):
    result = create_fit_card("   ", sample_item)
    assert isinstance(result, str)
    assert result.strip()
