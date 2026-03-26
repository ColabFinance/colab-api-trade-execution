from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """
    Application settings for api-trade-execution.
    """

    APP_NAME: str = os.getenv("APP_NAME", "api-trade-execution")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "trade_execution_db")
    MONGODB_MAX_POOL_SIZE: int = int(os.getenv("MONGODB_MAX_POOL_SIZE", "50"))
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = int(
        os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "5000")
    )
    MONGODB_CONNECT_TIMEOUT_MS: int = int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "3000"))
    MONGODB_SOCKET_TIMEOUT_MS: int = int(os.getenv("MONGODB_SOCKET_TIMEOUT_MS", "10000"))

    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
    BINANCE_TLD: str = os.getenv("BINANCE_TLD", "com")

    DEFAULT_MARGIN_TYPE: str = os.getenv("DEFAULT_MARGIN_TYPE", "ISOLATED")
    DEFAULT_RECV_WINDOW_MS: int = int(os.getenv("DEFAULT_RECV_WINDOW_MS", "5000"))


settings = Settings()