from __future__ import annotations

from typing import Any


def libraries(**kwargs: Any):
    from algenta.mojo_runtime import MojoRuntime

    return MojoRuntime(**kwargs).libraries()


def health(**kwargs: Any) -> dict[str, Any]:
    from algenta.mojo_runtime import MojoRuntime

    return MojoRuntime(**kwargs).health()
