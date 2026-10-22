"use client";

import { useEffect, useState } from "react";
import { Alert, Spin, Typography } from "antd";

import {
  beginOidcLogin,
  completeOidcLogin,
  getAccessToken,
  getAuthSession,
} from "./oidc";

type AuthState = "checking" | "authenticated" | "redirecting" | "error";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>("checking");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        const callbackSession = await completeOidcLogin();
        const session = callbackSession ?? getAuthSession();
        if (cancelled) return;
        if (session) {
          await getAccessToken();
          if (cancelled) return;
          setState("authenticated");
          return;
        }
        setState("redirecting");
        await beginOidcLogin();
      } catch (authError) {
        if (cancelled) return;
        setError(
          authError instanceof Error
            ? authError.message
            : "身份验证启动失败，请刷新后重试。",
        );
        setState("error");
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "error") {
    return (
      <main className="auth-screen">
        <Alert
          type="error"
          showIcon
          message="无法进入工作区"
          description={error}
        />
      </main>
    );
  }
  if (state !== "authenticated") {
    return (
      <main className="auth-screen" aria-live="polite">
        <Spin size="large" />
        <Typography.Text type="secondary">
          {state === "redirecting"
            ? "正在前往统一身份认证..."
            : "正在验证登录状态..."}
        </Typography.Text>
      </main>
    );
  }
  return children;
}
