import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: tuple[int, ...] = tuple(x for x in (env_int(v.strip(), 0) for v in os.getenv("ADMIN_IDS", "").split(",") if v.strip()) if x)
    db_path: str = os.getenv("DB_PATH", "./data/nurvpn.db")
    web_host: str = os.getenv("WEB_HOST", "127.0.0.1")
    web_port: int = env_int("WEB_PORT", 8090)
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "")
    trial_days: int = env_int("TRIAL_DAYS", 1)
    xui_url: str = os.getenv("XUI_URL", "").rstrip("/")
    xui_username: str = os.getenv("XUI_USERNAME", "")
    xui_password: str = os.getenv("XUI_PASSWORD", "")
    xui_inbound_id: int = env_int("XUI_INBOUND_ID", 1)
    xui_verify_tls: bool = env_bool("XUI_VERIFY_TLS", False)
    xui_subscription_host: str = os.getenv("XUI_SUBSCRIPTION_HOST", "")
    plan_7: int = env_int("PLAN_7_DAYS_STARS", 50)
    plan_30: int = env_int("PLAN_30_DAYS_STARS", 150)
    plan_90: int = env_int("PLAN_90_DAYS_STARS", 350)

settings = Settings()
