"""
구조화 로그 설정 (structlog + Python logging)
출력: 콘솔 + 파일 동시
로그 파일: logs/api.log, logs/ingest.log, logs/preprocess.log
"""
import logging
import logging.handlers
import sys
from pathlib import Path

import structlog

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def _build_file_handler(filename: str) -> logging.Handler:
    handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / filename,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    return handler


def setup_logging(module: str = "api") -> None:
    """
    module: "api" | "ingest" | "preprocess"
    각 module 에 맞는 로그 파일에 동시 기록
    """
    log_filename = f"{module}.log"

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    file_handler = _build_file_handler(log_filename)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)
