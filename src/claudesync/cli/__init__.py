from typing import Any

__all__ = ["cli"]

def __getattr__(name: str) -> Any:
    if name == "cli":
        from .main import cli as _cli
        return _cli
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
