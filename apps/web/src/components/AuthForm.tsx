"use client";

import Link from "next/link";
import {
  buildOAuthStartUrl,
  type OAuthProvider,
} from "@/lib/api";
import type { ReactNode } from "react";

/**
 * 로그인 / 회원가입 공통 레이아웃.
 * 자체 ID/PW 폼은 children 으로 받고, OAuth 버튼 영역은 컴포넌트가 박음.
 */
export function AuthFormShell({
  title,
  subtitle,
  children,
  footer,
  oauthRedirect = "/canvas",
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
  oauthRedirect?: string;
}) {
  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ background: "var(--color-bg-subtle)" }}
    >
      <div
        className="w-full max-w-md rounded-xl border p-8 shadow-sm"
        style={{
          background: "var(--color-surface)",
          borderColor: "var(--color-border)",
        }}
      >
        <Link
          href="/"
          className="block text-2xl font-semibold mb-1"
          style={{ color: "var(--color-text)" }}
        >
          Eolgae
        </Link>
        <h1
          className="text-lg font-semibold mt-4"
          style={{ color: "var(--color-text)" }}
        >
          {title}
        </h1>
        <p
          className="text-sm mt-1 mb-6"
          style={{ color: "var(--color-text-muted)" }}
        >
          {subtitle}
        </p>

        {children}

        <div className="mt-6 flex items-center gap-3">
          <div
            className="flex-1 h-px"
            style={{ background: "var(--color-border)" }}
          />
          <span
            className="text-xs"
            style={{ color: "var(--color-text-subtle)" }}
          >
            또는
          </span>
          <div
            className="flex-1 h-px"
            style={{ background: "var(--color-border)" }}
          />
        </div>

        <div className="mt-4 flex flex-col gap-2">
          <OAuthButton provider="github" redirect={oauthRedirect}>
            GitHub 로 계속
          </OAuthButton>
          <OAuthButton provider="google" redirect={oauthRedirect}>
            Google 로 계속
          </OAuthButton>
        </div>

        <div
          className="mt-6 text-sm text-center"
          style={{ color: "var(--color-text-muted)" }}
        >
          {footer}
        </div>
      </div>
    </div>
  );
}

function OAuthButton({
  provider,
  redirect,
  children,
}: {
  provider: OAuthProvider;
  redirect: string;
  children: ReactNode;
}) {
  // BE 가 503 (provider 미설정) 반환 시: 페이지 이동 후 에러 보임.
  // 1차에선 별도 사전 체크 없이 단순 redirect.
  const href = buildOAuthStartUrl(provider, redirect);
  return (
    <a
      href={href}
      className="w-full inline-flex items-center justify-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors hover:opacity-90"
      style={{
        background: "var(--color-surface-raised)",
        color: "var(--color-text)",
        borderColor: "var(--color-border)",
      }}
    >
      {children}
    </a>
  );
}

export function FormField({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={htmlFor}
        className="text-xs font-medium"
        style={{ color: "var(--color-text)" }}
      >
        {label}
      </label>
      {children}
      {hint && (
        <span
          className="text-xs"
          style={{ color: "var(--color-text-subtle)" }}
        >
          {hint}
        </span>
      )}
    </div>
  );
}

export function TextInput(
  props: React.InputHTMLAttributes<HTMLInputElement>,
) {
  return (
    <input
      {...props}
      className={
        "rounded-md border px-3 py-2 text-sm outline-none focus:border-[color:var(--color-accent)] " +
        (props.className || "")
      }
      style={{
        background: "var(--color-surface)",
        color: "var(--color-text)",
        borderColor: "var(--color-border-strong)",
      }}
    />
  );
}

export function PrimaryButton({
  loading,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) {
  return (
    <button
      {...props}
      disabled={loading || props.disabled}
      className={
        "w-full rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:opacity-60 disabled:cursor-not-allowed hover:opacity-90 " +
        (props.className || "")
      }
      style={{
        background: "var(--color-accent)",
        color: "var(--color-accent-fg)",
      }}
    >
      {loading ? "처리 중…" : children}
    </button>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      className="mt-3 rounded-md border px-3 py-2 text-sm"
      style={{
        background: "color-mix(in srgb, var(--color-danger) 10%, transparent)",
        color: "var(--color-danger)",
        borderColor:
          "color-mix(in srgb, var(--color-danger) 30%, transparent)",
      }}
    >
      {message}
    </div>
  );
}
