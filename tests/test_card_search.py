import unittest

from bot.card_search import search_card_ids


class CardSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = {
            "LUF": {"name": "Luffy's Hat", "series": "One Piece"},
            "NAR": {"name": "Naruto Uzumaki", "series": "Naruto"},
            "SPG": {"name": "Spicy Noodle", "series": "Noods"},
        }

    def test_ignores_apostrophes_in_query_matching(self) -> None:
        self.assertEqual(search_card_ids("luffys hat", card_catalog=self.catalog), ["LUF"])
        self.assertEqual(search_card_ids("luffy's hat", card_catalog=self.catalog), ["LUF"])

    def test_fuzzy_fallback_returns_name_matches_when_exact_not_found(self) -> None:
        self.assertEqual(search_card_ids("naruto uzamaki", card_catalog=self.catalog), ["NAR"])

    def test_fuzzy_fallback_includes_series_matching_when_enabled(self) -> None:
        self.assertEqual(
            search_card_ids("one pece", card_catalog=self.catalog, include_series=True),
            ["LUF"],
        )


if __name__ == "__main__":
    unittest.main()
