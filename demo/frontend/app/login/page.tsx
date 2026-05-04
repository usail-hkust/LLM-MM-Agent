"use client";

import { useState } from "react";
import { Box, Lock, User as UserIcon } from "lucide-react";
import { useAuth } from "@/app/context/AuthContext";
import { useRouter } from "next/navigation";

const allowPublicRegistration = process.env.NEXT_PUBLIC_ALLOW_PUBLIC_REGISTRATION !== "false";
const defaultLoginEmail = process.env.NEXT_PUBLIC_DEFAULT_LOGIN_EMAIL || "";
const defaultLoginPassword = process.env.NEXT_PUBLIC_DEFAULT_LOGIN_PASSWORD || "";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { loginWithCredentials } = useAuth();
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await loginWithCredentials(username, password);
    } catch (err: any) {
      setError(err.message || "Login failed. Check credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#f3f6ff] via-white to-[#f7f5ff] flex items-center justify-center p-4">
      <div className="bg-white p-8 rounded-2xl shadow-xl border border-gray-100 w-full max-w-md space-y-8">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-black text-white mb-4">
            <Box className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Welcome Back</h1>
          <p className="text-gray-500 text-sm">Sign in to your locally deployed MM-Agent workspace</p>
        </div>

        {(defaultLoginEmail || defaultLoginPassword) && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <div className="font-semibold">Default local account</div>
            <div className="mt-1 font-mono">
              {defaultLoginEmail || "not-set"} / {defaultLoginPassword || "not-set"}
            </div>
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-6">
          <div className="space-y-4">
            <div className="relative">
              <UserIcon className="absolute left-3 top-3 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-black/5 focus:border-gray-400 transition-all"
                placeholder="Email Address"
                required
              />
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-3 w-5 h-5 text-gray-400" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-black/5 focus:border-gray-400 transition-all"
                placeholder="Password"
                required
              />
            </div>
          </div>

          {error && (
            <div className="text-red-500 text-sm bg-red-50 p-3 rounded-lg border border-red-100">
              {error}
            </div>
          )}

          <div className="space-y-3">
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-black text-white py-2.5 rounded-lg font-bold hover:bg-gray-800 transition-colors disabled:opacity-50"
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
            
            {allowPublicRegistration && (
              <div className="pt-2 text-center text-sm">
                  <span className="text-gray-500">Don't have an account? </span>
                  <button
                    type="button"
                    onClick={() => router.push("/register")}
                    className="font-bold text-black hover:underline"
                  >
                    Sign up
                  </button>
              </div>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
