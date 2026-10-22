"use client";

const SESSION_KEY = "ida.oidc.session";
const STATE_KEY = "ida.oidc.state";
const VERIFIER_KEY = "ida.oidc.verifier";
const REFRESH_SKEW_MS = 30_000;

interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  expires_in: number;
  token_type: string;
}

export interface AuthSession {
  accessToken: string;
  refreshToken: string | null;
  idToken: string | null;
  expiresAt: number;
  username: string | null;
}

export class AuthenticationRequiredError extends Error {
  constructor(message = "登录状态已失效，请重新登录。") {
    super(message);
    this.name = "AuthenticationRequiredError";
  }
}

function config() {
  const issuer =
    process.env.NEXT_PUBLIC_OIDC_ISSUER ?? "http://localhost:8080/realms/ida";
  return {
    issuer: issuer.replace(/\/$/, ""),
    clientId:
      process.env.NEXT_PUBLIC_OIDC_CLIENT_ID ?? "intelligent-data-agent-web",
    redirectUri:
      process.env.NEXT_PUBLIC_OIDC_REDIRECT_URI ??
      (typeof window === "undefined"
        ? "http://localhost:3000/"
        : `${window.location.origin}/`),
    scope: process.env.NEXT_PUBLIC_OIDC_SCOPE ?? "openid profile email",
  };
}

function decodeClaims(token: string): Record<string, unknown> {
  try {
    const payload = token.split(".")[1];
    if (!payload) return {};
    const normalized = payload
      .replace(/-/g, "+")
      .replace(/_/g, "/")
      .padEnd(Math.ceil(payload.length / 4) * 4, "=");
    return JSON.parse(window.atob(normalized)) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function usernameFor(token: string): string | null {
  const claims = decodeClaims(token);
  for (const key of ["preferred_username", "name", "email", "sub"]) {
    const value = claims[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
}

function readSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.sessionStorage.getItem(SESSION_KEY);
    if (!value) return null;
    const parsed = JSON.parse(value) as Partial<AuthSession>;
    if (
      typeof parsed.accessToken !== "string" ||
      typeof parsed.expiresAt !== "number"
    ) {
      return null;
    }
    return {
      accessToken: parsed.accessToken,
      refreshToken:
        typeof parsed.refreshToken === "string" ? parsed.refreshToken : null,
      idToken: typeof parsed.idToken === "string" ? parsed.idToken : null,
      expiresAt: parsed.expiresAt,
      username: typeof parsed.username === "string" ? parsed.username : null,
    };
  } catch {
    return null;
  }
}

function toSession(
  tokens: TokenResponse,
  previous?: AuthSession | null,
): AuthSession {
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token ?? previous?.refreshToken ?? null,
    idToken: tokens.id_token ?? previous?.idToken ?? null,
    expiresAt: Date.now() + tokens.expires_in * 1000,
    username: usernameFor(tokens.access_token),
  };
}

function saveSession(session: AuthSession): void {
  window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

function randomUrlSafe(bytes = 32): string {
  const values = crypto.getRandomValues(new Uint8Array(bytes));
  return btoa(String.fromCharCode(...values))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

async function pkceChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(verifier),
  );
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

async function tokenRequest(body: URLSearchParams): Promise<TokenResponse> {
  const { issuer } = config();
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 8_000);
  let response: Response;
  try {
    response = await fetch(`${issuer}/protocol/openid-connect/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timer);
  }
  if (!response.ok) {
    throw new AuthenticationRequiredError("无法完成身份验证，请重新登录。");
  }
  return (await response.json()) as TokenResponse;
}

async function refreshSession(session: AuthSession): Promise<AuthSession> {
  if (!session.refreshToken) throw new AuthenticationRequiredError();
  const tokens = await tokenRequest(
    new URLSearchParams({
      grant_type: "refresh_token",
      client_id: config().clientId,
      refresh_token: session.refreshToken,
    }),
  );
  const refreshed = toSession(tokens, session);
  saveSession(refreshed);
  return refreshed;
}

export function getAuthSession(): AuthSession | null {
  return readSession();
}

export async function getAccessToken(forceRefresh = false): Promise<string> {
  const session = readSession();
  if (!session) throw new AuthenticationRequiredError();
  if (!forceRefresh && session.expiresAt - REFRESH_SKEW_MS > Date.now()) {
    return session.accessToken;
  }
  return (await refreshSession(session)).accessToken;
}

export async function beginOidcLogin(): Promise<void> {
  const { issuer, clientId, redirectUri, scope } = config();
  const verifier = randomUrlSafe();
  const state = randomUrlSafe(24);
  window.sessionStorage.setItem(VERIFIER_KEY, verifier);
  window.sessionStorage.setItem(STATE_KEY, state);
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope,
    state,
    code_challenge: await pkceChallenge(verifier),
    code_challenge_method: "S256",
  });
  window.location.assign(
    `${issuer}/protocol/openid-connect/auth?${params.toString()}`,
  );
}

export async function completeOidcLogin(): Promise<AuthSession | null> {
  const url = new URL(window.location.href);
  const code = url.searchParams.get("code");
  if (!code) return null;
  const returnedState = url.searchParams.get("state");
  const expectedState = window.sessionStorage.getItem(STATE_KEY);
  const verifier = window.sessionStorage.getItem(VERIFIER_KEY);
  if (
    !returnedState ||
    !expectedState ||
    returnedState !== expectedState ||
    !verifier
  ) {
    throw new AuthenticationRequiredError("身份验证回调校验失败。");
  }
  const tokens = await tokenRequest(
    new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config().clientId,
      redirect_uri: config().redirectUri,
      code,
      code_verifier: verifier,
    }),
  );
  const session = toSession(tokens);
  saveSession(session);
  window.sessionStorage.removeItem(STATE_KEY);
  window.sessionStorage.removeItem(VERIFIER_KEY);
  url.searchParams.delete("code");
  url.searchParams.delete("state");
  url.searchParams.delete("session_state");
  window.history.replaceState(
    {},
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
  return session;
}

export function signOut(): void {
  window.sessionStorage.removeItem(SESSION_KEY);
  window.sessionStorage.removeItem(STATE_KEY);
  window.sessionStorage.removeItem(VERIFIER_KEY);
  window.location.assign(window.location.origin);
}
