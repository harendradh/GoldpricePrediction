"""Registry behavior: registration, lookup, duplicates, errors."""

from __future__ import annotations

import pytest

from dbx_rt_ingestion.core.exceptions import ConfigurationError
from dbx_rt_ingestion.core.registry import Registry


class Base:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def test_register_and_create() -> None:
    registry: Registry[Base] = Registry("thing")

    @registry.register("Alpha")
    class Alpha(Base):
        pass

    assert "alpha" in registry  # case-insensitive
    instance = registry.create("ALPHA", value=7)
    assert isinstance(instance, Alpha)
    assert instance.value == 7


def test_unknown_name_lists_available() -> None:
    registry: Registry[Base] = Registry("thing")

    @registry.register("known")
    class Known(Base):
        pass

    with pytest.raises(ConfigurationError) as exc:
        registry.get("missing")
    assert "known" in str(exc.value)


def test_duplicate_registration_rejected() -> None:
    registry: Registry[Base] = Registry("thing")

    @registry.register("dup")
    class First(Base):
        pass

    with pytest.raises(ConfigurationError):

        @registry.register("dup")
        class Second(Base):
            pass


def test_reregistering_same_class_is_idempotent() -> None:
    registry: Registry[Base] = Registry("thing")

    class Same(Base):
        pass

    registry.register("same")(Same)
    registry.register("same")(Same)  # module re-import must not explode
    assert registry.names() == ["same"]
