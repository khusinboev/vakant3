import { useEffect } from "react";
import { Navigate, Route, Routes, useNavigate, useSearchParams } from "react-router-dom";

import client from "./api/client";
import Layout from "./components/Layout/Navbar";
import useTelegramWebApp from "./hooks/useTelegramWebApp";
import Home from "./pages/Home";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import Referral from "./pages/Referral";
import Saves from "./pages/Saves";
import { useAuthStore } from "./store/auth";
import type { UserProfile } from "./types";

type AuthResponse = { session_token: string; user: UserProfile };

function HandoffExpired() {
  return (
    <div className="flex min-h-[var(--app-viewport-height)] items-center justify-center p-4 pb-[calc(1rem+var(--tg-content-safe-area-bottom))] pt-[calc(1rem+var(--tg-content-safe-area-top))]">
      <div className="card w-full max-w-md p-6 text-center">
        <p className="font-display text-2xl font-extrabold text-brand-700">Havola eskirgan</p>
        <p className="mt-3 text-sm text-slate-600">
          Bu havola bir martalik va qisqa muddatli. Botga qayting va /start ni qayta bosing.
        </p>
      </div>
    </div>
  );
}

function HandoffHandler() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    const token = params.get("token");
    if (!token) return;

    const handoffKey = `handoff_used_${token}`;
    if (sessionStorage.getItem(handoffKey) === "1") {
      navigate("/app", { replace: true });
      return;
    }

    sessionStorage.setItem(handoffKey, "1");
    // Remove param from URL immediately to avoid re-use on refresh
    window.history.replaceState({}, "", "/app");
    void (async () => {
      try {
        const { data } = await client.post<AuthResponse>("/auth/handoff", { token });
        setSession(data.session_token, data.user);
        navigate("/app", { replace: true });
      } catch {
        const existingSession = localStorage.getItem("session_token");
        if (existingSession) {
          navigate("/app", { replace: true });
          return;
        }
        navigate("/handoff-expired", { replace: true });
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (isAuthenticated) return <Navigate to="/" replace />;
  return (
    <div className="flex min-h-[var(--app-viewport-height)] items-center justify-center px-4 pb-[calc(1rem+var(--tg-content-safe-area-bottom))] pt-[calc(1rem+var(--tg-content-safe-area-top))] text-sm text-slate-500">
      Kirish...
    </div>
  );
}

function PrivateRoute({ children }: { children: JSX.Element }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export default function App() {
  useTelegramWebApp();
  const setUser = useAuthStore((s) => s.setUser);
  const clearSession = useAuthStore((s) => s.clearSession);

  useEffect(() => {
    const token = localStorage.getItem("session_token");
    if (!token) {
      setUser(null);
      return;
    }

    void (async () => {
      try {
        const { data } = await client.get<UserProfile>("/auth/me");
        setUser(data);
      } catch {
        clearSession();
      }
    })();
  }, [setUser, clearSession]);

  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      {/* Bot /start havolasi: /handoff?token=xxx → auto login */}
      <Route path="/handoff" element={<HandoffHandler />} />
      <Route path="/handoff-expired" element={<HandoffExpired />} />
      <Route
        path="/app"
        element={
          <Layout>
            <Home />
          </Layout>
        }
      />
      <Route
        path="/saves"
        element={
          <PrivateRoute>
            <Layout>
              <Saves />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <PrivateRoute>
            <Layout>
              <Profile />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/referral"
        element={
          <PrivateRoute>
            <Layout>
              <Referral />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
