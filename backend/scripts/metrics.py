"""Ranking metrics for the synthetic evaluation smoke test."""

from __future__ import annotations

import math


def precision_at_k(ranked_ids: list, relevant_ids: set, k: int) -> float:
    if k <= 0:
        return 0.0
    top = ranked_ids[:k]
    hits = sum(1 for item in top if item in relevant_ids)
    return hits / k


def recall_at_k(ranked_ids: list, relevant_ids: set, k: int) -> float:
    if not relevant_ids:
        return 0.0
    top = ranked_ids[:k]
    hits = sum(1 for item in top if item in relevant_ids)
    return hits / len(relevant_ids)


def dcg_at_k(gains: list[float], k: int) -> float:
    total = 0.0
    for i, gain in enumerate(gains[:k], start=1):
        total += gain / math.log2(i + 1)
    return total


def ndcg_at_k(ranked_ids: list, graded: dict[str, float], k: int) -> float:
    gains = [float(graded.get(item, 0.0)) for item in ranked_ids[:k]]
    ideal = sorted(graded.values(), reverse=True)
    denom = dcg_at_k(ideal, k)
    if denom == 0:
        return 0.0
    return dcg_at_k(gains, k) / denom


def mrr(ranked_ids: list, relevant_ids: set) -> float:
    for i, item in enumerate(ranked_ids, start=1):
        if item in relevant_ids:
            return 1.0 / i
    return 0.0
