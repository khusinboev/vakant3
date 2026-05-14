import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import client from "./api/client";
import Layout from "./components/Layout/Navbar";
import useTelegramWebApp from "./hooks/useTelegramWebApp";
import useTelegramAuth, { isTelegramWebApp } from "./hooks/useTelegramAuth";
import Home from "./pages/Home";
import Landing from "./pages/Landing";
import Profile from "./pages/Profile";
import Referral from "./pages/Referral";
import Saves from "./pages/Saves";
import { useAuthStore } from "./store/auth";
import type { UserProfile } from "./types";

export default function App() {
  useTelegramWebApp();
  useTelegramAuth();

  const setUser = useAuthStore((s) => s.setUser);
  const clearSession = useAuthStore((s) => s.clearSession);

  // If opened in external browser, skip /auth/me — no session possible
  const inTelegram = isTelegramWebApp();

  useEffect(() => {
    if (!inTelegram) return;

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
  }, [setUser, clearSession, inTelegram]);

  // External browser — always show landing page
  if (!inTelegram) {
    return <Landing />;
  }

  return (
    <Routes>
      <Route path="/" element={<Navigate to="/app" replace />} />
      <Route path="/app" element={<Layout><Home /></Layout>} />
      <Route path="/saves" element={<Layout><Saves /></Layout>} />
      <Route path="/profile" element={<Layout><Profile /></Layout>} />
      <Route path="/referral" element={<Layout><Referral /></Layout>} />
      <Route path="*" element={<Navigate to="/app" replace />} />
    </Routes>
  );
}

