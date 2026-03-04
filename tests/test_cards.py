import unittest

from noodswap.cards import CARD_CATALOG, CARD_IMAGE_URLS, default_card_image


class CardsImageTests(unittest.TestCase):
    def test_every_card_has_local_path_image_value(self) -> None:
        missing_local_path_ids = [
            card_id
            for card_id, card in CARD_CATALOG.items()
            if not isinstance(card.get("image"), str) or not card["image"].startswith("assets/card_images/")
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
        self.assertEqual(default_card_image("SPG"), "assets/card_images/SPG.img")


if __name__ == "__main__":
    unittest.main()
