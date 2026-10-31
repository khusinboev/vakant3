import { lazy, Suspense, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Route, Routes, Navigate, useLocation, useNavigate } from "react-router-dom";

import client from "./api/client";
import EntryLockScreen from "./components/EntryLockScreen";
import ErrorBoundary from "./components/ErrorBoundary";
import Layout from "./components/Layout/Layout";
import { ToastHost } from "./hooks/useToast";
import useTelegramWebApp from "./hooks/useTelegramWebApp";
import useTelegramAuth, { isTelegramWebApp } from "./hooks/useTelegramAuth";
import useTelegramBackButton from "./hooks/useTelegramBackButton";
import useTheme from "./hooks/useTheme";
import { useT } from "./i18n/useT";
import { consumeStartParam, resolveEntryTarget, vacancyToken, VACANCY_QUERY_KEY } from "./lib/deepLink";
import type { GateState } from "./lib/entryGate";
import { gateBlockReason } from "./lib/entryGate";
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

/**
 * A vacancy deep link (`?go=` / `start_param` = a vacancy token, see lib/deepLink) lands
 * on the job list with that vacancy's sheet open as its own history entry:
 * `/app` (replace) then `/app?vacancy=<token>` (push), so Back closes the sheet
 * and leaves the list underneath.
 */
function VacancyEntry({ uid }: { uid: string }) {
  const navigate = useNavigate();
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    navigate("/app", { replace: true });
    navigate(`/app?${VACANCY_QUERY_KEY}=${vacancyToken(uid) ?? ""}`, { state: { vacancySheet: true } });
  }, [navigate, uid]);
  return null;
}

function AppHomeEntry() {
  const location = useLocation();
  const target = resolveEntryTarget(location.search);

  // start_param stays in initData for the whole session: act on it once only.
  useEffect(() => {
    consumeStartParam();
  }, []);

  if (target.kind === "profile") {
    return <Navigate to="/profile" replace />;
  }

  if (target.kind === "saves") {
    return <Navigate to="/saves" replace />;
  }

  if (target.kind === "vacancy") {
    return <VacancyEntry uid={target.uid} />;
  }

  return <Layout><Home /></Layout>;
}

export default function App() {
  useTheme();
  useTelegramWebApp();
  useTelegramBackButton();
  useTelegramAuth();

  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // One server-side verdict for the whole entry flow: /start pressed, required
  // channels subscribed, referral condition met (webapp/core/entry_gate.py).
  // Every gated endpoint enforces the same thing, so this only picks the screen.
  const gate = useQuery<GateState>({
    queryKey: ["auth", "gate"],
    queryFn: async () => {
      const { data } = await client.get<GateState>("/auth/gate");
      return data;
    },
    retry: false,
    // The gate is a per-user check: asking before auth resolves always 401s.
    enabled: isTelegramWebApp() && isAuthenticated,
  });

  const blockReason = gateBlockReason(gate.data);

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

  if (gate.data && blockReason) {
    return (
      <>
        <EntryLockScreen reason={blockReason} gate={gate.data} />
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
            {/* The admin panel owns the whole viewport: no app header, no BottomNav. */}
            <Route path="/admin/*" element={<ErrorBoundary><Admin /></ErrorBoundary>} />
            <Route path="/referral" element={<Layout><ErrorBoundary><Referral /></ErrorBoundary></Layout>} />
            <Route path="*" element={<Navigate to="/app" replace />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
      <ToastHost />
    </>
  );
}
