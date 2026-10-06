"use client";

import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AuthFormShell,
  ErrorBanner,
  FormField,
  PrimaryButton,
  TextInput,
} from "@/components/AuthForm";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";

function LoginPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/canvas";

  const { login } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ identifier, password });
      router.replace(next);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          err.code === "invalid_credentials"
            ? "아이디 또는 비밀번호가 올바르지 않습니다."
            : err.message,
        );
      } else {
        setError("로그인에 실패했습니다. 네트워크 상태를 확인해주세요.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthFormShell
      title="로그인"
      subtitle="Eolgae 계정으로 로그인합니다."
      oauthRedirect={next}
      footer={
        <>
          아직 계정이 없으신가요?{" "}
          <Link
            href={`/signup${next !== "/canvas" ? `?next=${encodeURIComponent(next)}` : ""}`}
            style={{ color: "var(--color-accent)" }}
            className="font-medium hover:underline"
          >
            회원가입
          </Link>
        </>
      }
    >
      <form className="flex flex-col gap-3" onSubmit={onSubmit}>
        <FormField label="아이디 또는 이메일" htmlFor="identifier">
          <TextInput
            id="identifier"
            name="identifier"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            autoComplete="username"
            required
          />
        </FormField>
        <FormField label="비밀번호" htmlFor="password">
          <TextInput
            id="password"
            name="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </FormField>
        {error && <ErrorBanner message={error} />}
        <div className="mt-2">
          <PrimaryButton type="submit" loading={submitting}>
            로그인
          </PrimaryButton>
        </div>
      </form>
    </AuthFormShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageInner />
    </Suspense>
  );
}
