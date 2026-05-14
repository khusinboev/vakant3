import { Route, Routes, Navigate } from "react-router-dom";

import Layout from "./components/Layout/Navbar";
import useTelegramWebApp from "./hooks/useTelegramWebApp";
import useTelegramAuth, { isTelegramWebApp } from "./hooks/useTelegramAuth";
import Home from "./pages/Home";
import Landing from "./pages/Landing";
import Profile from "./pages/Profile";
import Referral from "./pages/Referral";
import Saves from "./pages/Saves";

export default function App() {
  useTelegramWebApp();
  useTelegramAuth();

  // External browser — always show landing page
  if (!isTelegramWebApp()) {
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

