import { lazy, Suspense } from "react";
import { Route, Routes, Navigate } from "react-router-dom";

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

function PageFallback() {
  return <div className="flex h-40 items-center justify-center text-sm text-slate-400">Yuklanmoqda...</div>;
}

export default function App() {
  useTelegramWebApp();
  useTelegramAuth();
  useTelegramBackButton();

  // External browser — always show landing page
  if (!isTelegramWebApp()) {
    return (
      <Suspense fallback={<PageFallback />}>
        <Landing />
      </Suspense>
    );
  }

  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<Navigate to="/app" replace />} />
        <Route path="/app" element={<Layout><Home /></Layout>} />
        <Route path="/saves" element={<Layout><Saves /></Layout>} />
        <Route path="/profile" element={<Layout><Profile /></Layout>} />
        <Route path="/referral" element={<Layout><Referral /></Layout>} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </Suspense>
  );
}

