"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

/**
 * 우측 상단 사용자 메뉴. 미인증 → "로그인" 링크, 인증 → display_name 드롭다운.
 */
export function UserMenu() {
  const { user, status, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  if (status === "loading") {
    return (
      <div
        className="h-9 w-24 rounded-md"
        style={{ background: "var(--color-bg-subtle)" }}
      />
    );
  }

  if (status === "unauthenticated") {
    const next = encodeURIComponent(pathname);
    return (
      <Link
        href={`/login?next=${next}`}
        className="rounded-md px-3 py-1.5 text-sm font-medium transition-colors"
        style={{
          color: "var(--color-accent)",
          background: "var(--color-accent-soft)",
        }}
      >
        로그인
      </Link>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors"
        style={{
          background: "var(--color-surface)",
          color: "var(--color-text)",
          borderColor: "var(--color-border)",
        }}
      >
        <span
          className="inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold"
          style={{
            background: "var(--color-accent)",
            color: "var(--color-accent-fg)",
          }}
        >
          {(user?.display_name || user?.username || "?")
            .slice(0, 1)
            .toUpperCase()}
        </span>
        {user?.display_name || user?.username}
      </button>

      {open && (
        <div
          className="absolute right-0 top-full z-50 mt-1 w-48 rounded-md border py-1 shadow-md"
          style={{
            background: "var(--color-surface-raised)",
            borderColor: "var(--color-border)",
          }}
        >
          <MenuItem
            onClick={() => {
              setOpen(false);
              router.push("/settings");
            }}
          >
            환경설정
          </MenuItem>
          <div
            className="my-1 h-px"
            style={{ background: "var(--color-border)" }}
          />
          <MenuItem
            onClick={async () => {
              setOpen(false);
              await logout();
              router.push("/login");
            }}
          >
            로그아웃
          </MenuItem>
        </div>
      )}
    </div>
  );
}

function MenuItem({
  onClick,
  children,
}: {
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="block w-full px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--color-bg-subtle)]"
      style={{ color: "var(--color-text)" }}
    >
      {children}
    </button>
  );
}
