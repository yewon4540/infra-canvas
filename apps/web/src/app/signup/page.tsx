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
import { MIN_PASSWORD_LENGTH } from "@/lib/constants";

const USERNAME_PATTERN = /^[a-zA-Z0-9_-]{3,64}$/;
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function SignupPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/canvas";

  const { signup } = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!USERNAME_PATTERN.test(username)) {
      setError("아이디는 영문/숫자/-/_ 만, 3~64자.");
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`비밀번호는 ${MIN_PASSWORD_LENGTH}자 이상이어야 합니다.`);
      return;
    }
    if (password !== passwordConfirm) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }
    if (email.trim() && !EMAIL_PATTERN.test(email.trim())) {
      setError("이메일 형식이 올바르지 않습니다. 비워두셔도 됩니다.");
      return;
    }

    setSubmitting(true);
    try {
      await signup({
        username,
        password,
        email: email.trim() || undefined,
        display_name: displayName.trim() || undefined,
      });
      router.replace(next);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "username_taken") setError("이미 사용 중인 아이디입니다.");
        else if (err.code === "email_taken") setError("이미 사용 중인 이메일입니다.");
        else setError(err.message);
      } else {
        setError("회원가입에 실패했습니다.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthFormShell
      title="회원가입"
      subtitle="새 Eolgae 계정을 만듭니다."
      oauthRedirect={next}
      footer={
        <>
          이미 계정이 있으신가요?{" "}
          <Link
            href={`/login${next !== "/canvas" ? `?next=${encodeURIComponent(next)}` : ""}`}
            style={{ color: "var(--color-accent)" }}
            className="font-medium hover:underline"
          >
            로그인
          </Link>
        </>
      }
    >
      <form className="flex flex-col gap-3" onSubmit={onSubmit}>
        <FormField label="아이디" htmlFor="username" hint="영문/숫자/-/_ 3~64자">
          <TextInput
            id="username"
            name="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            minLength={3}
            maxLength={64}
            pattern="[a-zA-Z0-9_-]+"
            autoComplete="username"
            required
          />
        </FormField>
        <FormField label="표시 이름" htmlFor="display_name" hint="비워두면 아이디와 동일">
          <TextInput
            id="display_name"
            name="display_name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            maxLength={100}
          />
        </FormField>
        <FormField label="이메일 (선택)" htmlFor="email">
          <TextInput
            id="email"
            name="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            maxLength={255}
            autoComplete="email"
          />
        </FormField>
        <FormField label="비밀번호" htmlFor="password" hint={`${MIN_PASSWORD_LENGTH}자 이상`}>
          <TextInput
            id="password"
            name="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            required
          />
        </FormField>
        <FormField label="비밀번호 확인" htmlFor="password_confirm">
          <TextInput
            id="password_confirm"
            name="password_confirm"
            type="password"
            value={passwordConfirm}
            onChange={(e) => setPasswordConfirm(e.target.value)}
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            required
          />
        </FormField>
        {error && <ErrorBanner message={error} />}
        <div className="mt-2">
          <PrimaryButton type="submit" loading={submitting}>
            가입하고 시작하기
          </PrimaryButton>
        </div>
      </form>
    </AuthFormShell>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={null}>
      <SignupPageInner />
    </Suspense>
  );
}
