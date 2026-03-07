import unittest

from noodswap.cards import CARD_CATALOG, SERIES_CATALOG, default_card_image


class CardsImageTests(unittest.TestCase):
    def test_every_card_has_local_path_image_value(self) -> None:
        missing_local_path_ids = [
            card_id
            for card_id, card in CARD_CATALOG.items()
            if not isinstance(card.get("image"), str) or not card["image"].startswith("runtime/card_images/")
        ]
        self.assertEqual(missing_local_path_ids, [])

    def test_no_card_uses_remote_image_urls(self) -> None:
        remote_ids = [
            card_id
            for card_id, card in CARD_CATALOG.items()
            if isinstance(card.get("image"), str) and card["image"].startswith(("http://", "https://"))
        ]
        self.assertEqual(remote_ids, [])

    def test_default_card_image_is_local_placeholder_path(self) -> None:
        self.assertEqual(default_card_image("SPG"), "runtime/card_images/SPG.img")


class CardsSeriesTests(unittest.TestCase):
    def test_every_card_series_is_declared(self) -> None:
        undeclared_series = sorted(
            {card["series"] for card in CARD_CATALOG.values() if card["series"] not in SERIES_CATALOG}
        )
        self.assertEqual(undeclared_series, [])

    def test_declared_series_have_non_empty_emoji(self) -> None:
        missing_emojis = sorted(
            series_id
            for series_id, series_meta in SERIES_CATALOG.items()
            if not isinstance(series_meta.get("emoji"), str) or not series_meta["emoji"].strip()
        )
        self.assertEqual(missing_emojis, [])


if __name__ == "__main__":
    unittest.main()
