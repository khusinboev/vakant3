import { useState, useEffect } from "react";
import { Grid2x2, Home, UserCircle2 } from "lucide-react";
import { ShieldCheck } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";

import client from "../../api/client";

const links = [
  { to: "/app", label: "Bosh sahifa", icon: Home },
  { to: "/profile", label: "Profil", icon: UserCircle2 },
  { to: "/hub", label: "Markaz", icon: Grid2x2 },
];

export default function BottomNav({ fixed = true }: { fixed?: boolean }) {
  const [keyboardOpen, setKeyboardOpen] = useState(false);

  useEffect(() => {
    const onFocusIn = (e: FocusEvent) => {
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea") setKeyboardOpen(true);
    };
    const onFocusOut = () => setTimeout(() => setKeyboardOpen(false), 150);
    document.addEventListener("focusin", onFocusIn);
    document.addEventListener("focusout", onFocusOut);
    return () => {
      document.removeEventListener("focusin", onFocusIn);
      document.removeEventListener("focusout", onFocusOut);
    };
  }, []);

  const adminState = useQuery({
    queryKey: ["admin", "state", "nav"],
    queryFn: async () => {
      const { data } = await client.get<{ is_admin: boolean }>("/admin/state");
      return data;
    },
    retry: false,
    staleTime: 60_000,
  });

  const navLinks = adminState.data?.is_admin
    ? [...links, { to: "/admin", label: "Admin", icon: ShieldCheck }]
    : links;

  if (keyboardOpen) return null;

  const navCls = fixed
    ? "fixed bottom-0 left-0 right-0 z-20 border-t border-slate-200 bg-white/95 pb-[var(--tg-content-safe-area-bottom)] backdrop-blur"
    : "border-t border-slate-200 bg-white/95 pb-[var(--tg-content-safe-area-bottom)] backdrop-blur shrink-0";

  return (
    <nav className={navCls}>
      <ul
        className="mx-auto grid max-w-2xl px-[var(--tg-content-safe-area-left)] pr-[var(--tg-content-safe-area-right)]"
        style={{ gridTemplateColumns: `repeat(${navLinks.length}, minmax(0, 1fr))` }}
      >
        {navLinks.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                `tap-target flex flex-col items-center justify-center gap-1 py-2 text-xs ${isActive ? "text-brand-500" : "text-slate-500"}`
              }
            >
              <item.icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
