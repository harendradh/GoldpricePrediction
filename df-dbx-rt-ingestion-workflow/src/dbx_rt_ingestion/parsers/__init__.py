"""Pluggable parser framework.

Layout:
    parsers/common/       format parsers shared by all platforms
    parsers/platforms/    one package per platform (isolated release units)

Platform parsers register with dotted names (``platform_a.account``) so specs
address them unambiguously and platforms never collide.
"""

from dbx_rt_ingestion.parsers.base import parser_registry

__all__ = ["parser_registry", "load_builtin_parsers"]


def load_builtin_parsers() -> None:
    """Import built-in and platform parsers so registrations execute."""

    from dbx_rt_ingestion.parsers.common import (  # noqa: F401
        avro_parser,
        binary_parser,
        delimited_parser,
        fixed_width_parser,
        json_parser,
        text_parser,
        xml_parser,
    )
    from dbx_rt_ingestion.parsers.platforms import load_platform_parsers

    load_platform_parsers()
