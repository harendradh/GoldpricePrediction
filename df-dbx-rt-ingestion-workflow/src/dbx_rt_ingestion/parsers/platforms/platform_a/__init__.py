"""Platform A parsers (GBS Auth Data Migration reference platform).

Every parser in this package registers under the ``platform_a.`` namespace.
"""

from __future__ import annotations


def register() -> None:
    """Import parser modules so their registry registrations execute."""

    from dbx_rt_ingestion.parsers.platforms.platform_a import account_parser  # noqa: F401
