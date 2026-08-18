"""
Codna Decision Engine — Mojo Simulation Core v0.8.0
Dispatch-only entry point (Phase 7). All engine logic lives in engines/ subdirectory.

Server loop uses native Mojo Unix domain sockets (net/unix_socket.mojo) and
native JSON parsing (json/parser.mojo) — zero Python in the hot path.

Build:
  cd mojo_env && pixi run mojo build ../mojo/engine/main.mojo -o ../mojo_build/simulate

Run (subprocess):
  echo '{"engine_type":"monte_carlo","runs":10000,...}' | ./mojo_build/simulate

Run (server mode):
  ./mojo_build/simulate --server /tmp/algenta-mojo/worker-0.sock
"""
from std.python import Python, PythonObject
from std.sys import info, argv as mojo_argv

from python_bridge  import fast_int, py_str
from request_parser import parse_request

# Native socket + JSON imports (zero Python)
from net.unix_socket import (
    libc_socket_unix, libc_bind_unix, libc_listen, libc_accept,
    libc_close, libc_unlink, libc_path_exists,
    send_frame, recv_frame,
)
from json.parser import json_get_string

# Engine imports
from engines.monte_carlo   import run_monte_carlo
from engines.scenario      import run_scenario
from engines.bootstrap     import run_bootstrap
from engines.sensitivity   import run_sensitivity
from engines.mcmc          import run_mcmc
from engines.lhs           import run_lhs
from engines.qmc_sobol     import run_qmc_sobol
from compare               import run_compare
from decision_tree         import run_decision_tree
from time_series           import run_time_series
from importance_sampling   import run_importance_sampling
from engines.field_map          import run_field_map
from engines.column_ranker      import (
    ResidentColumnRankState,
    run_column_rank,
)
from engines.column_profiler    import run_column_profile
from engines.column_matcher     import run_column_match
from engines.join_detector      import run_join_detect
from engines.relation_detector  import run_relation_detect
from engines.repo_classifier    import run_repo_classifier
from engines.string_similarity  import run_string_similarity
from runtime_library_dispatch_generated import dispatch_runtime_library
from algenta_runtime.batch import run_batch_execute
from algenta_runtime.pipeline import run_pipeline_execute
from algenta_runtime.query import run_query
from algenta_runtime.session import ResidentDatasets
from algenta_runtime.stream import ResidentStreams


def _run_raw(raw: String) raises -> String:
    """
    Single dispatch entry point. Calls parse_request() once (single Python boundary),
    then routes to the appropriate engine module — no PythonObject in engine hot loops.
    """
    var req = parse_request(raw)
    var et  = req.engine_type

    if et == "field_map":
        return run_field_map(raw)
    elif et == "column_rank":
        return run_column_rank(raw)
    elif et == "column_profile":
        return run_column_profile(raw)
    elif et == "column_match":
        return run_column_match(raw)
    elif et == "join_detect":
        return run_join_detect(raw)
    elif et == "relation_detect":
        return run_relation_detect(raw)
    elif et == "repo_classifier":
        return run_repo_classifier(raw)
    elif et == "string_similarity":
        return run_string_similarity(raw)
    elif et == "importance_sampling":
        return run_importance_sampling(req)
    elif et == "compare":
        # compare.mojo needs the raw JSON to iterate scenarios array
        var mutable_req = req.copy()
        mutable_req.obj_fn = raw  # pass raw JSON for scenario re-parse
        return run_compare(mutable_req)
    elif et == "decision_tree":
        return run_decision_tree(req)
    elif et == "time_series":
        return run_time_series(req)
    elif et == "scenario":
        return run_scenario(req)
    elif et == "bootstrap":
        return run_bootstrap(req)
    elif et == "sensitivity":
        return run_sensitivity(req)
    elif et == "mcmc":
        return run_mcmc(req)
    elif et == "lhs":
        return run_lhs(req)
    elif et == "qmc_sobol":
        return run_qmc_sobol(req)
    else:
        # Default: monte_carlo (handles parallel, sequential, streaming, Cholesky)
        return run_monte_carlo(req)


def run_server_loop(socket_path: String) raises:
    """Long-lived Unix socket server loop using native Mojo libc FFI.

    Zero Python imports — uses send_frame/recv_frame from net/unix_socket.mojo
    and json_get_string from json/parser.mojo for message type parsing.
    Wire protocol: [4-byte big-endian uint32 length][UTF-8 JSON payload].
    """
    # Cleanup old socket file if it exists
    if libc_path_exists(socket_path):
        libc_unlink(socket_path)

    # Create, bind, listen
    var server_fd = libc_socket_unix()
    if server_fd < 0:
        print('{"error":"failed to create socket"}')
        return
    libc_bind_unix(server_fd, socket_path)
    libc_listen(server_fd, 1)

    var resident_column_rank = ResidentColumnRankState()
    # Sibling of resident_column_rank: connection-scoped, dropped when the loop
    # exits, so a handle can never outlive the connection that opened it.
    var resident_datasets = ResidentDatasets()
    var resident_streams = ResidentStreams()
    var keep_running = True
    while keep_running:
        var conn_fd = libc_accept(server_fd)
        if conn_fd < 0:
            continue

        # Send ready handshake
        send_frame(conn_fd, '{"status":"ready"}')

        while True:
            var raw = recv_frame(conn_fd)
            if raw.byte_length() == 0:
                break

            var response: String
            var msg_type = json_get_string(raw, "type")
            if msg_type.byte_length() == 0:
                msg_type = json_get_string(raw, "engine_type")
            if msg_type.byte_length() == 0:
                msg_type = "request"

            if msg_type == "shutdown":
                response = '{"status":"bye"}'
                keep_running = False
            elif msg_type == "ping":
                response = '{"status":"ok"}'
            elif msg_type == "column_rank_init":
                response = resident_column_rank.init_from_json(raw)
            elif msg_type == "column_rank_query":
                response = resident_column_rank.run_query(raw)
            elif msg_type == "column_rank_batch":
                response = resident_column_rank.run_batch(raw)
            elif msg_type == "library_execute":
                response = dispatch_runtime_library(raw)
            elif msg_type == "batch_execute":
                response = run_batch_execute(
                    dispatch_runtime_library, raw, resident_datasets
                )
            elif msg_type == "pipeline_execute":
                response = run_pipeline_execute(
                    dispatch_runtime_library, raw, resident_datasets
                )
            elif msg_type == "query_execute":
                response = run_query(raw, resident_datasets)
            elif msg_type == "dataset_open":
                response = resident_datasets.open_from_json(raw)
            elif msg_type == "dataset_close":
                response = resident_datasets.close_from_json(raw)
            elif msg_type == "dataset_list":
                response = resident_datasets.list_json()
            elif msg_type == "stream_open":
                response = resident_streams.open_from_json(raw, resident_datasets)
            elif msg_type == "stream_next":
                response = resident_streams.next_from_json(raw, resident_datasets)
            elif msg_type == "stream_close":
                response = resident_streams.close_from_json(raw)
            else:
                try:
                    response = _run_raw(raw)
                except:
                    response = '{"error":"mojo worker dispatch failed"}'

            send_frame(conn_fd, response)

            if not keep_running:
                break

        libc_close(conn_fd)

    libc_close(server_fd)
    if libc_path_exists(socket_path):
        libc_unlink(socket_path)


def main() raises:
    """Entry point. Uses Mojo native sys.argv for CLI args (works in compiled binaries).

    Python sys is only imported for stdin.read() in subprocess mode.
    The server loop and all engine dispatch are 100% Python-free.
    """
    # Use Mojo native argv — Python sys.argv is empty in compiled binaries
    var args = mojo_argv()
    var argc = len(args)

    if argc >= 3 and String(args[1]) == "--server":
        run_server_loop(String(args[2]))
        return

    # Subprocess mode: read JSON from stdin via Python (only time Python is needed)
    var sys_m = Python.import_module("sys")
    var raw = py_str(sys_m.stdin.read())
    var out = _run_raw(raw)
    if out.byte_length() > 0:
        print(out)
