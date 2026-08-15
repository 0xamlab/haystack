"""algenta_dns_proxy -- resilient loopback CONNECT proxy for the self-hosted GitHub runners.

WHY: this Mac's resolver path (router DNS 192.168.4.1 -> ISP) intermittently fails to resolve
api.github.com (curl/getaddrinfo time out while upstream resolvers answer fine). The failure
recurs and self-heals unpredictably, which makes the GitHub self-hosted runners on this box
drop off / fail jobs. A one-time `sudo dscacheutil -flushcache` cannot fix a recurring problem,
so this proxy makes the runners' network path independent of the local resolver entirely.

Resolution order for CONNECT targets:
  1. static pin table (GitHub API/web anycast + the DoH endpoint itself),
  2. DNS-over-HTTPS to cloudflare-dns.com, dialed at its pinned IPs (no DNS needed to reach it),
  3. the system resolver (getaddrinfo) as last resort.
Answers are cached for CACHE_TTL seconds. Everything else is plain byte tunneling (TLS passes
through end-to-end; this proxy never terminates or inspects TLS).

Installed as a user LaunchAgent (see ~/Library/LaunchAgents/com.algenta.dns-proxy.plist);
listens on 127.0.0.1:8899 only. Clients set https_proxy/http_proxy=http://127.0.0.1:8899.
"""

import json
import socket
import socketserver
import ssl
import threading
import time
import urllib.request

LISTEN = ("127.0.0.1", 8899)
CACHE_TTL = 300

# Anycast ranges are stable for GitHub's edge; multiple candidates are tried in order.
PINS = {
    "api.github.com": ["140.82.114.5", "140.82.113.6", "140.82.112.6"],
    "github.com": ["140.82.114.4", "140.82.113.4", "140.82.112.4"],
    "cloudflare-dns.com": ["1.1.1.1", "1.0.0.1"],
}
DOH_IPS = ["1.1.1.1", "1.0.0.1"]

_cache = {}
_cache_lock = threading.Lock()


def _log(msg):
    print(f"[dns-proxy {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _doh_resolve(host):
    """Resolve via Cloudflare DoH, connecting straight to a pinned DoH IP (no DNS needed)."""
    url = f"https://cloudflare-dns.com/dns-query?name={host}&type=A"
    for ip in DOH_IPS:
        try:
            sock = socket.create_connection((ip, 443), timeout=6)
            ctx = ssl.create_default_context()
            ssock = ctx.wrap_socket(sock, server_hostname="cloudflare-dns.com")
            req = urllib.request.Request(url, headers={
                "accept": "application/dns-json",
                "Host": "cloudflare-dns.com",
            })
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),  # direct connection already established
            )
            # urllib cannot reuse our raw TLS socket; do the exchange by hand instead.
            ssock.sendall(
                (f"GET /dns-query?name={host}&type=A HTTP/1.1\r\n"
                 f"Host: cloudflare-dns.com\r\naccept: application/dns-json\r\n"
                 f"Connection: close\r\n\r\n").encode()
            )
            data = b""
            while True:
                chunk = ssock.recv(65536)
                if not chunk:
                    break
                data += chunk
            ssock.close()
            body = data.split(b"\r\n\r\n", 1)[1]
            payload = json.loads(body)
            addrs = [a["data"] for a in payload.get("Answer", []) if a.get("type") == 1]
            if addrs:
                return addrs
        except Exception:
            continue
    return []


def resolve(host):
    host_l = host.lower().rstrip(".")
    with _cache_lock:
        hit = _cache.get(host_l)
        if hit and hit[1] > time.time():
            return hit[0]
    addrs = list(PINS.get(host_l, []))
    if not addrs:
        addrs = _doh_resolve(host_l)
    if not addrs:
        try:
            addrs = [ai[4][0] for ai in socket.getaddrinfo(host, None, socket.AF_INET)]
        except OSError:
            addrs = []
    if addrs:
        with _cache_lock:
            _cache[host_l] = (addrs, time.time() + CACHE_TTL)
    return addrs


def connect_up(host, port):
    last_err = None
    for ip in resolve(host):
        try:
            return socket.create_connection((ip, port), timeout=12)
        except OSError as exc:
            last_err = exc
    raise OSError(f"no route to {host}:{port}: {last_err}")


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        sock = self.request
        sock.settimeout(30)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                return
            data += chunk
        line = data.split(b"\r\n", 1)[0].decode("latin-1")
        parts = line.split()
        if len(parts) < 2 or parts[0] != "CONNECT":
            sock.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
            return
        host, _, port = parts[1].partition(":")
        port = int(port or 443)
        try:
            up = connect_up(host, port)
        except OSError as exc:
            sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            _log(f"FAIL {host}:{port} -- {exc}")
            return
        # Long-lived tunnels (runner broker long-polls, artifact downloads with quiet stretches)
        # must not be cut by the handshake-phase timeouts: clear them on both directions.
        up.settimeout(None)
        sock.settimeout(None)
        sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

        def pump(a, b):
            try:
                while True:
                    d = a.recv(65536)
                    if not d:
                        break
                    b.sendall(d)
            except OSError:
                pass
            finally:
                try:
                    b.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        t1 = threading.Thread(target=pump, args=(sock, up), daemon=True)
        t2 = threading.Thread(target=pump, args=(up, sock), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        try:
            up.close()
        except OSError:
            pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    srv = Server(LISTEN, Handler)
    _log(f"listening on {LISTEN[0]}:{LISTEN[1]} (pins: {', '.join(PINS)}; DoH: {DOH_IPS})")
    srv.serve_forever()
