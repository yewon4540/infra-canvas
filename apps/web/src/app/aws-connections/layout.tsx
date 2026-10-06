"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { useAuth } from "@/lib/auth-context";

export default function AwsConnectionsLayout({
  children,
}: {
  children: ReactNode;
}) {
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
        className="flex min-h-screen items-center justify-center"
        style={{ background: "var(--color-bg-subtle)" }}
      >
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {status === "loading" ? "로딩 중…" : "로그인이 필요합니다…"}
        </p>
      </div>
    );
  }

  return <WorkspaceShell active="settings">{children}</WorkspaceShell>;
}
