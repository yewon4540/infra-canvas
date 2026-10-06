"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

/**
 * 루트(/) — 진입 분기만. 로그인됨 → /canvas, 아니면 → /login.
 * 메인 랜딩 페이지는 나중에 꾸밈 (현재는 thin redirect).
 */
export default function RootPage() {
  const router = useRouter();
  const { status } = useAuth();

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/canvas");
    } else if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  return (
    <div
      className="flex min-h-screen items-center justify-center text-sm"
      style={{ color: "var(--color-text-subtle)" }}
    >
      로딩중...
    </div>
  );
}
