import { useQuery } from "@tanstack/react-query";
import { Grid2x2, Home, UserCircle2 } from "lucide-react";
import { ShieldCheck } from "lucide-react";
import { NavLink } from "react-router-dom";

import client from "../../api/client";
import { useKeyboardOpen } from "../../hooks/useKeyboardOpen";

const links = [
  { to: "/app", label: "Bosh sahifa", icon: Home },
  { to: "/profile", label: "Profil", icon: UserCircle2 },
  { to: "/hub", label: "Markaz", icon: Grid2x2 },
];

export default function BottomNav({ fixed = true }: { fixed?: boolean }) {
  const keyboardOpen = useKeyboardOpen();

  const adminState = useQuery({
    queryKey: ["admin", "state", "nav"],
    queryFn: async () => {
      const { data } = await client.get<{ is_admin: boolean }>("/admin/state");
      return data;
    },
    retry: false,
    staleTime: 60_000,
  });

  // Hide on keyboard open in BOTH modes:
  //  • fixed=true  → prevents nav from floating above the keyboard
  //  • fixed=false → frees up space so the action bar stays reachable
  if (keyboardOpen) return null;

  const navLinks = adminState.data?.is_admin
    ? [...links, { to: "/admin", label: "Admin", icon: ShieldCheck }]
    : links;

  const navCls = fixed
    ? "fixed bottom-0 left-0 right-0 z-20 border-t border-slate-200 bg-white/95 backdrop-blur"
    : "border-t border-slate-200 bg-white/95 backdrop-blur shrink-0";

  return (
    <nav className={navCls} style={{ paddingBottom: "var(--bottom-safe, 0px)" }}>
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
