"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, getToken, setToken } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!getToken()) {
      setReady(true);
      return undefined;
    }
    api("/auth/me")
      .then((me) => !cancelled && setUser(me))
      .catch(() => setToken(null))
      .finally(() => !cancelled && setReady(true));
    const onExpired = () => setUser(null);
    window.addEventListener("vs-auth-expired", onExpired);
    return () => {
      cancelled = true;
      window.removeEventListener("vs-auth-expired", onExpired);
    };
  }, []);

  const signIn = useCallback(async (path, body) => {
    const data = await api(path, { method: "POST", body });
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const value = {
    user,
    ready,
    isCoordinator: user?.role === "coordinator",
    login: (email, password) => signIn("/auth/login", { email, password }),
    register: (name, email, password) => signIn("/auth/register", { name, email, password }),
    logout: () => {
      setToken(null);
      setUser(null);
    },
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

/** Pages call this: it redirects to /login when signed out and reports when it is safe to render. */
export function useRequireAuth({ coordinatorOnly = false } = {}) {
  const auth = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!auth.ready) return;
    if (!auth.user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    else if (coordinatorOnly && !auth.isCoordinator) router.replace("/");
  }, [auth.ready, auth.user, auth.isCoordinator, coordinatorOnly, pathname, router]);

  const allowed = auth.ready && auth.user && (!coordinatorOnly || auth.isCoordinator);
  return { ...auth, allowed };
}
