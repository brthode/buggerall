"""Shared logging setup.

Call `get_logger(__name__)` from any module to get a named logger. Logging is
configured exactly once (the first call wins), so handlers are never added
twice no matter how many modules import this.
"""

import logging
from typing import Final

_FORMAT: Final = "%(levelname)s %(name)s: %(message)s"
_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(level=logging.INFO, format=_FORMAT)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(name)
