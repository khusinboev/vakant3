import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { Route, Routes, Navigate, useLocation } from "react-router-dom";

import client from "./api/client";
import ErrorBoundary from "./components/ErrorBoundary";
import Layout from "./components/Layout/Layout";
import { ToastHost } from "./hooks/useToast";
import useTelegramWebApp from "./hooks/useTelegramWebApp";
import useTelegramAuth, { isTelegramWebApp } from "./hooks/useTelegramAuth";
import useTelegramBackButton from "./hooks/useTelegramBackButton";
import useTheme from "./hooks/useTheme";
import { useT } from "./i18n/useT";
import { shareRefLink } from "./lib/share";
import { useAuthStore } from "./store/auth";
import Home from "./pages/Home";

// Lazy-load secondary pages — they are NOT needed on first paint
const Landing  = lazy(() => import("./pages/Landing"));
const Profile  = lazy(() => import("./pages/Profile"));
const Referral = lazy(() => import("./pages/Referral"));
const Saves    = lazy(() => import("./pages/Saves"));
const Admin    = lazy(() => import("./pages/Admin"));
const Wallet   = lazy(() => import("./pages/Wallet"));
const Hub      = lazy(() => import("./pages/Hub"));
const ResumeStudio = lazy(() => import("./pages/ResumeStudio"));
const Laws         = lazy(() => import("./pages/Laws"));

function PageFallback() {
  const t = useT();
  return (
    <div className="flex h-40 items-center justify-center text-sm text-muted">
      {t("common.loading")}
    </div>
  );
}

function resolveEntryTarget(search: string): "home" | "profile" | "saves" {
  const go = (new URLSearchParams(search).get("go") || "").toLowerCase();
  if (go === "profile") return "profile";
  if (go === "saves") return "saves";

  const startParam = (window.Telegram?.WebApp?.initDataUnsafe?.start_param || "").toLowerCase();
  if (startParam === "profile") return "profile";
  if (startParam === "saves") return "saves";
  if (startParam === "home" || startParam === "app" || startParam === "jobs") return "home";

  return "home";
}

function AppHomeEntry() {
  const location = useLocation();
  const target = resolveEntryTarget(location.search);

  if (target === "profile") {
    return <Navigate to="/profile" replace />;
  }

  if (target === "saves") {
    return <Navigate to="/saves" replace />;
  }

  return <Layout><Home /></Layout>;
}

function ReferralLockScreen({ current, required, refLink }: { current: number; required: number; refLink: string }) {
  const t = useT();
  return (
    <div className="mx-auto mt-6 max-w-xl space-y-3 px-4">
      <div className="card p-5 text-center">
        <p className="text-base font-semibold text-text">🔒 {t("app.referralLockTitle")}</p>
        <p className="mt-2 text-sm text-muted">{t("app.referralLockBody")}</p>
        <p className="mt-3 text-sm font-semibold text-warning">
          {t("app.referralLockStatus", { current, required })}
        </p>
        <button
          type="button"
          onClick={() => shareRefLink(refLink, t("referral.shareText"))}
          className="tap-target mt-4 inline-block rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-primaryFg"
        >
          {t("app.referralLockShare")}
        </button>
      </div>
    </div>
  );
}

type GateData = {
  enabled: boolean;
  unlocked: boolean;
  current: number;
  required: number;
  ref_link: string;
};

export default function App() {
  useTheme();
  useTelegramWebApp();
  useTelegramBackButton();
  useTelegramAuth();

  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const gate = useQuery<GateData>({
    queryKey: ["referral", "stats", "gate"],
    queryFn: async () => {
      const { data } = await client.get<GateData>("/referral/stats");
      return data;
    },
    retry: false,
    // The gate is a per-user check: asking before auth resolves always 401s.
    enabled: isTelegramWebApp() && isAuthenticated,
  });

  // External browser — always show landing page
  if (!isTelegramWebApp()) {
    return (
      <>
        <ErrorBoundary>
          <Suspense fallback={<PageFallback />}>
            <Landing />
          </Suspense>
        </ErrorBoundary>
        <ToastHost />
      </>
    );
  }

  if (gate.data?.enabled && !gate.data.unlocked) {
    return (
      <>
        <ReferralLockScreen
          current={gate.data.current}
          required={gate.data.required}
          refLink={gate.data.ref_link}
        />
        <ToastHost />
      </>
    );
  }

  return (
    <>
      <ErrorBoundary>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/" element={<Navigate to="/app" replace />} />
            <Route path="/app" element={<AppHomeEntry />} />
            <Route path="/saves" element={<Layout><ErrorBoundary><Saves /></ErrorBoundary></Layout>} />
            <Route path="/profile" element={<Layout><ErrorBoundary><Profile /></ErrorBoundary></Layout>} />
            <Route path="/hub" element={<Layout><ErrorBoundary><Hub /></ErrorBoundary></Layout>} />
            <Route path="/hub/resume" element={<ErrorBoundary><ResumeStudio /></ErrorBoundary>} />
            <Route path="/hub/laws" element={<Layout><ErrorBoundary><Laws /></ErrorBoundary></Layout>} />
            <Route path="/wallet" element={<Layout><ErrorBoundary><Wallet /></ErrorBoundary></Layout>} />
            <Route path="/admin" element={<Layout><ErrorBoundary><Admin /></ErrorBoundary></Layout>} />
            <Route path="/referral" element={<Layout><ErrorBoundary><Referral /></ErrorBoundary></Layout>} />
            <Route path="*" element={<Navigate to="/app" replace />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
      <ToastHost />
    </>
  );
}
