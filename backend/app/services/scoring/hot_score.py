import math


def normalize_log(value: float, base: float = 10.0) -> float:
    if value <= 0:
        return 0.0
    return math.log(value + 1, base)


def compute_hot_score(
    volume_24h: float,
    probability_change_24h: float,
    news_mention_count: int,
    liquidity: float,
) -> float:
    v = normalize_log(volume_24h) * 0.35
    p = abs(probability_change_24h) * 100 * 0.25
    n = news_mention_count * 0.30
    l = normalize_log(liquidity) * 0.10
    return round(v + p + n + l, 4)
