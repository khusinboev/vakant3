import type { PropsWithChildren } from "react";
import { Link } from "react-router-dom";

import BottomNav from "./BottomNav";

export default function Layout({ children }: PropsWithChildren) {
  return (
    <div className="min-h-[var(--app-viewport-height)] pb-[calc(5rem+var(--tg-content-safe-area-bottom))] md:pb-8">
      {/* sticky top-0 so header covers the notch/status-bar area in fullscreen.
          pt-[var(--tg-content-safe-area-top)] pushes content below the notch
          while the bg fills the transparent status bar region. */}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-center
          pt-[calc(0.75rem+var(--tg-content-safe-area-top))] pb-3
          pl-[calc(1rem+var(--tg-content-safe-area-left))]
          pr-[calc(1rem+var(--tg-content-safe-area-right))]">
          <Link to="/app" className="font-display text-xl font-extrabold text-brand-700">
            Bandlik.uz
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-[calc(1rem+var(--tg-content-safe-area-left))] py-4 pr-[calc(1rem+var(--tg-content-safe-area-right))]">{children}</main>
      <BottomNav />
    </div>
  );
}
