# SPDX-License-Identifier: Apache-2.0

"""models_runtime_manifest — public facade.

The implementation is split into submodules of this package for
maintainability (each well under 1000 lines). This __init__.py
re-exports the complete public API so existing
`from decision_engine.models_runtime_manifest import X` imports
continue to work unchanged.
"""
from decision_engine.models_runtime_manifest import (
    _enums,
    _models_admin,
    _models_basic,
    _models_release_top,
)
from decision_engine.models_runtime_manifest._enums import *  # noqa: F403
from decision_engine.models_runtime_manifest._models_admin import *  # noqa: F403
from decision_engine.models_runtime_manifest._models_basic import *  # noqa: F403
from decision_engine.models_runtime_manifest._models_release_top import *  # noqa: F403

__all__ = [
    *_enums.__all__,
    *_models_basic.__all__,
    *_models_admin.__all__,
    *_models_release_top.__all__,
]
