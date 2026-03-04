import unittest

from noodswap.cards import CARD_CATALOG, CARD_IMAGE_URLS, default_card_image


class CardsImageTests(unittest.TestCase):
    def test_every_card_has_explicit_image_source(self) -> None:
        missing_explicit_ids = [
            card_id
            for card_id, card in CARD_CATALOG.items()
            if not card.get("image") and card_id not in CARD_IMAGE_URLS
        ]
        self.assertEqual(missing_explicit_ids, [])

    def test_no_card_uses_fallback_placeholder_image(self) -> None:
        fallback_ids = [
            card_id
            for card_id, card in CARD_CATALOG.items()
            if card.get("image") == default_card_image(card_id)
        ]
        self.assertEqual(fallback_ids, [])


if __name__ == "__main__":
    unittest.main()
