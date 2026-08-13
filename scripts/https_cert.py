#!/usr/bin/env python3
"""Diagnose and fix HTTPS for thebonhomme.com (apex + www).

https://thebonhomme.com already has a GitHub Pages certificate.
https://www.thebonhomme.com fails because www is a CNAME to the apex, so
GitHub terminates TLS with *.github.io (name mismatch).

GitHub issues one Let's Encrypt cert covering both names only when:

    www.thebonhomme.com  CNAME  lebonhommepharma.github.io

This script never replaces the whole zone. --apply-dns only writes:
  - CNAME www
  - AAAA @  (GitHub Pages IPv6, if missing)

A / MX / TXT / NS records are left alone.

Usage:
  python3 scripts/https_cert.py              # diagnose (no credentials)
  python3 scripts/https_cert.py --apply-dns  # GoDaddy API (needs keys)
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

DOMAIN = "thebonhomme.com"
WWW_HOST = f"www.{DOMAIN}"
PAGES_HOST = "lebonhommepharma.github.io"
GODADDY = "https://api.godaddy.com"
TTL = 600
GITHUB_AAAA = (
    "2606:50c0:8000::153",
    "2606:50c0:8001::153",
    "2606:50c0:8002::153",
    "2606:50c0:8003::153",
)


def dig_short(*args: str) -> list[str]:
    proc = subprocess.run(
        ["dig", "+short", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [ln.strip().rstrip(".") for ln in proc.stdout.splitlines() if ln.strip()]
    return lines


def peer_cert(server_hostname: str) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    with socket.create_connection((server_hostname, 443), timeout=20) as sock:
        with ctx.wrap_socket(sock, server_hostname=server_hostname) as tls:
            cert = tls.getpeercert()
    if not cert:
        raise SystemExit(f"empty certificate for {server_hostname}")
    return cert


def sans_of(cert: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for kind, value in cert.get("subjectAltName") or ():
        if kind == "DNS":
            names.append(value)
    return names


def common_name(cert: dict[str, Any]) -> str:
    for rdn in cert.get("subject") or ():
        for key, value in rdn:
            if key == "commonName":
                return str(value)
    return ""


def print_cert(label: str, host: str) -> list[str]:
    cert = peer_cert(host)
    names = sans_of(cert)
    print(f"{label} ({host})")
    print(f"  CN  {common_name(cert)}")
    print(f"  SAN {', '.join(names) or '(none)'}")
    return names


def diagnose() -> int:
    print("DNS")
    www_cname = dig_short("CNAME", WWW_HOST)
    apex_a = dig_short("A", DOMAIN)
    print(f"  {WWW_HOST} CNAME → {www_cname or '(none)'}")
    print(f"  {DOMAIN} A     → {apex_a}")
    print()
    print("Certificates")
    apex_sans = print_cert("apex", DOMAIN)
    www_sans = print_cert("www", WWW_HOST)
    print()

    problems: list[str] = []
    cname_ok = any(v.lower() == PAGES_HOST for v in www_cname)
    if not cname_ok:
        problems.append(
            f"{WWW_HOST} must CNAME to {PAGES_HOST} (today: {www_cname or 'missing'}). "
            "A CNAME to the apex makes GitHub serve *.github.io on HTTPS www."
        )
    if DOMAIN not in apex_sans:
        problems.append(f"apex certificate SAN is missing {DOMAIN}")
    if WWW_HOST not in www_sans:
        problems.append(
            f"www certificate SAN is missing {WWW_HOST} (presented {www_sans}). "
            "This is the HTTPS www failure."
        )
    if problems:
        print("NOT FLAWLESS")
        for item in problems:
            print(f"  - {item}")
        print()
        print("GoDaddy DNS panel: https://dcc.godaddy.com/control/thebonhomme.com/dns")
        print(f"  Edit CNAME www  →  {PAGES_HOST}")
        print("  Do not delete A / MX / TXT records.")
        print("Then wait for GitHub Pages to re-issue Let's Encrypt (often minutes, up to an hour).")
        print("If the SAN still omits www: homepage repo → Settings → Pages → remove and re-add")
        print("thebonhomme.com as the custom domain (apex stays primary).")
        return 1
    print("FLAWLESS: apex and www certificates include the matching hostnames.")
    return 0


def godaddy_auth() -> str:
    pat = os.environ.get("GODADDY_PAT", "").strip()
    if pat:
        return f"Bearer {pat}"
    key = os.environ.get("GODADDY_API_KEY", "").strip()
    secret = os.environ.get("GODADDY_API_SECRET", "").strip()
    if key and secret:
        return f"sso-key {key}:{secret}"
    raise SystemExit(
        "Need GoDaddy credentials in the environment:\n"
        "  GODADDY_API_KEY + GODADDY_API_SECRET  (developer.godaddy.com, production)\n"
        "  or GODADDY_PAT (Bearer token with domains.dns:update)\n"
        "Create keys at https://developer.godaddy.com/keys — production, not OTE.\n"
        "Or edit CNAME www in https://dcc.godaddy.com/control/thebonhomme.com/dns"
    )


def godaddy(method: str, path: str, payload: Any | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        GODADDY + path,
        data=body,
        method=method,
        headers={
            "Authorization": godaddy_auth(),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "symphony-https-cert",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode())
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:800]
        raise SystemExit(f"GoDaddy {method} {path} → HTTP {err.code}: {detail}") from err


def apply_dns() -> None:
    current = godaddy("GET", f"/v1/domains/{DOMAIN}/records/CNAME/www") or []
    current_data = [str(item.get("data", "")).rstrip(".") for item in current]
    print(f"GoDaddy CNAME www is {current_data or '(none)'}")
    if current_data == [PAGES_HOST]:
        print("www CNAME already points at GitHub Pages.")
    else:
        godaddy(
            "PUT",
            f"/v1/domains/{DOMAIN}/records/CNAME/www",
            [{"data": PAGES_HOST, "ttl": TTL}],
        )
        print(f"Set CNAME www → {PAGES_HOST}")

    aaaa = godaddy("GET", f"/v1/domains/{DOMAIN}/records/AAAA/@") or []
    have = {str(item.get("data", "")).lower() for item in aaaa}
    want = {ip.lower() for ip in GITHUB_AAAA}
    if have == want:
        print("Apex AAAA already matches GitHub Pages.")
        return
    if have and have != want:
        print(f"Refusing to replace unexpected apex AAAA records: {sorted(have)}")
        print("Fix those by hand if they are not GitHub Pages.")
        return
    godaddy(
        "PUT",
        f"/v1/domains/{DOMAIN}/records/AAAA/@",
        [{"data": ip, "ttl": TTL} for ip in GITHUB_AAAA],
    )
    print("Set apex AAAA to GitHub Pages IPv6 addresses.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply-dns",
        action="store_true",
        help="Write the www CNAME (and missing GitHub AAAA) via the GoDaddy API",
    )
    args = ap.parse_args()
    if args.apply_dns:
        apply_dns()
        print()
    code = diagnose()
    if args.apply_dns and code:
        print(
            "DNS write done if GoDaddy accepted it; public resolvers and the "
            "GitHub certificate can lag. Re-run without --apply-dns until FLAWLESS."
        )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
