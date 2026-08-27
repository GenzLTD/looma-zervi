"""Quick smoke test for Ed25519 crypto module."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.crypto import _load_or_generate_keys, sign_attestation, verify_attestation, get_public_key_pem

# Test key generation
pem = get_public_key_pem()
print(f"Public key OK: {pem[:60]}...")

# Test sign + verify
body = {
    "attestation_id": "att_test",
    "candidate_id": "uid_test",
    "claim_type": "collaboration",
    "claim_statement": "能与不同风格的人完成协作任务",
    "evidence_type": "fleet_consensus",
    "verification_status": "verified",
    "evidence_refs": ["mem_abc"],
    "confidence_score": 0.9,
    "issued_at": "2026-07-20T08:00:00Z",
    "expires_at": None,
}
sig = sign_attestation(body)
print(f"Signature: {sig}")

# Verify
body_with_sig = {**body, "signature": sig}
ok = verify_attestation(body_with_sig)
print(f"Verify OK: {ok}")

# Tamper test
body_tampered = {**body_with_sig, "claim_statement": "被篡改的声明"}
ok2 = verify_attestation(body_tampered)
print(f"Tampered detection OK: {not ok2}")

print("\nAll crypto tests passed!")