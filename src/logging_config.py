import logging

from rich.logging import RichHandler


def setup_logging(level: int = logging.INFO) -> None:
    handler = RichHandler(
        show_time=True,
        show_path=False,
        markup=False,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
    )
    handler.setFormatter(logging.Formatter("%(name)s | %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.addHandler(handler)
        uv_logger.propagate = False
