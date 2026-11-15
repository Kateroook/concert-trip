"""Статичний діапазон вартості поїздки. Це оцінка, не бронювання."""

from __future__ import annotations

from concertrip.reference import TRIP_RANGES, ZONES, city_key


def estimate_trip(origin: str, destination: str) -> tuple[int, int] | None:
    origin_key = city_key(origin)
    destination_key = city_key(destination)
    if origin_key not in ZONES or destination_key not in ZONES:
        return None
    if origin_key == destination_key:
        return (15, 60)
    origin_zone = ZONES[origin_key]
    destination_zone = ZONES[destination_key]
    if origin_zone == destination_zone:
        return (35, 130)
    pair = tuple(sorted((origin_zone, destination_zone)))
    return TRIP_RANGES.get(pair)


def format_trip(origin: str, destination: str) -> str:
    estimate = estimate_trip(origin, destination)
    if estimate is None:
        return "Поїздка: немає оцінки для цього напрямку"
    low, high = estimate
    return f"Поїздка: €{low}–{high}, лише оцінка"
