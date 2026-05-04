"use client";

import { createContext, useContext, useEffect, useState, ReactNode, useCallback, useMemo } from "react";
import { usePathname, useRouter } from "next/navigation";

interface User {
  username: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string, token: string) => void;
  loginWithCredentials: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

// [Resilience] Safe JSON Parser to prevent crash on corrupted storage
function safeJSONParse<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  const item = localStorage.getItem(key);
  if (!item) return null;

  try {
    return JSON.parse(item);
  } catch (error) {
    console.error(`[AuthContext] Failed to parse ${key}, clearing corrupted data.`, error);
    localStorage.removeItem(key);
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const storedToken = localStorage.getItem("mm_token");
        const storedUser = safeJSONParse<User>("mm_user");

        if (storedToken && storedUser) {
          setToken(storedToken);
          setUser(storedUser);
        } else {
          if (storedToken || localStorage.getItem("mm_user")) {
            console.warn("[AuthContext] Inconsistent auth state detected. Logging out.");
            localStorage.removeItem("mm_token");
            localStorage.removeItem("mm_user");
          }
        }
      } catch (e) {
        console.error("[AuthContext] Critical initialization error:", e);
      } finally {
        setIsLoading(false);
      }
    };

    // [FIX] Safety Timeout: Force finish loading after 5 seconds to prevent blank screen hang
    const timeoutId = setTimeout(() => {
      setIsLoading((loading) => {
        if (loading) {
          console.warn("[AuthContext] Initialization timed out. Forcing app load.");
          return false;
        }
        return loading;
      });
    }, 5000);

    initializeAuth();

    return () => clearTimeout(timeoutId);
  }, []);

  // Redirect unauthenticated users to login anywhere in the app
  useEffect(() => {
    if (isLoading) return;

    // 定义公共路径白名单，包含首页、login 和 register
    const publicPaths = ["/", "/login", "/register"];
    const isPublicPage = publicPaths.includes(pathname);

    // 如果用户未登录，且当前不在公共页面，则重定向
    if (!user && !isPublicPage) {
      router.replace("/login");
    }
  }, [isLoading, pathname, router, user]);

  const login = useCallback((username: string, newToken: string) => {
    const userData = { username };
    setUser(userData);
    setToken(newToken);
    localStorage.setItem("mm_token", newToken);
    localStorage.setItem("mm_user", JSON.stringify(userData));
    router.push("/");
  }, [router]);

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("mm_token");
    localStorage.removeItem("mm_user");
    router.push("/login");
  }, [router]);

  const loginWithCredentials = useCallback(async (username: string, password: string) => {
    const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const res = await fetch(`${API_BASE}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData.toString(),
    });

    if (!res.ok) throw new Error("Login failed");
    const data = await res.json();
    login(username, data.access_token);
  }, [login]);

  // [FIX] Listen for Unauthorized event from api-client
  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("auth:unauthorized", handleUnauthorized);
  }, [logout]);

  const value = useMemo(() => ({
    user,
    token,
    login,
    loginWithCredentials,
    logout,
    isLoading
  }), [user, token, login, loginWithCredentials, logout, isLoading]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
