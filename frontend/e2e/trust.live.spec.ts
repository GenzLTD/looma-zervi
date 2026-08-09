/**
 * P0 — Trust attestations + public share verify (Vultr / overseas)
 *
 *   E2E_OVERSEAS_API=https://api.genz.ltd pnpm e2e:overseas:trust
 *
 * Contract notes (vs early draft):
 *   - verify is POST /v1/trust/verify { share_code } (public, no JWT)
 *   - create is POST /v1/trust/share-code; revoke is DELETE /v1/trust/share-code/:id
 *   - attestation cards use claim_type / verification_status / confidence_score / signature
 */
import { test, expect } from "@playwright/test";
import {
  registerOverseasUser,
  listAttestations,
  refreshAttestations,
  createTrustShareCode,
  listTrustShareCodes,
  revokeTrustShareCode,
  verifyTrustShareCode,
} from "./helpers/overseasApi";

test.describe.configure({ mode: "serial" });

test.describe("trust API @overseas @live", () => {
  test("list attestations returns cards schema", async () => {
    const { token } = await registerOverseasUser("E2E Trust List");
    const { attestations, total } = await listAttestations(token);
    expect(Array.isArray(attestations)).toBe(true);
    expect(total).toBe(attestations.length);

    for (const card of attestations) {
      expect(card.attestation_id || card.id).toBeTruthy();
      expect(card.claim_type).toBeTruthy();
      expect(card.verification_status).toBeTruthy();
      expect(typeof (card.confidence_score ?? 0)).toBe("number");
      // signature may be empty until refresh; field must exist after list signing
      expect("signature" in card || card.signature === "" || card.signature).toBeTruthy();
    }
  });

  test("refresh does not shrink attestation count", async () => {
    test.setTimeout(180_000);
    const { token } = await registerOverseasUser("E2E Trust Refresh");
    const before = await listAttestations(token);
    const refreshed = await refreshAttestations(token);
    expect(Array.isArray(refreshed.attestations)).toBe(true);
    expect(refreshed.total).toBeGreaterThanOrEqual(before.total);
  });

  test("share code create → public verify → revoke → revoked", async () => {
    test.setTimeout(120_000);
    const { token } = await registerOverseasUser("E2E Trust Share");
    await refreshAttestations(token);

    const created = await createTrustShareCode(token, {
      scope: ["identity", "collaboration"],
      max_access_count: 5,
      expires_in_seconds: 3600,
    });

    // Production codes look like sc_<hex> (not bare 8-char alnum)
    expect(created.share_code).toMatch(/^sc_[a-f0-9]{8,32}$/i);
    expect(created.remaining_access_count).toBeGreaterThan(0);
    expect(Array.isArray(created.scope)).toBe(true);

    const verified = await verifyTrustShareCode(created.share_code);
    expect(verified.status).toBe(200);
    expect(Array.isArray(verified.body.attestations)).toBe(true);
    // issuer / confidence when cards exist
    for (const card of (verified.body.attestations as Array<Record<string, unknown>>) || []) {
      expect(card.claim_type || card.attestation_id).toBeTruthy();
      if (card.confidence_score !== undefined) {
        expect(Number(card.confidence_score)).toBeGreaterThanOrEqual(0);
      }
    }

    const listed = await listTrustShareCodes(token);
    const row = listed.share_codes.find(
      (c) => c.code === created.share_code || c.share_code === created.share_code,
    );
    expect(row).toBeTruthy();
    const codeId = String(row!.id);
    expect(codeId.length).toBeGreaterThan(0);

    await revokeTrustShareCode(token, codeId);

    const afterRevoke = await verifyTrustShareCode(created.share_code);
    expect(afterRevoke.status).toBe(403);
    expect(afterRevoke.body.error).toBe("share_code_revoked");
  });

  test("share code exhausted after max_access_count", async () => {
    test.setTimeout(120_000);
    const { token } = await registerOverseasUser("E2E Trust Exhaust");
    await refreshAttestations(token);

    const created = await createTrustShareCode(token, {
      scope: ["identity"],
      max_access_count: 1,
      expires_in_seconds: 3600,
    });

    const first = await verifyTrustShareCode(created.share_code);
    expect(first.status).toBe(200);

    const second = await verifyTrustShareCode(created.share_code);
    expect(second.status).toBe(429);
    expect(second.body.error).toBe("share_code_exhausted");
  });
});
