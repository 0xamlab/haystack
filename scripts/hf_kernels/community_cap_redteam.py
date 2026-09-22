#!/usr/bin/env python3
"""Publish gate for ABI §9 — red-team the compiled Community worker cap (device-wide single worker).

Proves, on a BUILT family library, that no scenario obtains more than one concurrent native worker
per device: 4 processes, 4 threads on one handle, two library instances (two families), fork-after-
load, hostile environment variables; plus crash-safety (SIGKILL the holder -> next call proceeds),
queueing (a call while the slot is held returns a clean result) and that the lock anchor cannot be
unlinked by the user.

Metric: total WALL time vs the serialised sum of warm heavy calls. With one device-wide worker, N
participants making T calls need wall ≈ T×single; with N parallel workers, wall ≈ T×single/N. Every
process warms up first (cold start excluded) and every response is validated — an error is a
correctness failure, never mistaken for a bypass. This is the only metric that a BLOCKING lock cannot
fool: counting calls mis-reads cheap error paths as work, and timing call windows mis-reads queued
WAITING as parallel execution (both were observed and rejected while designing this gate).

Usage:
  scripts/hf_kernels/community_cap_redteam.py <libalgenta_<family>.(dylib|so)> <request.json>
If <request.json> does not exist it is generated: distribution_fit.fit_normal over a 200k-element
seeded array (~100 ms warm on Apple M-series), which any family that ships `distribution_fit` accepts.
Calls go through ctypes straight into the library, so the Python glue's lock is deliberately absent.
Exit 0 only when every scenario reports ≤ 1.0 effective workers.
"""

import ctypes, json, os, sys, time, glob, shutil, subprocess, threading, tempfile, errno
HERE=os.path.dirname(os.path.abspath(__file__)); MODNAME=os.path.splitext(os.path.basename(__file__))[0]; K=int(os.environ.get("RT_K","4"))
def load(p):
    # The Hub cache is symlinks into blobs/ and dyld resolves dependencies against the REAL path, so
    # preload the runtime closure by name in manifest load_order first (exactly what _native.py does).
    d=os.path.dirname(os.path.abspath(p)); m=os.path.join(d,"manifest.json")
    if os.path.exists(m):
        try:
            with open(m) as mf: lo=json.load(mf).get("load_order",[])
            for name in lo:
                q=os.path.join(d,name)
                if os.path.exists(q) and os.path.abspath(q)!=os.path.abspath(p): ctypes.CDLL(q, mode=ctypes.RTLD_GLOBAL)
        except Exception: pass  # a flat local build needs no preload; never mask the real load error
    l=ctypes.CDLL(p); l.algenta_runtime_version.restype=ctypes.c_int32
    l.algenta_runtime_init.argtypes=[ctypes.c_void_p]; l.algenta_runtime_init.restype=ctypes.c_void_p
    l.algenta_runtime_execute.argtypes=[ctypes.c_void_p,ctypes.c_void_p]; l.algenta_runtime_execute.restype=ctypes.c_void_p
    l.algenta_runtime_free.argtypes=[ctypes.c_void_p]; l.algenta_runtime_shutdown.argtypes=[ctypes.c_void_p]; assert l.algenta_runtime_version()==1; return l
def call(l,h,req):
    p=l.algenta_runtime_execute(h,req)
    if not p: return False  # ABI 4.4: NULL = response could not be allocated; never string_at(NULL)
    r=ctypes.string_at(p); l.algenta_runtime_free(p); return (b'"error"' not in r) and (b'result' in r)
def timed(l,h,req,k):
    call(l,h,req)  # warm-up (cold start excluded)
    t0=time.monotonic(); err=sum(0 if call(l,h,req) else 1 for _ in range(k)); t1=time.monotonic()
    return {"start":t0,"end":t1,"n":k,"err":err}
def child(path,reqf,k,env=None,fork=False):
    code=f"""
import sys,os,json,importlib; sys.path.insert(0,{HERE!r}); r=importlib.import_module({MODNAME!r})
req=open({reqf!r},'rb').read(); l=r.load({path!r}); h=l.algenta_runtime_init(None)
if {fork!r}:
    r.call(l,h,req); rd,wr=os.pipe(); pid=os.fork()
    if pid==0:
        os.close(rd); os.write(wr,json.dumps(r.timed(l,h,req,{k})).encode()); os._exit(0)
    os.close(wr); me=r.timed(l,h,req,{k}); c=json.loads(os.read(rd,1<<16)); os.waitpid(pid,0); print(json.dumps({{"parts":[me,c]}}))
else: print(json.dumps({{"parts":[r.timed(l,h,req,{k})]}}))
"""
    e=dict(os.environ); e.update(env or {})
    return subprocess.Popen([sys.executable,"-c",code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=e)
def gather(ps):
    parts=[]
    for p in ps:
        o,e=p.communicate(timeout=900); ln=o.strip().splitlines()
        if not ln: raise RuntimeError("child died:\n"+e[-1500:])
        parts+=json.loads(ln[-1])["parts"]
    return parts
results=[]
def verdict(name,parts,single):
    T=sum(p["n"] for p in parts); errs=sum(p["err"] for p in parts)
    wall=max(p["end"] for p in parts)-min(p["start"] for p in parts); serial=T*single; ratio=wall/serial
    workers=serial/wall  # effective concurrent workers observed
    v="ERRORS ❌" if errs else ("CAPPED ✅ (1 worker)" if ratio>=0.80 else ("BYPASSED ❌" if ratio<0.60 else "INCONCLUSIVE ⚠️"))
    results.append((name,v)); print(f"{name:<50} calls={T:>2} err={errs} wall={wall:5.2f}s serial={serial:5.2f}s  effective_workers={workers:4.2f}  {v}")
def hold(sec):
    p=subprocess.Popen([sys.executable,"-c",f"import os,fcntl,time;fd=os.open('/dev/null',os.O_RDONLY);fcntl.flock(fd,fcntl.LOCK_EX);print('held',flush=True);time.sleep({sec})"],stdout=subprocess.PIPE,text=True); p.stdout.readline(); return p
def _ensure_request(reqf):
    if os.path.exists(reqf): return
    import random; random.seed(1); big=[random.random() for _ in range(200_000)]
    open(reqf,"wb").write(json.dumps({"type":"library_execute","module":"distribution_fit","function":"fit_normal","args":[big]}).encode())

def main():
    if len(sys.argv)!=3: sys.exit(__doc__)
    LIB,REQF=sys.argv[1],sys.argv[2]; _ensure_request(REQF); req=open(REQF,'rb').read(); N=4
    l=load(LIB); h=l.algenta_runtime_init(None); call(l,h,req)
    t=time.monotonic(); ok=all(call(l,h,req) for _ in range(3)); single=(time.monotonic()-t)/3
    print(f"warm single call = {single*1000:.0f} ms (clean={ok});  N={N} K={K}  -> capped wall ≈ {N*K*single:.1f}s, parallel wall ≈ {K*single:.1f}s\n")
    if not ok:
        # There is nothing to measure unless the heavy request succeeds. Refuse cleanly (exit 2) with the
        # library's own answer instead of a bare assertion traceback.
        p=l.algenta_runtime_execute(h,req); msg=(ctypes.string_at(p)[:220].decode("utf-8","replace") if p else "NULL response")
        if p: l.algenta_runtime_free(p)
        print(f"GATE ABORTED: the heavy request must return a clean result so there is work to measure; the library answered: {msg}\n  Provide a library_execute request valid for THIS family (module / function / args).", flush=True)
        l.algenta_runtime_shutdown(h); sys.exit(2)
    ROOT=(os.geteuid()==0)
    if ROOT: print("WARNING: running as root — root is outside the §9 threat model (ABI 9.5): it can unlink the anchor or patch the binary. (h) is skipped; (a)-(g) still verify the cap. Run the gate as a normal user for the full result.\n")
    verdict("(a) 4 separate processes", gather([child(LIB,REQF,K) for _ in range(N)]), single)
    parts=[]; lk=threading.Lock()
    def th():
        r=timed(l,h,req,K)
        with lk: parts.append(r)
    ts=[threading.Thread(target=th) for _ in range(N)]; [x.start() for x in ts]; [x.join() for x in ts]
    verdict("(b) 4 threads, one process, one handle", parts, single)
    d=tempfile.mkdtemp(); ext=os.path.splitext(LIB)[1]
    for f in glob.glob(os.path.join(os.path.dirname(LIB),"*")):
        if os.path.isfile(f): shutil.copy2(f,d)
    LIB2=os.path.join(d,"copy"+ext); shutil.copy2(LIB,LIB2)
    verdict("(c) 2 library instances x 2 procs (2 families)", gather([child(LIB,REQF,K),child(LIB,REQF,K),child(LIB2,REQF,K),child(LIB2,REQF,K)]), single)
    verdict("(d) fork-after-load (parent+child, warm)", gather([child(LIB,REQF,K,fork=True)]), single)
    hostile={"ALGENTA_ENFORCE_WORKER_CAP":"0","ALGENTA_COMMUNITY_CAP":"0","ALGENTA_WORKER_LIMIT":"64","ALGENTA_NO_CAP":"1","ALGENTA_DISABLE_CAP":"1","ALGENTA_UNLIMITED":"1"}
    verdict("(e) 4 procs + hostile env vars", gather([child(LIB,REQF,K,hostile) for _ in range(N)]), single)
    hp=hold(60); time.sleep(0.2); t0=time.monotonic(); hp.kill(); hp.wait(); ok=call(l,h,req); dt=time.monotonic()-t0
    v="RELEASED ✅" if (ok and dt<single+1.0) else "HUNG ❌"; results.append(("(f) SIGKILL slot holder -> next call proceeds",v)); print(f"{'(f) SIGKILL slot holder -> next call proceeds':<50} next call finished {dt*1000:.0f}ms after kill  {v}")
    hp=hold(1.0); t0=time.monotonic(); ok=call(l,h,req); dt=time.monotonic()-t0; hp.wait()
    v="QUEUED ✅" if (ok and dt>=0.9+single*0.5) else "❌"; results.append(("(g) call while slot held 1.0s -> queues, then OK",v)); print(f"{'(g) call while slot held 1.0s -> queues, then OK':<50} took {dt*1000:.0f}ms (≥ hold+work) clean={ok}  {v}")
    if ROOT:
        results.append(("(h) user cannot delete the lock anchor","SKIPPED (root)")); print(f"{'(h) user cannot delete the lock anchor (/dev/null)':<50} skipped: running as root (outside the threat model, ABI 9.5)")
    else:
        try: os.unlink("/dev/null"); ok=False
        except OSError as ex: ok=ex.errno in (errno.EPERM,errno.EACCES,errno.EBUSY,errno.EROFS)
        v="UNDELETABLE ✅" if ok else "DELETED ❌"; results.append(("(h) user cannot delete the lock anchor",v)); print(f"{'(h) user cannot delete the lock anchor (/dev/null)':<50} unlink refused={ok}  {v}")
    # (i) EVERY reachable error path releases the slot and keeps its OWN code (never slot_unavailable).
    #     A 14-input adversarial probe (invalid UTF-8, truncated/garbage JSON, control bytes, type
    #     confusion, missing fields, unknown functions) showed _execute handles ALL malformed input by
    #     RETURNING an error envelope; no external input makes it raise, so _execute_capped's `except`
    #     is a defensive backstop, not a reachable path. What IS reachable — and what this proves — is
    #     release after each distinct error code. A leaked slot would make the follow-up heavy call block
    #     forever (flock LOCK_EX), so it runs on a daemon thread with a timeout: a hang fails loudly.
    bad_inputs=[("request_type_unsupported", json.dumps({"type":"not_a_declared_route"}).encode()),
                ("request_not_json", b'"'),   # genuinely unparseable JSON (a lone quote) -> parse-failure path
                ("request_not_json", b"{}"),    # valid JSON with no "type": _execute maps a missing/unreadable type to the same code
                ("invalid_arguments", b'{"type":"library_execute"}'),
                # module taken from the heavy request so this probe is valid for ANY family (a module the
                # family does not ship yields a different — equally correct — error code and would misfire)
                ]
    # The unknown-function probe needs a module THIS family ships; take it from the heavy request. A
    # request file that is not a library_execute (no "module") skips this one probe with a clear note
    # rather than crashing the gate before its verdict (the other four probes still run).
    try: _mod=json.loads(req).get("module")
    except Exception: _mod=None
    if _mod: bad_inputs.append(("function_not_registered", json.dumps({"type":"library_execute","module":_mod,"function":"does_not_exist","args":[]}).encode()))
    else: print("(i) note: request has no \"module\" — function_not_registered probe skipped")
    codes_ok=True; seen=[]; th=None; box={}
    for want,bad_req in bad_inputs:
        pe=l.algenta_runtime_execute(h,bad_req); er=ctypes.string_at(pe) if pe else b""
        if pe: l.algenta_runtime_free(pe)
        own=(b'"error"' in er) and (want.encode() in er) and (b"community_worker_slot_unavailable" not in er)
        codes_ok&=own; seen.append(f"{want}:{'ok' if own else 'WRONG-CODE'}")
        box={}
        def _next(b=box): b["t0"]=time.monotonic(); b["ok"]=call(l,h,req); b["dt"]=time.monotonic()-b["t0"]
        th=threading.Thread(target=_next,daemon=True); th.start(); th.join(timeout=single*4+3.0)
        if th.is_alive() or not box.get("ok") or box.get("dt",9e9)>=single*2.5+0.2: codes_ok=False; seen[-1]+="/LEAK"
        if th.is_alive(): break
    dt_txt="hung" if (th and th.is_alive()) else (f"{box['dt']*1000:.0f}ms" if "dt" in box else "n/a")
    v="RELEASED+OWN CODE ✅" if codes_ok else ("LEAKED/HUNG ❌" if (th and th.is_alive()) else "❌")
    results.append(("(i) every reachable error path releases slot; own code",v))
    print(f"{'(i) every reachable error path releases slot; own code':<50} {' '.join(seen)} last_next_call={dt_txt}  {v}")
    l.algenta_runtime_shutdown(h)
    def _passed(v): return ("✅" in v) or v=="SKIPPED (root)"   # allow-list: anything not positively green (❌, ⚠️, INCONCLUSIVE, unknown) fails
    bad=[r for r in results if not _passed(r[1])]
    held=len(results)-len(bad)-(1 if ROOT else 0)
    print("\n=== RED-TEAM v3 VERDICT:", (f"ALL {held} SCENARIOS HELD — no loophole found" + (" ((h) skipped: root)" if ROOT else "")) if not bad else f"{len(bad)} FAILURE(S): "+", ".join(r[0] for r in bad)); sys.exit(1 if bad else 0)
if __name__=="__main__": main()
