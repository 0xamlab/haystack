"""
test_mojo_kernel_libraries_az.py — End-to-end tests for the compiled Mojo kernel dispatcher.

This suite differs from tests/integration/test_mojo_libraries_az.py:
  - test_mojo_libraries_az.py validates per-module `mojo run` coverage
  - this file validates the compiled `library_execute` kernel path in
    mojo_build/simulate --server

The goal is to prove the current executable runtime inventory can execute
representative calls through the kernel dispatcher, not the legacy wrapper path.

Run:
  python3 tests/integration/test_mojo_kernel_libraries_az.py
  DE_KERNEL_MOJO_TIMEOUT=15 python3 ...    # per-function timeout in seconds
  DE_KERNEL_MOJO_MODULES=ab_testing,stats python3 ...
"""

from __future__ import annotations

import ast
import copy
import importlib
import json
import math
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

mojo_inventory = importlib.import_module("apps.runtime.mojo_inventory")
mojo_binary_freshness = importlib.import_module("apps.runtime.mojo_binary_freshness")
mojo_runner = importlib.import_module("apps.runtime.mojo_library_runner")
mojo_test_gen = importlib.import_module("tests.generate_mojo_tests")

MOJO_BINARY = PROJECT_ROOT / "mojo_build" / "simulate"
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build_mojo_binary.sh"
MAIN_SOURCE = PROJECT_ROOT / "mojo" / "engine" / "main.mojo"
ENGINE_DIR = PROJECT_ROOT / "mojo" / "engine"
TIMEOUT_SECONDS = float(os.environ.get("DE_KERNEL_MOJO_TIMEOUT", "10"))
BUILD_TIMEOUT_SECONDS = float(os.environ.get("DE_KERNEL_MOJO_BUILD_TIMEOUT", "300"))
MODULE_FILTER = tuple(
    item.strip() for item in os.environ.get("DE_KERNEL_MOJO_MODULES", "").split(",") if item.strip()
)

PASS = "✅"
FAIL = "❌"

_UINT_WRAPPER_RE = re.compile(r"^UInt(?:8|16|32|64)\((\d+)\)$")
_FLOAT32_WRAPPER_RE = re.compile(r"^Float32\((.+)\)$")
_SAMPLE_VARIABLES: dict[str, Any] = {
    "_lf5": [0.5, 0.6, 0.7, 0.4, 0.3],
    "_lf6_matrix": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
    "_lf8_coalitions": [0.0, 1.0, 2.0, 4.0, 3.0, 5.0, 6.0, 9.0],
    "_li5": [1, 2, 3, 4, 5],
    "_li2_zero": [0, 1],
    "_li3": [1, 2, 3],
    "_li3_tail": [2, 3, 4],
    "_li6_grid2x3": [0, 1, 0, 1, 1, 0],
    "_li8": [1, 2, 3, 4, 5, 6, 7, 8],
    "_li10_borda": [0, 1, 2, 3, 4, 1, 0, 2, 4, 3],
    "_li16": list(range(16)),
    "_lb5": [True, False, True, True, False],
}
_SAFE_INDEX_NAMES = {
    "candidate_idx",
    "constraint_idx",
    "node",
    "start",
    "target_class",
    "user",
    "x",
}
_SAFE_SECOND_INDEX_NAMES = {"i", "item", "j", "u1", "u2", "y"}


_MANUAL_KERNEL_OVERRIDES: dict[tuple[str, str], list[Any]] = {
    ("cellular_automata", "game_of_life_step"): [
        [
            0,
            1,
            0,
            1,
            0,
            1,
            0,
            1,
            0,
            1,
            0,
            1,
            1,
            1,
            0,
            1,
            0,
            1,
            0,
            1,
            0,
            1,
            0,
            1,
            0,
        ],
        5,
        5,
        2,
        2,
    ],
    ("cellular_automata", "totalistic_rule"): [3, 17, 4],
    ("clustering_metrics", "inertia"): [
        [
            [0.0, 0.0],
            [0.1, 0.1],
            [1.0, 1.0],
            [1.1, 1.1],
            [2.0, 2.0],
        ],
        [0, 0, 1, 1, 2],
        [
            [0.05, 0.05],
            [1.05, 1.05],
            [2.0, 2.0],
        ],
    ],
    ("clustering_metrics", "davies_bouldin"): [
        [
            [0.0, 0.0],
            [0.1, 0.1],
            [1.0, 1.0],
            [1.1, 1.1],
            [2.0, 2.0],
        ],
        [0, 0, 1, 1, 2],
        3,
    ],
    ("crypto.chacha20", "quarter_round"): [
        list(range(16)),
        0,
        4,
        8,
        12,
    ],
    ("crypto.chacha20", "chacha20_init_state"): [
        list(range(8)),
        1,
        [7, 8, 9],
    ],
    ("decision_ml_fusion", "adaptive_exploration_rate"): [0.5, 2.0, 10.0, 1.41421356237],
    ("game_theory", "shapley_value_3player"): [[0.0, 1.0, 1.0, 2.0, 1.0, 2.0, 2.0, 3.0]],
    ("game_theory", "pareto_optimal_outcomes"): [
        [1.0, 2.0, 2.0, 3.0, 1.5],
        [1.0, 1.0, 2.5, 2.0, 1.4],
    ],
    ("matrix_ops", "unvec"): [
        [
            0.0,
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
            6.0,
            7.0,
            8.0,
            9.0,
            10.0,
            11.0,
            12.0,
            13.0,
            14.0,
            15.0,
            16.0,
            17.0,
            18.0,
            19.0,
            20.0,
            21.0,
            22.0,
            23.0,
            24.0,
        ],
        5,
        5,
    ],
    ("ml.naive_bayes", "gaussian_nb_predict"): [
        [
            [0.0, 1.0, 0.0, 1.0],
            [2.0, 1.0, 2.0, 1.0],
        ],
        [0.5, 0.5],
        [0.2, 0.1],
    ],
    ("ml.naive_bayes", "gaussian_nb_predict_batch"): [
        [
            [0.0, 1.0, 0.0, 1.0],
            [2.0, 1.0, 2.0, 1.0],
        ],
        [0.5, 0.5],
        [
            [0.2, 0.1],
            [1.8, 2.1],
            [0.0, 0.3],
        ],
    ],
    ("ml.random_forest", "tree_predict_simple"): [
        [
            [0.0, 0.0, 0.0],
            [0.0, 1.0, 1.0],
            [1.0, 0.0, 1.0],
            [1.0, 1.0, 2.0],
            [2.0, 1.0, 3.0],
        ],
        [0.0, 1.0, 1.5, 2.5, 3.0],
        [1.0, 0.5, 1.5],
        [0, 1, 2],
    ],
    ("ml.random_forest", "random_forest_predict"): [
        [
            [0.0, 0.0, 0.0],
            [0.0, 1.0, 1.0],
            [1.0, 0.0, 1.0],
            [1.0, 1.0, 2.0],
            [2.0, 1.0, 3.0],
        ],
        [0.0, 1.0, 1.5, 2.5, 3.0],
        [1.0, 0.5, 1.5],
        3,
        2,
    ],
    ("regression_tree", "mse_reduction"): [
        [0.0, 1.0, 2.0, 3.0, 4.0],
        [0, 1],
        [2, 3, 4],
    ],
    ("regression_tree", "best_split"): [
        [
            [0.0, 0.0],
            [0.0, 1.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [2.0, 1.0],
        ],
        [0.0, 0.5, 1.0, 1.5, 2.0],
        [0, 1, 2, 3, 4],
    ],
    ("reinforcement", "q_learning"): [
        5,
        5,
        [
            [0.0, 1.0, 0.5, 0.0, 0.2],
            [0.0, 0.5, 1.0, 0.0, 0.2],
            [0.0, 0.2, 0.5, 1.0, 0.0],
            [0.0, 0.0, 0.2, 0.5, 1.0],
            [0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        [
            [1, 2, 0, 3, 4],
            [2, 3, 1, 4, 4],
            [3, 4, 2, 4, 4],
            [4, 4, 3, 4, 4],
            [4, 4, 4, 4, 4],
        ],
        0.1,
        0.9,
        0.1,
        5,
    ],
    ("reinforcement", "sarsa"): [
        5,
        5,
        [
            [0.0, 1.0, 0.5, 0.0, 0.2],
            [0.0, 0.5, 1.0, 0.0, 0.2],
            [0.0, 0.2, 0.5, 1.0, 0.0],
            [0.0, 0.0, 0.2, 0.5, 1.0],
            [0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        [
            [1, 2, 0, 3, 4],
            [2, 3, 1, 4, 4],
            [3, 4, 2, 4, 4],
            [4, 4, 3, 4, 4],
            [4, 4, 4, 4, 4],
        ],
        0.1,
        0.9,
        0.1,
        5,
    ],
    ("reinforcement", "value_iteration"): [
        5,
        5,
        [
            [0.0, 1.0, 0.5, 0.0, 0.2],
            [0.0, 0.5, 1.0, 0.0, 0.2],
            [0.0, 0.2, 0.5, 1.0, 0.0],
            [0.0, 0.0, 0.2, 0.5, 1.0],
            [0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        [
            [1, 2, 0, 3, 4],
            [2, 3, 1, 4, 4],
            [3, 4, 2, 4, 4],
            [4, 4, 3, 4, 4],
            [4, 4, 4, 4, 4],
        ],
        0.9,
        1e-6,
    ],
    ("reinforcement", "policy_evaluation"): [
        [0, 1, 2, 3, 4],
        5,
        [
            [0.0, 1.0, 0.5, 0.0, 0.2],
            [0.0, 0.5, 1.0, 0.0, 0.2],
            [0.0, 0.2, 0.5, 1.0, 0.0],
            [0.0, 0.0, 0.2, 0.5, 1.0],
            [0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        [
            [1, 2, 0, 3, 4],
            [2, 3, 1, 4, 4],
            [3, 4, 2, 4, 4],
            [4, 4, 3, 4, 4],
            [4, 4, 4, 4, 4],
        ],
        0.9,
        1e-6,
    ],
    ("rlhf_dpo", "orpo_ratio"): [-0.2, -1.0, 10.0, 12.0, 0.1],
    ("sorting", "nth_smallest"): [[0.5, 0.6, 0.7, 0.4, 0.3], 2],
    ("sparse_attention", "local_window_mask"): [10.0, 12.0, 3.0, 0.0],
    ("vector_kernels.dot", "dot64_f32"): [[0.5 for _ in range(64)], [0.25 for _ in range(64)]],
    ("vector_kernels.dot", "l2_norm_inv_f32"): [[0.5 for _ in range(64)]],
    ("vector_kernels.dot", "cosine64_f32"): [
        [0.5 for _ in range(64)],
        [0.25 for _ in range(64)],
        0.25,
        0.5,
    ],
    ("vector_kernels.dot", "build_vec64_f32"): ["test vector", [0.0 for _ in range(64)]],
    ("vector_kernels.table", "source_id_of"): ["pos"],
    ("voting", "borda_score"): [
        [
            0,
            1,
            2,
            3,
            4,
            1,
            0,
            2,
            4,
            3,
        ],
        5,
        2,
    ],
    ("voting", "condorcet_pairwise"): [7, 5],
}


@dataclass(frozen=True)
class KernelFunctionTarget:
    module_name: str
    module_id: str
    function_name: str
    args: list[Any]
    return_type: str


@dataclass(frozen=True)
class KernelCallResult:
    module_name: str
    function_name: str
    passed: bool
    elapsed_ms: float
    detail: str


def _recv_frame(sock: socket.socket) -> dict[str, object]:
    header = sock.recv(4)
    if len(header) < 4:
        raise RuntimeError("short frame header from Mojo kernel server")
    frame_len = struct.unpack(">I", header)[0]
    payload = bytearray()
    while len(payload) < frame_len:
        chunk = sock.recv(frame_len - len(payload))
        if not chunk:
            raise RuntimeError("unexpected EOF from Mojo kernel server")
        payload.extend(chunk)
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise RuntimeError(f"kernel returned non-object response: {decoded!r}")
    return decoded


def _send_frame(sock: socket.socket, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    sock.sendall(struct.pack(">I", len(body)) + body)
    return _recv_frame(sock)


def _expr_to_python_value(expr: str) -> Any:
    if expr in _SAMPLE_VARIABLES:
        return copy.deepcopy(_SAMPLE_VARIABLES[expr])
    uint_match = _UINT_WRAPPER_RE.match(expr)
    if uint_match is not None:
        return int(uint_match.group(1))
    float32_match = _FLOAT32_WRAPPER_RE.match(expr)
    if float32_match is not None:
        return float(ast.literal_eval(float32_match.group(1)))
    return ast.literal_eval(expr)


def _default_scalar_value(type_name: str) -> Any:
    if type_name == "Bool":
        return True
    if type_name in {"Float32", "Float64"}:
        return 0.5
    if type_name == "Int":
        return 5
    if type_name == "UInt8":
        return 8
    if type_name in {"UInt16", "UInt32", "UInt64"}:
        return 42
    if type_name == "String":
        return "test"
    raise ValueError(f"Unsupported scalar runtime type '{type_name}'.")


def _default_list_value(inner_type: str) -> list[Any]:
    if inner_type == "Bool":
        return copy.deepcopy(_SAMPLE_VARIABLES["_lb5"])
    if inner_type == "String":
        return ["test", "alpha", "beta"]
    if inner_type in {"Float32", "Float64"}:
        return copy.deepcopy(_SAMPLE_VARIABLES["_lf5"])
    if inner_type == "Int":
        return copy.deepcopy(_SAMPLE_VARIABLES["_li5"])
    if inner_type == "UInt8":
        return [1, 2, 3, 4, 5]
    if inner_type in {"UInt16", "UInt32", "UInt64"}:
        return [1, 2, 3, 4, 5]
    sample = _default_value(inner_type)
    return [copy.deepcopy(sample) for _ in range(5)]


def _index_vector() -> list[int]:
    return [0, 1, 2, 3, 4]


def _ballot_matrix() -> list[list[int]]:
    return [
        [0, 1, 2, 3, 4],
        [1, 2, 3, 4, 0],
        [2, 3, 4, 0, 1],
        [3, 4, 0, 1, 2],
        [4, 0, 1, 2, 3],
    ]


def _binary_matrix() -> list[list[int]]:
    return [
        [0, 1, 1, 0, 1],
        [1, 0, 1, 1, 0],
        [1, 1, 0, 1, 0],
        [0, 1, 1, 0, 1],
        [1, 0, 0, 1, 0],
    ]


def _flat_vector(type_name: str, size: int) -> list[Any]:
    if type_name == "Int":
        base = _index_vector()
    elif type_name in {"Float32", "Float64"}:
        base = copy.deepcopy(_SAMPLE_VARIABLES["_lf5"])
    elif type_name == "Bool":
        base = copy.deepcopy(_SAMPLE_VARIABLES["_lb5"])
    elif type_name == "String":
        base = ["test", "alpha", "beta", "gamma", "delta"]
    else:
        base = [copy.deepcopy(_default_value(type_name)) for _ in range(5)]
    values: list[Any] = []
    while len(values) < size:
        values.extend(copy.deepcopy(base))
    return values[:size]


def _default_value(type_name: str) -> Any:
    if mojo_inventory._is_list_type(type_name):
        inner_type = mojo_inventory._list_inner_type(type_name)
        return _default_list_value(inner_type)
    return _default_scalar_value(type_name)


def _vector_length(value: Any) -> int | None:
    if not isinstance(value, list):
        return None
    if value and all(not isinstance(item, list) for item in value):
        return len(value)
    return None


def _matrix_shape(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, list) or not value:
        return None
    if not all(isinstance(row, list) for row in value):
        return None
    first_row = value[0]
    if not isinstance(first_row, list):
        return None
    return len(value), len(first_row)


def _default_args_for_function(function_spec: Any) -> list[Any]:
    args: list[Any] = []
    vector_len: int | None = None
    matrix_shape: tuple[int, int] | None = None
    has_flat_grid = {param.name for param in function_spec.params} >= {"rows", "cols"} or {
        param.name for param in function_spec.params
    } >= {"height", "width"}
    for param in function_spec.params:
        value: Any
        if param.typ == "List[Int]" and param.name in {
            "parent",
            "ranks",
            "tour",
            "votes",
            "indices",
            "seeds",
        }:
            value = _index_vector()
        elif param.typ == "List[List[Int]]" and param.name == "ballots":
            value = _ballot_matrix()
        elif param.typ == "List[List[Int]]" and param.name in {"adj", "approvals"}:
            value = _binary_matrix()
        elif (
            has_flat_grid
            and param.typ in {"List[Int]", "List[Float64]", "List[Float32]"}
            and vector_len is None
        ):
            inner_type = mojo_inventory._list_inner_type(param.typ)
            value = _flat_vector(inner_type, 25)
        elif param.typ == "Int" and param.name == "lo" and vector_len is not None:
            value = 0
        elif param.typ == "Int" and param.name == "hi" and vector_len is not None:
            value = max(vector_len - 1, 0)
        elif param.typ == "Int" and param.name in _SAFE_INDEX_NAMES:
            value = 0
        elif param.typ == "Int" and param.name in _SAFE_SECOND_INDEX_NAMES:
            value = 1
        elif param.typ == "Int" and param.name in {"n", "size", "count", "length"}:
            if vector_len is not None:
                value = vector_len
            elif matrix_shape is not None:
                value = matrix_shape[0]
            else:
                value = _default_value(param.typ)
        elif param.typ == "Int" and param.name == "rows" and matrix_shape is not None:
            value = matrix_shape[0]
        elif param.typ == "Int" and param.name == "cols" and matrix_shape is not None:
            value = matrix_shape[1]
        elif param.typ == "Int" and param.name in {"p", "percentile"}:
            value = 50
        else:
            value = _default_value(param.typ)
        args.append(value)
        if vector_len is None:
            vector_len = _vector_length(value)
        if matrix_shape is None:
            matrix_shape = _matrix_shape(value)
    return args


def _generator_argument_overrides() -> dict[tuple[str, str], list[Any]]:
    overrides: dict[tuple[str, str], list[Any]] = {}
    for target, sigs in mojo_test_gen.build_generation_plan():
        for sig in sigs:
            testable, args = mojo_test_gen._is_testable(sig)
            if not testable or args is None:
                continue
            overrides[(target.import_path, sig.name)] = [
                _expr_to_python_value(arg_expr) for arg_expr in args
            ]
    return overrides


def _build_kernel_targets() -> list[KernelFunctionTarget]:
    overrides = _generator_argument_overrides()
    runtime_modules = mojo_inventory.discover_runtime_library_modules(executable_only=True)
    targets: list[KernelFunctionTarget] = []
    for module in runtime_modules:
        if (
            MODULE_FILTER
            and module.import_path not in MODULE_FILTER
            and module.lib_id not in MODULE_FILTER
        ):
            continue
        for function in module.functions:
            key = (module.import_path, function.name)
            args = copy.deepcopy(_MANUAL_KERNEL_OVERRIDES.get(key))
            if args is None:
                args = overrides.get(key)
            if args is None:
                args = _default_args_for_function(function)
            targets.append(
                KernelFunctionTarget(
                    module_name=module.import_path,
                    module_id=module.lib_id,
                    function_name=function.name,
                    args=args,
                    return_type=function.return_type,
                )
            )
    return targets


def _result_is_valid(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_result_is_valid(item) for item in value)
    return True


def _result_summary(value: Any) -> str:
    if isinstance(value, list):
        return f"list(len={len(value)})"
    return repr(value)


class MojoKernelServer:
    def __init__(self) -> None:
        self._tmpdir = Path(tempfile.mkdtemp(prefix="algenta-kernel-az-"))
        self._socket_path = self._tmpdir / "kernel.sock"
        self._log_path = self._tmpdir / "kernel.log"
        self._build_log_path = self._tmpdir / "build.log"
        self._proc: subprocess.Popen[str] | None = None
        self._binary_path = MOJO_BINARY

    @property
    def socket_path(self) -> Path:
        return self._socket_path

    @property
    def binary_path(self) -> Path:
        return self._binary_path

    def _build_filtered_binary(self) -> Path:
        temp_main = self._tmpdir / "main.mojo"
        temp_dispatch = self._tmpdir / "runtime_library_dispatch_generated.mojo"
        temp_object = self._tmpdir / "simulate.o"
        temp_binary = self._tmpdir / "simulate"
        temp_object_tmp = self._tmpdir / "simulate.o.tmp"
        temp_binary_tmp = self._tmpdir / "simulate.tmp"

        temp_main.write_text(MAIN_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
        build_env = {
            **os.environ,
            "MOJO_SRC": str(temp_main),
            "DISPATCH_OUTPUT_PATH": str(temp_dispatch),
            "ENGINE_INCLUDE_DIR": str(ENGINE_DIR),
            "OBJECT_PATH": str(temp_object),
            "BINARY_PATH": str(temp_binary),
            "TEMP_OBJECT_PATH": str(temp_object_tmp),
            "TEMP_BINARY_PATH": str(temp_binary_tmp),
            "MOJO_RUNTIME_MODULE_FILTER": ",".join(MODULE_FILTER),
        }
        try:
            result = subprocess.run(  # noqa: S603
                ["bash", str(BUILD_SCRIPT)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=BUILD_TIMEOUT_SECONDS,
                env=build_env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                "Timed out building filtered Mojo kernel binary for modules "
                f"{', '.join(MODULE_FILTER)} after {BUILD_TIMEOUT_SECONDS:.0f}s."
            ) from exc

        build_output = (result.stdout or "") + (result.stderr or "")
        self._build_log_path.write_text(build_output, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError(
                "Filtered Mojo kernel build failed.\n"
                + self._read_tail(self._build_log_path, label="build log")
            )
        if not temp_binary.exists():
            raise RuntimeError(
                "Filtered Mojo kernel build reported success but did not produce a binary.\n"
                + self._read_tail(self._build_log_path, label="build log")
            )
        return temp_binary

    def start(self) -> None:
        freshness = mojo_binary_freshness.inspect_mojo_binary_freshness(MOJO_BINARY)
        if freshness.exists and freshness.is_fresh:
            self._binary_path = MOJO_BINARY
        elif MODULE_FILTER:
            self._binary_path = self._build_filtered_binary()
        elif not freshness.exists:
            raise RuntimeError(
                f"Compiled Mojo kernel binary not found at {MOJO_BINARY}. "
                "Build it before running the kernel A-Z suite."
            )
        else:
            raise RuntimeError(freshness.failure_message())
        if self._socket_path.exists():
            self._socket_path.unlink()
        log_handle = self._log_path.open("w", encoding="utf-8")
        self._proc = subprocess.Popen(  # noqa: S603
            [str(self._binary_path), "--server", str(self._socket_path)],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log_handle.close()
        deadline = time.monotonic() + 10.0
        while not self._socket_path.exists():
            if self._proc.poll() is not None:
                raise RuntimeError(
                    f"Mojo kernel server exited before opening its socket.\n{self._read_log_tail()}"
                )
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Timed out waiting for Mojo kernel server socket.\n{self._read_log_tail()}"
                )
            time.sleep(0.01)

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=2.0)
        self._proc = None
        if self._socket_path.exists():
            self._socket_path.unlink()

    def restart(self) -> None:
        self.stop()
        self.start()

    def close(self) -> None:
        self.stop()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def call(self, payload: dict[str, object]) -> dict[str, object]:
        if self._proc is None or self._proc.poll() is not None:
            raise RuntimeError(f"Mojo kernel server is not running.\n{self._read_log_tail()}")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(TIMEOUT_SECONDS)
            sock.connect(str(self._socket_path))
            ready = _recv_frame(sock)
            if ready != {"status": "ready"}:
                raise RuntimeError(f"unexpected kernel handshake: {ready!r}")
            return _send_frame(sock, payload)

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _read_log_tail(self) -> str:
        return self._read_tail(self._log_path, label="kernel log")

    def _read_tail(self, path: Path, *, label: str) -> str:
        if not path.exists():
            return f"(no {label} output)"
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = "\n".join(lines[-20:])
        return tail or f"(no {label} output)"


def _execute_kernel_target(
    server: MojoKernelServer,
    target: KernelFunctionTarget,
) -> KernelCallResult:
    started = time.perf_counter()
    try:
        function_spec, payload = mojo_runner.build_runtime_library_worker_request(
            target.module_name,
            target.function_name,
            target.args,
        )
        raw = server.call(payload)
        result = mojo_runner.parse_runtime_library_worker_response(
            target.module_name,
            target.function_name,
            raw,
            function_spec=function_spec,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        if not _result_is_valid(result):
            return KernelCallResult(
                module_name=target.module_name,
                function_name=target.function_name,
                passed=False,
                elapsed_ms=elapsed_ms,
                detail=f"non-finite result: {_result_summary(result)}",
            )
        return KernelCallResult(
            module_name=target.module_name,
            function_name=target.function_name,
            passed=True,
            elapsed_ms=elapsed_ms,
            detail=_result_summary(result),
        )
    except (TimeoutError, ConnectionError, BrokenPipeError, OSError) as exc:
        server.restart()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return KernelCallResult(
            module_name=target.module_name,
            function_name=target.function_name,
            passed=False,
            elapsed_ms=elapsed_ms,
            detail=f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:  # noqa: BLE001
        if not server.is_running():
            server.restart()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return KernelCallResult(
            module_name=target.module_name,
            function_name=target.function_name,
            passed=False,
            elapsed_ms=elapsed_ms,
            detail=f"{type(exc).__name__}: {exc}",
        )


def main() -> int:
    targets = _build_kernel_targets()
    if not targets:
        print("No kernel-dispatch targets found.")
        return 1

    modules = sorted({target.module_name for target in targets})
    print("=" * 70)
    print("  Mojo Kernel A-Z — Compiled Dispatcher Function Tests")
    print("=" * 70)
    print(f"  Modules:    {len(modules)}")
    print(f"  Functions:  {len(targets)}")
    print(f"  Timeout:    {TIMEOUT_SECONDS:.1f}s per function")
    print(f"  Binary:     {MOJO_BINARY}")
    if MODULE_FILTER:
        print(f"  Filter:     {', '.join(MODULE_FILTER)}")
    print("=" * 70)

    by_module: dict[str, list[KernelFunctionTarget]] = {}
    for target in targets:
        by_module.setdefault(target.module_name, []).append(target)

    suite_started = time.perf_counter()
    failures: list[KernelCallResult] = []
    server = MojoKernelServer()
    server.start()
    print(f"  Runtime:    {server.binary_path}")
    try:
        for module_name in sorted(by_module):
            module_targets = by_module[module_name]
            passed = 0
            failed = 0
            module_started = time.perf_counter()
            for target in module_targets:
                result = _execute_kernel_target(server, target)
                if result.passed:
                    passed += 1
                else:
                    failed += 1
                    failures.append(result)
            elapsed_ms = round((time.perf_counter() - module_started) * 1000, 0)
            icon = PASS if failed == 0 else FAIL
            print(
                f"  {icon}  {module_name:<40}  pass={passed:<4} fail={failed:<3} ({elapsed_ms:.0f}ms)"
            )
    finally:
        server.close()

    duration_s = time.perf_counter() - suite_started
    passed_total = len(targets) - len(failures)
    failed_total = len(failures)
    passed_modules = len(modules) - len({failure.module_name for failure in failures})
    failed_modules = len(modules) - passed_modules

    print()
    print("=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)
    print(
        f"  Modules:   {len(modules)} total  {PASS} {passed_modules} passed  {FAIL} {failed_modules} failed"
    )
    print(f"  Functions: {len(targets)} total  {PASS} {passed_total}  {FAIL} {failed_total}")
    print(f"  Duration:  {duration_s:.1f}s")

    if failures:
        print()
        print("=" * 70)
        print("  FAILED FUNCTIONS — detailed output")
        print("=" * 70)
        for failure in failures[:200]:
            print(
                f"  {FAIL} {failure.module_name}::{failure.function_name}  "
                f"({failure.elapsed_ms:.2f}ms)  {failure.detail}"
            )
        remaining = len(failures) - 200
        if remaining > 0:
            print(f"  ... {remaining} more failure(s) omitted")
        print()
        print(f"  {FAIL} {failed_total} kernel-dispatch function test(s) failed\n")
        return 1

    print()
    print(
        f"  {PASS} ALL KERNEL TESTS PASSED — {passed_total} functions across {passed_modules} modules\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
