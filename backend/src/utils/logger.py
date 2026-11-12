"""极简 logger 工厂。"""
from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"bidsift.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
