from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "PolyMonitor"
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_chat_model: str = "gemini-2.5-flash-lite"

    polymarket_base_url: str = "https://gamma-api.polymarket.com"
    news_api_key: str = ""
    news_api_key2: str = ""
    gnews_api_key: str = ""
    worldnews_api_key: str = ""
    news_api_base_url: str = "https://newsapi.org/v2"
    gnews_max_articles: int = 30
    worldnews_max_articles: int = 30
    newsdata_max_articles: int = 30

    rthk_rss_enabled: bool = True
    rthk_rss_url: str = "https://rthk9.rthk.hk/rthk/news/rss/c_expressnews_clocal.xml"
    rthk_rss_max_items: int = 60
    news_rss_max_items_per_feed: int = 90

    news_min_per_region: int = 30
    news_supplement_fetch_size: int = 35
    news_supplement_max_rounds: int = 4

    finnhub_api_key: str = ""
    fmp_api_key: str = ""
    fmp_api_base_url: str = "https://financialmodelingprep.com/stable/"
    massive_api_key: str = ""
    massive_api_base_url: str = "https://api.massive.com"

    massive_proxy_username: str = ""
    massive_proxy_api_key: str = ""
    massive_proxy_https_port: int = 65535
    massive_proxy_http_port: int = 65534
    massive_proxy_socks5_port: int = 65533

    polymarket_refresh_seconds: int = 300
    polymarket_markets_max_events: int = 500
    polymarket_markets_max_markets: int = 800
    polymarket_monitor_max_active_events: int = 500
    polymarket_monitor_max_closed_events: int = 200
    polymarket_monitor_max_markets: int = 1000
    news_refresh_seconds: int = 900
    breaking_refresh_seconds: int = 900
    general_news_refresh_seconds: int = 1800
    news_scheduler_enabled: bool = False
    news_fetch_external_on_request: bool = False
    gnews_daily_limit: int = 100
    worldnews_daily_limit: int = 500
    newsdata_daily_limit: int = 200
    hotpoints_top_n: int = 60

    data_dir: Path = BASE_DIR / "data"
    mock_dir: Path = BASE_DIR / "data" / "mock"

    class Config:
        env_file = BASE_DIR / ".env"


settings = Settings()
