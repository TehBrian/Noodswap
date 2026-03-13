from typing import Callable, Mapping


def display_card_id(card_id: str | None) -> str:
    if card_id is None:
        return "?  "
    return card_id.strip().lower().ljust(3)


def display_card_id_raw(card_id: str | None) -> str:
    if card_id is None:
        return "?"
    return card_id.strip().lower()


def generation_label(generation: int) -> str:
    return f"G-{generation}"


def proper_case(value: str) -> str:
    return " ".join(word.capitalize() for word in value.split())


def series_display(series: str, *, series_catalog: Mapping[str, Mapping[str, object]]) -> str:
    series_meta = series_catalog.get(series)
    if series_meta is None:
        return proper_case(series)

    label = str(series_meta.get("label") or proper_case(series))
    return f"{series_meta['emoji']} {label}"


def series_emoji(series: str, *, series_catalog: Mapping[str, Mapping[str, object]]) -> str:
    series_meta = series_catalog.get(series)
    if series_meta is None:
        return proper_case(series)
    return str(series_meta["emoji"])


def card_base_display(
    card_type_id: str,
    *,
    card_catalog: Mapping[str, Mapping[str, object]],
    series_catalog: Mapping[str, Mapping[str, object]],
    card_base_value: Callable[[str], int],
) -> str:
    card = card_catalog[card_type_id]
    return (
        f"(`{card_type_id}`) [{series_emoji(str(card['series']), series_catalog=series_catalog)}] "
        f"**{card['name']}** ({proper_case(str(card['rarity']))}) "
        f"(**{card_base_value(card_type_id)}** dough)"
    )


def card_display(
    card_type_id: str,
    generation: int,
    card_id: str | None = None,
    *,
    pad_card_id: bool = True,
    morph_key: str | None = None,
    frame_key: str | None = None,
    font_key: str | None = None,
    card_catalog: Mapping[str, Mapping[str, object]],
    series_catalog: Mapping[str, Mapping[str, object]],
    card_value: Callable[..., int],
) -> str:
    card = card_catalog[card_type_id]
    card_id_text = display_card_id(card_id) if pad_card_id else display_card_id_raw(card_id)
    return (
        f"`#{card_id_text}` **{card['name']}** • (`{card_type_id}`) "
        f"[{series_display(str(card['series']), series_catalog=series_catalog)}] "
        f"({proper_case(str(card['rarity']))}) "
        f"• **{generation_label(generation)}** "
        f"(**{card_value(card_type_id, generation, morph_key=morph_key, frame_key=frame_key, font_key=font_key)}** dough)"
    )


def card_display_concise(
    card_type_id: str,
    generation: int,
    card_id: str | None = None,
    *,
    morph_key: str | None = None,
    frame_key: str | None = None,
    font_key: str | None = None,
    card_catalog: Mapping[str, Mapping[str, object]],
    series_catalog: Mapping[str, Mapping[str, object]],
    card_value: Callable[..., int],
) -> str:
    card = card_catalog[card_type_id]
    card_id_text = display_card_id(card_id)
    return (
        f"`#{card_id_text}` (`{card_type_id}`) [{series_emoji(str(card['series']), series_catalog=series_catalog)}] "
        f"**{card['name']}** ({proper_case(str(card['rarity']))}) • **{generation_label(generation)}** "
        f"(**{card_value(card_type_id, generation, morph_key=morph_key, frame_key=frame_key, font_key=font_key)}** dough)"
    )
