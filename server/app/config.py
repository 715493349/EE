from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("EASTMONEY_HOST", "https://push2.eastmoney.com")
    referer: str = os.getenv("EASTMONEY_REFERER", "https://quote.eastmoney.com/")
    user_agent: str = os.getenv("EASTMONEY_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36")
    scan_interval: float = float(os.getenv("SCAN_INTERVAL_SECONDS", "3"))
    deep_interval: float = float(os.getenv("DEEP_INTERVAL_SECONDS", "5"))
    candidate_count: int = int(os.getenv("CANDIDATE_COUNT", "24"))
    stale_after: float = float(os.getenv("STALE_AFTER_SECONDS", "12"))
    timeout: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "5"))

settings = Settings()
