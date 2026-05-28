import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { Route, Routes, Navigate, useLocation } from "react-router-dom";

import client from "./api/client";
import Layout from "./components/Layout/Navbar";
import useTelegramWebApp from "./hooks/useTelegramWebApp";
import useTelegramAuth, { isTelegramWebApp } from "./hooks/useTelegramAuth";
import useTelegramBackButton from "./hooks/useTelegramBackButton";
import Home from "./pages/Home";

// Lazy-load secondary pages — they are NOT needed on first paint
const Landing  = lazy(() => import("./pages/Landing"));
const Profile  = lazy(() => import("./pages/Profile"));
const Referral = lazy(() => import("./pages/Referral"));
const Saves    = lazy(() => import("./pages/Saves"));
const Admin    = lazy(() => import("./pages/Admin"));
const Wallet   = lazy(() => import("./pages/Wallet"));

function PageFallback() {
  return <div className="flex h-40 items-center justify-center text-sm text-slate-400">Yuklanmoqda...</div>;
}

function resolveEntryTarget(pathname: string, search: string): "home" | "profile" | "saves" {
  const go = (new URLSearchParams(search).get("go") || "").toLowerCase();
  if (go === "profile") return "profile";
  if (go === "saves") return "saves";

  const startParam = (window.Telegram?.WebApp?.initDataUnsafe?.start_param || "").toLowerCase();
  if (startParam === "profile") return "profile";
  if (startParam === "saves") return "saves";
  if (startParam === "home" || startParam === "app" || startParam === "jobs") return "home";

  if (pathname === "/profile") return "profile";
  if (pathname === "/saves") return "saves";

  return "home";
}

function AppHomeEntry() {
  const location = useLocation();
  const target = resolveEntryTarget(location.pathname, location.search);

  if (target === "profile") {
    return <Navigate to="/profile" replace />;
  }

  if (target === "saves") {
    return <Navigate to="/saves" replace />;
  }

  return <Layout><Home /></Layout>;
}

function ReferralLockScreen({ current, required, refLink }: { current: number; required: number; refLink: string }) {
  return (
    <div className="mx-auto mt-6 max-w-xl space-y-3 px-4">
      <div className="card p-5 text-center">
        <p className="text-base font-semibold text-slate-800">🔒 Referral sharti yoqilgan</p>
        <p className="mt-2 text-sm text-slate-500">
          Webappdan foydalanish uchun avval referral shartini bajaring.
        </p>
        <p className="mt-3 text-sm font-semibold text-amber-600">Holat: {current}/{required}</p>
        <a href={refLink} className="mt-4 inline-block rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
          Referral havolani ulashish
        </a>
      </div>
    </div>
  );
}

export default function App() {
  useTelegramWebApp();
  useTelegramBackButton();
  useTelegramAuth();

  const gate = useQuery({
    queryKey: ["referral", "stats", "gate"],
    queryFn: async () => {
      const { data } = await client.get<{ enabled: boolean; unlocked: boolean; current: number; required: number; ref_link: string }>(
        "/referral/stats"
      );
      return data;
    },
    retry: false,
    enabled: isTelegramWebApp(),
  });

  // External browser — always show landing page
  if (!isTelegramWebApp()) {
    return (
      <Suspense fallback={<PageFallback />}>
        <Landing />
      </Suspense>
    );
  }

  if (gate.data?.enabled && !gate.data.unlocked) {
    return <ReferralLockScreen current={gate.data.current} required={gate.data.required} refLink={gate.data.ref_link} />;
  }

  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<Navigate to="/app" replace />} />
        <Route path="/app" element={<AppHomeEntry />} />
        <Route path="/saves" element={<AppHomeEntry />} />
        <Route path="/profile" element={<AppHomeEntry />} />
        <Route path="/wallet" element={<Layout><Wallet /></Layout>} />
        <Route path="/admin" element={<Layout><Admin /></Layout>} />
        <Route path="/referral" element={<Layout><Referral /></Layout>} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </Suspense>
  );
}

