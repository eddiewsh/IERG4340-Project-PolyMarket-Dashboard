from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "PolyMonitor"
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    polymarket_base_url: str = "https://gamma-api.polymarket.com"
    news_api_key: str = ""
    news_api_base_url: str = "https://newsapi.org/v2"

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
    news_refresh_seconds: int = 900
    hotpoints_top_n: int = 60

    data_dir: Path = BASE_DIR / "data"
    mock_dir: Path = BASE_DIR / "data" / "mock"

    class Config:
        env_file = BASE_DIR / ".env"


settings = Settings()
