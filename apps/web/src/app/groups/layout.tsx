"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { useAuth } from "@/lib/auth-context";

/**
 * /groups/* opt-in 인증 가드.
 * 다른 경로(/, /canvas/[id], /trash)는 영향 받지 않음.
 */
export default function GroupsLayout({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [status, router, pathname]);

  if (status !== "authenticated") {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "var(--color-bg-subtle)" }}
      >
        <p
          className="text-sm"
          style={{ color: "var(--color-text-muted)" }}
        >
          {status === "loading" ? "로딩 중…" : "로그인이 필요합니다…"}
        </p>
      </div>
    );
  }

  return <WorkspaceShell active="settings">{children}</WorkspaceShell>;
}
