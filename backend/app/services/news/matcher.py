def count_mentions(market_keywords: list[str], articles: list[dict]) -> int:
    count = 0
    kw_set = set(k.lower() for k in market_keywords)
    for article in articles:
        article_kws = set(k.lower() for k in article.get("keywords", []))
        title_lower = article.get("title", "").lower()
        if article_kws & kw_set:
            count += 1
        elif any(kw in title_lower for kw in kw_set):
            count += 1
    return count
