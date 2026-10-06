"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import {
  ApiError,
  fetchMe,
  getAccessToken,
  login as apiLogin,
  logout as apiLogout,
  signup as apiSignup,
  setAccessToken,
  setUnauthorizedHandler,
  type AuthUser,
  type LoginPayload,
  type SignupPayload,
  type TokenResponse,
} from "@/lib/api";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  user: AuthUser | null;
  status: AuthStatus;
  login: (payload: LoginPayload) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // 초기 1회만 me 조회
  const initRan = useRef(false);

  const applyToken = useCallback((tokens: TokenResponse) => {
    setAccessToken(tokens.access_token);
    setUser(tokens.user);
    setStatus("authenticated");
  }, []);

  const clear = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const login = useCallback(
    async (payload: LoginPayload) => {
      const tokens = await apiLogin(payload);
      applyToken(tokens);
    },
    [applyToken],
  );

  const signup = useCallback(
    async (payload: SignupPayload) => {
      const tokens = await apiSignup(payload);
      applyToken(tokens);
    },
    [applyToken],
  );

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // 네트워크/만료 무시 — 어차피 클라이언트 측 clear
    }
    clear();
  }, [clear]);

  // 401 → refresh 실패 시 호출됨
  useEffect(() => {
    setUnauthorizedHandler(() => {
      clear();
    });
    return () => setUnauthorizedHandler(null);
  }, [clear]);

  // 초기 진입: OAuth callback (?access_token=...) 흡수 또는 refresh 시도
  const refresh = useCallback(async () => {
    // 1. URL 의 access_token 우선 (OAuth callback)
    const tokenFromUrl = searchParams.get("access_token");
    if (tokenFromUrl) {
      setAccessToken(tokenFromUrl);
      try {
        const me = await fetchMe();
        setUser(me);
        setStatus("authenticated");
      } catch {
        clear();
      }
      // URL 정리 — token query 제거
      const params = new URLSearchParams(searchParams.toString());
      params.delete("access_token");
      params.delete("expires_in");
      const queryString = params.toString();
      router.replace(queryString ? `${pathname}?${queryString}` : pathname);
      return;
    }

    // 2. 기존 access_token 있으면 그걸로 me 시도
    if (getAccessToken()) {
      try {
        const me = await fetchMe();
        setUser(me);
        setStatus("authenticated");
        return;
      } catch {
        // fall through to refresh attempt
      }
    }

    // 3. refresh cookie 로 갱신 시도. api.request 가 401 → refresh 자동 처리하므로
    //    fetchMe() 가 refresh 시도 후 성공/실패 분기. 실패 시 401 throw.
    try {
      const me = await fetchMe();
      setUser(me);
      setStatus("authenticated");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        clear();
      } else {
        // 네트워크 오류 — unauthenticated 로 처리하고 다음 시도에 복구
        clear();
      }
    }
  }, [searchParams, router, pathname, clear]);

  useEffect(() => {
    if (initRan.current) return;
    initRan.current = true;
    void refresh();
  }, [refresh]);

  return (
    <AuthContext.Provider
      value={{ user, status, login, signup, logout, refresh }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
