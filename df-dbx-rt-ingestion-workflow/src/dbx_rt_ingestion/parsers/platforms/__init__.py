"""Platform-specific parser packages.

One package per platform keeps releases isolated: changing platform_a code can
never regress platform_b. Each platform package exposes ``register()`` which
imports its parser modules; add new platforms to ``_PLATFORM_PACKAGES``
(or install them as separate wheels and register via entry points).
"""

from __future__ import annotations

import importlib

_PLATFORM_PACKAGES = (
    "dbx_rt_ingestion.parsers.platforms.platform_a",
)


def load_platform_parsers() -> None:
    """Import every platform package so parser registrations execute."""

    for package in _PLATFORM_PACKAGES:
        importlib.import_module(package).register()
