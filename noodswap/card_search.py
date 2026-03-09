from difflib import get_close_matches
from typing import Mapping, TypedDict


class CardSearchRecord(TypedDict):
    name: str
    series: str


def normalize_card_id(card_id: str) -> str:
    return card_id.strip().upper()


def _normalize_for_search(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def search_card_ids(
    query: str,
    *,
    card_catalog: Mapping[str, CardSearchRecord],
    include_series: bool = False,
) -> list[str]:
    cleaned_query = _normalize_for_search(query.strip())
    if not cleaned_query:
        return []

    exact_name_matches: list[str] = []
    prefix_name_matches: list[str] = []
    contains_name_matches: list[str] = []
    exact_series_matches: list[str] = []
    prefix_series_matches: list[str] = []
    contains_series_matches: list[str] = []

    search_names: dict[str, list[str]] = {}
    search_series: dict[str, list[str]] = {}

    for card_id, card in card_catalog.items():
        card_name = card["name"]
        normalized_name = _normalize_for_search(card_name)
        if normalized_name:
            search_names.setdefault(normalized_name, []).append(card_id)
        if normalized_name == cleaned_query:
            exact_name_matches.append(card_id)
        elif normalized_name.startswith(cleaned_query):
            prefix_name_matches.append(card_id)
        elif cleaned_query in normalized_name:
            contains_name_matches.append(card_id)

        if include_series:
            normalized_series = _normalize_for_search(card["series"])
            if normalized_series:
                search_series.setdefault(normalized_series, []).append(card_id)
            if normalized_series == cleaned_query:
                exact_series_matches.append(card_id)
            elif normalized_series.startswith(cleaned_query):
                prefix_series_matches.append(card_id)
            elif cleaned_query in normalized_series:
                contains_series_matches.append(card_id)

    def sort_key(cid: str) -> tuple[str, str]:
        return card_catalog[cid]["name"].casefold(), cid

    ordered_groups = [
        sorted(exact_name_matches, key=sort_key),
        sorted(prefix_name_matches, key=sort_key),
        sorted(contains_name_matches, key=sort_key),
    ]
    if include_series:
        ordered_groups.extend(
            [
                sorted(exact_series_matches, key=sort_key),
                sorted(prefix_series_matches, key=sort_key),
                sorted(contains_series_matches, key=sort_key),
            ]
        )

    if not exact_name_matches and not exact_series_matches:
        fuzzy_match_keys = get_close_matches(cleaned_query, list(search_names), n=10, cutoff=0.75)
        fuzzy_name_matches = sorted(
            {
                card_id
                for match_key in fuzzy_match_keys
                for card_id in search_names.get(match_key, [])
            },
            key=sort_key,
        )
        if fuzzy_name_matches:
            ordered_groups.append(fuzzy_name_matches)

        if include_series:
            fuzzy_series_keys = get_close_matches(cleaned_query, list(search_series), n=10, cutoff=0.75)
            fuzzy_series_matches = sorted(
                {
                    card_id
                    for match_key in fuzzy_series_keys
                    for card_id in search_series.get(match_key, [])
                },
                key=sort_key,
            )
            if fuzzy_series_matches:
                ordered_groups.append(fuzzy_series_matches)

    seen: set[str] = set()
    results: list[str] = []
    for group in ordered_groups:
        for card_id in group:
            if card_id in seen:
                continue
            seen.add(card_id)
            results.append(card_id)
    return results


def search_card_ids_by_name(query: str, *, card_catalog: Mapping[str, CardSearchRecord]) -> list[str]:
    return search_card_ids(query, card_catalog=card_catalog)


def card_code(_card_id: str, dupe_code: str) -> str:
    return dupe_code.strip().lower()


def split_card_code(raw_code: str) -> str | None:
    cleaned = raw_code.strip()
    if not cleaned:
        return None

    if cleaned.startswith("#"):
        cleaned = cleaned[1:]
        if not cleaned:
            return None

    dupe_code = cleaned.lower()

    if not all(char.isdigit() or ("a" <= char <= "z") for char in dupe_code):
        return None

    return dupe_code
