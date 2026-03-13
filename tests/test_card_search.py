import pytest

from bot.card_search import search_card_ids


@pytest.fixture
def catalog() -> dict[str, dict[str, str]]:
    return {
        "LUF": {"name": "Luffy's Hat", "series": "One Piece"},
        "NAR": {"name": "Naruto Uzumaki", "series": "Naruto"},
        "SPG": {"name": "Spicy Noodle", "series": "Noods"},
    }


def test_ignores_apostrophes_in_query_matching(catalog: dict[str, dict[str, str]]) -> None:
    assert search_card_ids("luffys hat", card_catalog=catalog) == ["LUF"]
    assert search_card_ids("luffy's hat", card_catalog=catalog) == ["LUF"]


def test_fuzzy_fallback_returns_name_matches_when_exact_not_found(catalog: dict[str, dict[str, str]]) -> None:
    assert search_card_ids("naruto uzamaki", card_catalog=catalog) == ["NAR"]


def test_fuzzy_fallback_includes_series_matching_when_enabled(catalog: dict[str, dict[str, str]]) -> None:
    assert search_card_ids("one pece", card_catalog=catalog, include_series=True) == ["LUF"]


def test_search_uses_zero_padded_card_type_id_tie_break() -> None:
    catalog = {
        "2Y": {"name": "Alpha", "series": "S"},
        "2": {"name": "Alpha", "series": "S"},
        "10": {"name": "Alpha", "series": "S"},
        "1": {"name": "Alpha", "series": "S"},
    }
    assert search_card_ids("alpha", card_catalog=catalog) == ["1", "2", "10", "2Y"]
