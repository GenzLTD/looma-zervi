/**
 * PIPL consent helpers for miniprogram (uses createMiniApi factories, no Web ApiClient).
 */
import { createComplianceApi, type MiniApiClientInterface } from "../api/createMiniApi";
import { resolveConsentPromptScope } from "../constants/compliance";
import type { ConsentScope } from "../types/compliance";

export function isConsentRequiredError(
  err: unknown,
): err is { status: number; body: { error: string; required_scope?: ConsentScope } } {
  if (!err || typeof err !== "object") return false;
  const e = err as { status?: number; body?: { error?: string } };
  return e.status === 403 && e.body?.error === "consent_required";
}

export async function hasConsent(
  client: MiniApiClientInterface,
  scope: ConsentScope,
): Promise<boolean> {
  const api = createComplianceApi(client);
  const res = await api.status();
  const promptScope = resolveConsentPromptScope(scope);
  return Boolean(res.status[scope] || res.status[promptScope]);
}

export async function grantConsent(
  client: MiniApiClientInterface,
  scope: ConsentScope,
): Promise<void> {
  const api = createComplianceApi(client);
  await api.grant(resolveConsentPromptScope(scope));
}

export async function ensureConsent(
  client: MiniApiClientInterface,
  scope: ConsentScope,
  prompt: (scope: ConsentScope) => Promise<boolean>,
): Promise<boolean> {
  const promptScope = resolveConsentPromptScope(scope);
  try {
    if (await hasConsent(client, scope)) return true;
  } catch {
    return false;
  }
  const accepted = await prompt(promptScope);
  if (!accepted) return false;
  try {
    await grantConsent(client, promptScope);
    return true;
  } catch {
    return false;
  }
}
