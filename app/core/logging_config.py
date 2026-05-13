import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

VALID_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

LOG_HANDLER_NAME = "ohmstash_file"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_FILE_PATH = PROJECT_ROOT / "logs" / "ohmstash.log"


def normalize_log_level(level: str | None) -> str:
    normalized = str(level or "INFO").strip().upper()
    if normalized not in VALID_LOG_LEVELS:
        return "INFO"
    return normalized


def get_log_file_path() -> Path:
    if settings.LOG_FILE_PATH:
        return Path(settings.LOG_FILE_PATH).expanduser().resolve()
    return DEFAULT_LOG_FILE_PATH


def configure_logging(level: str | None = None) -> None:
    log_level = normalize_log_level(level or settings.LOG_LEVEL)
    log_file_path = get_log_file_path()
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(VALID_LOG_LEVELS[log_level])

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    file_handler = _get_file_handler(root_logger)
    if not file_handler:
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.set_name(LOG_HANDLER_NAME)
        root_logger.addHandler(file_handler)

    file_handler.setLevel(VALID_LOG_LEVELS[log_level])
    file_handler.setFormatter(formatter)

    for logger_name in ("app", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(logger_name).setLevel(VALID_LOG_LEVELS[log_level])

    logging.getLogger(__name__).info("Logging configured at %s", log_level)


def set_runtime_log_level(level: str) -> str:
    log_level = normalize_log_level(level)
    numeric_level = VALID_LOG_LEVELS[log_level]
    logging.getLogger().setLevel(numeric_level)
    for handler in logging.getLogger().handlers:
        handler.setLevel(numeric_level)
    for logger_name in ("app", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(logger_name).setLevel(numeric_level)
    logging.getLogger(__name__).info("Runtime log level changed to %s", log_level)
    return log_level


def get_runtime_log_level() -> str:
    level = logging.getLogger().getEffectiveLevel()
    return logging.getLevelName(level)


def read_log_lines(limit: int) -> tuple[list[str], int]:
    log_file_path = get_log_file_path()
    if not log_file_path.exists():
        return [], 0
    lines = log_file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:], len(lines)


def _get_file_handler(root_logger: logging.Logger) -> RotatingFileHandler | None:
    for handler in root_logger.handlers:
        if handler.get_name() == LOG_HANDLER_NAME and isinstance(
            handler,
            RotatingFileHandler,
        ):
            return handler
    return None
