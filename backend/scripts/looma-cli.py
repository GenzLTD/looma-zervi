#!/usr/bin/env python3
"""
looma-cli — Trust Profile Terminal Client
==========================================
A lightweight CLI reference implementation for the Looma Trust Protocol.

Usage:
  looma-cli trust profile                  Show your trust attestations
  looma-cli trust share-code              Generate a share code
  looma-cli trust share-code --list       List your share codes
  looma-cli trust share-code --revoke ID  Revoke a share code
  looma-cli trust verify CODE             Verify attestations with a share code
  looma-cli trust audit-log               See who accessed your trust data

Setup:
  Set LOOMA_API_BASE (default: http://localhost:5200)
  Set LOOMA_TOKEN env var to your JWT bearer token
  Or pass --token explicitly

Design: trust.v1.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from datetime import datetime, timezone, timedelta
from typing import Any

import requests

# ---------------------------------------------------------------------------
# ANSI colour helpers (for terminal prettiness)
# ---------------------------------------------------------------------------

class C:
    """ANSI escape codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    @staticmethod
    def status(s: str) -> str:
        """Colour a verification status."""
        colours = {
            "verified": C.GREEN,
            "verified_by_authority": C.GREEN,
            "weak": C.YELLOW,
            "unverified": C.RED,
            "contradicted": C.RED,
        }
        c = colours.get(s, C.DIM)
        return f"{c}{s}{C.RESET}"

    @staticmethod
    def bar(confidence: float, width: int = 20) -> str:
        """Render a confidence bar."""
        filled = int(round(confidence * width))
        bar_chars = "█" * filled + "░" * (width - filled)
        colour = C.GREEN if confidence >= 0.7 else C.YELLOW if confidence >= 0.4 else C.RED
        return f"{colour}{bar_chars}{C.RESET} {confidence:.2f}"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_API_BASE = os.getenv("LOOMA_API_BASE", "http://localhost:5200")


def _get_token(cli_token: str | None = None) -> str:
    """Resolve JWT token from CLI arg, env var, or config file."""
    if cli_token:
        return cli_token
    env_token = os.getenv("LOOMA_TOKEN", "")
    if env_token:
        return env_token
    # Try .looma_token file in home directory
    home = os.path.expanduser("~")
    token_file = os.path.join(home, ".looma_token")
    if os.path.exists(token_file):
        with open(token_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    print(f"{C.RED}Error:{C.RESET} No token found. Set LOOMA_TOKEN env var or pass --token.", file=sys.stderr)
    print(f"  export LOOMA_TOKEN='your-jwt-token'", file=sys.stderr)
    print(f"  or: looma-cli --token YOUR_TOKEN trust profile", file=sys.stderr)
    sys.exit(1)


def _api(path: str, token: str | None = None, method: str = "GET", body: dict | None = None) -> dict:
    """Make an API call to the looma backend."""
    url = f"{_API_BASE.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=15)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=body, timeout=15)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=15)
        else:
            raise ValueError(f"Unknown method: {method}")
    except requests.ConnectionError:
        print(f"{C.RED}Connection error:{C.RESET} Cannot reach {_API_BASE}", file=sys.stderr)
        print("  Is the looma backend running?", file=sys.stderr)
        sys.exit(1)
    except requests.Timeout:
        print(f"{C.RED}Timeout:{C.RESET} Request to {url} timed out.", file=sys.stderr)
        sys.exit(1)

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print(f"{C.RED}Unexpected response:{C.RESET} {resp.text[:300]}", file=sys.stderr)
        sys.exit(1)

    if not resp.ok:
        err = data.get("error", "unknown_error")
        msg = data.get("message", str(data))
        print(f"{C.RED}API error [{resp.status_code}]:{C.RESET} {err} — {msg}", file=sys.stderr)
        sys.exit(1)

    return data


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

_CLAIM_EMOJI = {
    "identity": "🧠",
    "collaboration": "🤝",
    "communication": "💬",
    "influence": "📢",
}


def _display_profile(attestations: list[dict]) -> None:
    """Pretty print trust attestation cards."""
    if not attestations:
        print(f"\n{C.DIM}  No trust attestations yet. Complete some PlanetX missions to generate them.{C.RESET}\n")
        return

    print(f"\n{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}║{C.RESET}  {C.BOLD}Looma Trust Profile{C.RESET}                                  {C.BOLD}{C.CYAN}║{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}╚══════════════════════════════════════════════════════╝{C.RESET}\n")

    for att in attestations:
        ct = att.get("claim_type", "unknown")
        emoji = _CLAIM_EMOJI.get(ct, "📋")
        status = att.get("verification_status", "unverified")
        confidence = att.get("confidence_score", 0.0)
        statement = att.get("claim_statement", "")
        evidence_type = att.get("evidence_type", "")
        refs = att.get("evidence_refs", [])
        issued = att.get("issued_at", "")
        expires = att.get("expires_at", "")
        sig = att.get("signature", "")

        # Header
        print(f"  {emoji}  {C.BOLD}{ct.upper()}{C.RESET}  [{C.status(status)}]")
        print(f"     {C.BOLD}\"{statement}\"{C.RESET}")
        print(f"     {C.DIM}Evidence: {evidence_type} ({len(refs)} memory refs){C.RESET}")
        print(f"     Confidence:  {C.bar(confidence)}")
        if issued:
            print(f"     {C.DIM}Issued: {_nice_date(issued)}{C.RESET}")
        if expires:
            expired = _is_expired(expires)
            label = f"{C.RED}(EXPIRED){C.RESET}" if expired else ""
            print(f"     {C.DIM}Expires: {_nice_date(expires)} {label}{C.RESET}")
        if sig:
            short_sig = sig[:30] + "..." if len(sig) > 30 else sig
            print(f"     {C.DIM}Signature: {short_sig}{C.RESET}")
        print()

    total = len(attestations)
    verified = sum(1 for a in attestations if a.get("verification_status") == "verified")
    print(f"  {C.BOLD}{total} attestation(s){C.RESET} · {C.GREEN}{verified} verified{C.RESET}\n")


def _display_share_code(sc: dict) -> None:
    """Display a newly created share code."""
    print(f"\n{C.BOLD}{C.GREEN}  ✓ Share code generated{C.RESET}\n")
    print(f"  Code:       {C.BOLD}{C.CYAN}{sc.get('share_code', '?')}{C.RESET}")
    print(f"  Scope:      {', '.join(sc.get('scope', []))}")
    print(f"  Expires:    {_nice_date(sc.get('expires_at', ''))}")
    print(f"  Remaining:  {sc.get('remaining_access_count', '?')} uses\n")
    print(f"  {C.DIM}Share this with the verifier:{C.RESET}")
    print(f"  {C.DIM}looma-cli trust verify {sc.get('share_code', '')}{C.RESET}\n")


def _display_verify_result(data: dict) -> None:
    """Display attestations retrieved via share_code verification."""
    attestations = data.get("attestations", [])
    alias = data.get("candidate_alias", "Anonymous")

    print(f"\n{C.BOLD}{C.GREEN}  ✓ Verification successful{C.RESET}")
    print(f"  Candidate:  {C.BOLD}{alias}{C.RESET}")
    print(f"  Verified:   {_nice_date(data.get('verified_at', ''))}")
    print(f"  Scope:      {', '.join(data.get('share_code_scope', []))}\n")

    for att in attestations:
        ct = att.get("claim_type", "unknown")
        emoji = _CLAIM_EMOJI.get(ct, "📋")
        status = att.get("verification_status", "unverified")
        confidence = att.get("confidence_score", 0.0)
        statement = att.get("claim_statement", "")
        sig = att.get("signature", "")

        print(f"  {emoji}  {C.BOLD}{ct.upper()}{C.RESET}  [{C.status(status)}]")
        print(f"     \"{statement}\"")
        print(f"     Confidence: {C.bar(confidence)}")
        if sig:
            short = sig[:40] + "..." if len(sig) > 40 else sig
            print(f"     {C.DIM}Sig: {short}{C.RESET}")
        print()

    # Verify signatures (offline — the protocol layer's core value)
    print(f"  {C.DIM}── Signature verification ──{C.RESET}")
    try:
        pub_key_data = _api("/v1/trust/.well-known/public-key", token=None)
        pub_pem = pub_key_data.get("public_key_pem", "")
        print(f"  {C.DIM}Public key: {pub_pem[:60].strip()}...{C.RESET}")
        for att in attestations:
            sig = att.get("signature", "")
            if sig:
                # We can verify offline by calling the API's verify endpoint
                # or by checking the signature ourselves with crypto
                print(f"  {C.GREEN}  ✓ {att['attestation_id'][:12]}... signature present{C.RESET}")
            else:
                print(f"  {C.YELLOW}  ⚠ {att['attestation_id'][:12]}... no signature{C.RESET}")
        print(f"\n  {C.DIM}Full offline verification: save the attestation JSON + public key.{C.RESET}")
        print(f"  {C.DIM}verification: python -c \"from utils.crypto import verify_attestation; ...\"{C.RESET}")
    except Exception:
        print(f"  {C.YELLOW}  ⚠ Could not fetch public key for offline verification{C.RESET}")

    print()


def _display_audit_log(logs: list[dict]) -> None:
    """Display verification audit trail."""
    if not logs:
        print(f"\n{C.DIM}  No one has viewed your trust data yet.{C.RESET}\n")
        return

    print(f"\n{C.BOLD}  Verification Audit Log{C.RESET}\n")
    for log in logs:
        result = log.get("result", "success")
        result_colour = C.GREEN if result == "success" else C.YELLOW if result == "expired" else C.RED
        att_ids = log.get("attestation_ids", [])
        if isinstance(att_ids, str):
            try:
                att_ids = json.loads(att_ids)
            except (json.JSONDecodeError, TypeError):
                att_ids = []
        print(f"  {C.DIM}{_nice_date(log.get('created_at', ''))}{C.RESET}")
        print(f"     Code:   {log.get('share_code', '')[:20]}...")
        print(f"     By:     {log.get('verifier_info', '')[:60]}")
        print(f"     Result: {result_colour}{result}{C.RESET}")
        print(f"     Viewed: {len(att_ids)} attestation(s)")
        print()


def _display_share_codes(codes: list[dict]) -> None:
    """List user's share codes."""
    if not codes:
        print(f"\n{C.DIM}  No share codes. Generate one with: looma-cli trust share-code{C.RESET}\n")
        return

    print(f"\n{C.BOLD}  Your Share Codes{C.RESET}\n")
    for sc in codes:
        status = sc.get("status", "active")
        status_c = C.GREEN if status == "active" else C.YELLOW if status == "expired" else C.RED
        scope = sc.get("scope", [])
        if isinstance(scope, str):
            try:
                scope = json.loads(scope)
            except (json.JSONDecodeError, TypeError):
                scope = []
        remaining = sc.get("max_access_count", 0) - sc.get("access_count", 0)

        print(f"  {C.BOLD}{sc.get('code', '?')}{C.RESET}")
        print(f"     ID:       {sc.get('id', '?')}")
        print(f"     Status:   {status_c}{status}{C.RESET}")
        print(f"     Scope:    {', '.join(scope)}")
        print(f"     Uses:     {remaining}/{sc.get('max_access_count', '?')} remaining")
        print(f"     Expires:  {_nice_date(sc.get('expires_at', ''))}")
        print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nice_date(iso_str: str) -> str:
    """Convert ISO 8601 to a human-readable short format."""
    if not iso_str:
        return "—"
    try:
        # Handle various ISO formats
        s = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso_str[:16]


def _is_expired(iso_str: str) -> bool:
    """Check if an ISO date is in the past."""
    if not iso_str:
        return False
    try:
        s = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt < datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    global _API_BASE
    parser = argparse.ArgumentParser(
        prog="looma-cli",
        description="Looma Trust Profile — Terminal Client (Overseas Beta Demo)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              looma-cli trust profile
              looma-cli trust share-code --scope identity,collaboration
              looma-cli trust share-code --list
              looma-cli trust share-code --revoke <code_id>
              looma-cli trust verify sc_abc123def456
              looma-cli trust audit-log
        """),
    )
    parser.add_argument("--token", "-t", help="JWT bearer token (or set LOOMA_TOKEN env var)")
    parser.add_argument("--api", help=f"API base URL (default: {_API_BASE})", default=_API_BASE)

    sub = parser.add_subparsers(dest="command", required=True)

    # trust
    trust = sub.add_parser("trust", help="Trust protocol operations")
    tsub = trust.add_subparsers(dest="subcommand", required=True)

    # trust profile
    tsub.add_parser("profile", help="Show your trust attestation cards")

    # trust share-code
    share = tsub.add_parser("share-code", help="Generate or manage share codes")
    share.add_argument("--scope", help="Comma-separated claim types (default: all)", default=None)
    share.add_argument("--ttl", help="TTL (e.g. 7d, 24h, 30m)", default="7d")
    share.add_argument("--max-access", type=int, default=10, help="Max access count (default: 10)")
    share.add_argument("--list", action="store_true", help="List all share codes")
    share.add_argument("--revoke", metavar="CODE_ID", help="Revoke a share code by ID")

    # trust verify
    verify = tsub.add_parser("verify", help="Verify attestations with a share code")
    verify.add_argument("code", help="Share code to verify (e.g. sc_abc123)")

    # trust audit-log
    tsub.add_parser("audit-log", help="See verification audit trail")

    args = parser.parse_args()

    if args.api:
        _API_BASE = args.api.rstrip("/")

    token = _get_token(args.token) if args.command == "trust" and args.subcommand != "verify" else None

    if args.command == "trust":
        if args.subcommand == "profile":
            data = _api("/v1/trust/attestations", token=token)
            _display_profile(data.get("attestations", []))

        elif args.subcommand == "share-code":
            if args.list:
                data = _api("/v1/trust/share-codes", token=token)
                _display_share_codes(data.get("share_codes", []))
            elif args.revoke:
                data = _api(f"/v1/trust/share-code/{args.revoke}", token=token, method="DELETE")
                print(f"\n{C.GREEN}  ✓ Share code revoked{C.RESET}\n")
            else:
                scope = None
                if args.scope:
                    scope = [s.strip() for s in args.scope.split(",") if s.strip()]
                # Parse TTL
                ttl_seconds = _parse_ttl(args.ttl)
                body = {
                    "expires_in_seconds": ttl_seconds,
                    "max_access_count": args.max_access,
                }
                if scope:
                    body["scope"] = scope
                data = _api("/v1/trust/share-code", token=token, method="POST", body=body)
                _display_share_code(data)

        elif args.subcommand == "verify":
            data = _api("/v1/trust/verify", token=None, method="POST", body={"share_code": args.code})
            _display_verify_result(data)

        elif args.subcommand == "audit-log":
            data = _api("/v1/trust/audit-log", token=token)
            _display_audit_log(data.get("audit_logs", []))


def _parse_ttl(ttl: str) -> int:
    """Parse a TTL string like '7d', '24h', '30m' into seconds."""
    ttl = ttl.strip().lower()
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    for suffix, mul in multipliers.items():
        if ttl.endswith(suffix):
            try:
                val = int(ttl[:-1])
                return val * mul
            except ValueError:
                pass
    # Try plain integer seconds
    try:
        return int(ttl)
    except ValueError:
        print(f"{C.YELLOW}Warning:{C.RESET} Could not parse TTL '{ttl}', using 7 days.", file=sys.stderr)
        return 604800


if __name__ == "__main__":
    main()