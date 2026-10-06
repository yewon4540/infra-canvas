"use client";

import { useEffect, useState } from "react";

type ThemeMode = "light" | "dark" | "system";

const STORAGE_KEY = "eolgae-theme";

function applyTheme(mode: ThemeMode) {
  const prefersDark = window.matchMedia(
    "(prefers-color-scheme: dark)",
  ).matches;
  const isDark = mode === "dark" || (mode === "system" && prefersDark);
  document.documentElement.classList.toggle("dark", isDark);
  document.documentElement.dataset.themeMode = mode;
}

export function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>("system");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = (localStorage.getItem(STORAGE_KEY) as ThemeMode) || "system";
    setMode(stored);
    setMounted(true);

    // 시스템 모드일 때 OS 설정 변경 감지
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const current =
        (localStorage.getItem(STORAGE_KEY) as ThemeMode) || "system";
      if (current === "system") applyTheme("system");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  function change(next: ThemeMode) {
    setMode(next);
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  if (!mounted) {
    // SSR/하이드레이션 직후엔 자리만 잡고 비워둠
    return <div className="h-7 w-[114px]" aria-hidden />;
  }

  const options: { value: ThemeMode; label: string; icon: string }[] = [
    { value: "light", label: "Light", icon: "☀" },
    { value: "system", label: "System", icon: "◐" },
    { value: "dark", label: "Dark", icon: "☾" },
  ];

  return (
    <div
      className="inline-flex items-center rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-0.5 text-xs"
      role="radiogroup"
      aria-label="테마 선택"
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          role="radio"
          aria-checked={mode === opt.value}
          onClick={() => change(opt.value)}
          title={opt.label}
          className={
            mode === opt.value
              ? "rounded-[3px] bg-[var(--color-accent)] px-2 py-1 font-medium text-[var(--color-accent-fg)]"
              : "rounded-[3px] px-2 py-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }
        >
          <span aria-hidden>{opt.icon}</span>
          <span className="sr-only">{opt.label}</span>
        </button>
      ))}
    </div>
  );
}
