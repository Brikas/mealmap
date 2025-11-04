import logging
import typing
from collections import defaultdict

from loguru import logger


def setup_logging() -> None:
    """Set up logging configuration."""
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)
    # logger.add(sys.stdout, format="{time} {level} {message}", level="INFO")
    # logger.add(sys.stdout, serialize=True)
    # If you want to intercept logs from specific loggers instead of the root logger:
    # loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    # for _logger in loggers:
    #     _logger.handlers = [InterceptHandler()]


class InterceptHandler(logging.Handler):
    """Custom logging handler that intercepts log messages."""

    log_counts: typing.ClassVar[defaultdict[str, int]] = defaultdict(
        int
    )  # Counter for log messages

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record."""
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Increment the count for the specific log level
        InterceptHandler.log_counts[str(level)] += 1

        # Find caller from where the logged message originated
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )
