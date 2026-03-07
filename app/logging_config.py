"""Logging setup for the application."""

import logging


def setup_logging(log_level: str) -> None:
    """Configure application-wide logging format and level."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
