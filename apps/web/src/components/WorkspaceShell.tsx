"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UserMenu } from "@/components/UserMenu";

export type WorkspaceSection = "dashboard" | "canvas" | "settings";

type WorkspaceShellProps = {
  active: WorkspaceSection;
  onSectionChange?: (section: WorkspaceSection) => void;
  children: ReactNode;
};

export function WorkspaceShell({
  active,
  onSectionChange,
  children,
}: WorkspaceShellProps) {
  return (
    <div className="min-h-screen bg-[var(--color-bg)] lg:flex">
      <aside className="border-b border-[var(--color-border)] bg-[var(--color-surface)] lg:sticky lg:top-0 lg:h-screen lg:w-60 lg:shrink-0 lg:border-b-0 lg:border-r">
        <div className="flex h-full flex-col">
          <div className="border-b border-[var(--color-border)] px-5 py-5">
            <Link
              href="/canvas"
              className="text-base font-bold tracking-tight text-[var(--color-text)]"
              onClick={(event) => {
                if (!onSectionChange) return;
                event.preventDefault();
                onSectionChange("dashboard");
              }}
            >
              Eolgae
            </Link>
            <div className="mt-1 text-xs text-[var(--color-text-subtle)]">
              Infrastructure workspace
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 py-3 lg:flex-col lg:overflow-visible">
            <WorkspaceNavItem
              active={active === "dashboard"}
              href="/canvas"
              label="대시보드"
              onClick={
                onSectionChange
                  ? () => onSectionChange("dashboard")
                  : undefined
              }
            />
            <WorkspaceNavItem
              active={active === "canvas"}
              href="/canvas"
              label="캔버스"
              onClick={
                onSectionChange ? () => onSectionChange("canvas") : undefined
              }
            />
            <WorkspaceNavItem
              active={active === "settings"}
              href="/settings"
              label="환경설정"
            />
          </nav>
          <div className="mt-auto hidden border-t border-[var(--color-border)] p-4 text-xs leading-relaxed text-[var(--color-text-subtle)] lg:block">
            Apply, Destroy, Target health, 최근 변경 내역을 대시보드에 연결합니다.
          </div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-5 py-6 lg:px-8">{children}</main>
    </div>
  );
}

function WorkspaceNavItem({
  active,
  href,
  label,
  onClick,
}: {
  active: boolean;
  href: string;
  label: string;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={(event) => {
        if (!onClick) return;
        event.preventDefault();
        onClick();
      }}
      className={
        active
          ? "whitespace-nowrap rounded-md bg-[var(--color-accent)] px-3 py-2 text-sm font-semibold text-[var(--color-accent-fg)]"
          : "whitespace-nowrap rounded-md px-3 py-2 text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-text)]"
      }
    >
      {label}
    </Link>
  );
}

export function WorkspaceHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--color-text)]">
          {title}
        </h1>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          {description}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <UserMenu />
        <ThemeToggle />
      </div>
    </div>
  );
}
