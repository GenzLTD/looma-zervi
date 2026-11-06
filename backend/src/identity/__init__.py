"""Compat shim — real modules live in src.thomas_core.identity."""
from src.thomas_core.identity.ledger_subject import (  # noqa: F401
    AmbiguousLedgerSubject,
    ensure_principal_sub,
    resolve_settlement_user_id,
)
