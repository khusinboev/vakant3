import { LogOut } from "lucide-react";
import type { PropsWithChildren } from "react";
import { Link, useNavigate } from "react-router-dom";

import client from "../../api/client";
import { useAuthStore } from "../../store/auth";
import BottomNav from "./BottomNav";

export default function Layout({ children }: PropsWithChildren) {
  const navigate = useNavigate();
  const clearSession = useAuthStore((state) => state.clearSession);

  const logout = async () => {
    try {
      await client.post("/auth/logout");
    } catch {
      // ignore
    }
    clearSession();
    navigate("/login");
  };

  return (
    <div className="min-h-[var(--app-viewport-height)] pb-[calc(5rem+var(--tg-content-safe-area-bottom))] md:pb-8">
      <header className="sticky top-[var(--tg-content-safe-area-top)] z-20 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-[calc(1rem+var(--tg-content-safe-area-left))] py-3 pr-[calc(1rem+var(--tg-content-safe-area-right))]">
          <Link to="/" className="font-display text-xl font-extrabold text-brand-700">
            IshBot
          </Link>
          <button onClick={logout} className="tap-target inline-flex items-center gap-2 rounded-xl px-3 text-sm text-slate-600 hover:bg-slate-100">
            <LogOut size={16} /> Chiqish
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-[calc(1rem+var(--tg-content-safe-area-left))] py-4 pr-[calc(1rem+var(--tg-content-safe-area-right))]">{children}</main>
      <BottomNav />
    </div>
  );
}
