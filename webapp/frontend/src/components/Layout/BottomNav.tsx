import { Heart, Home, UserCircle2 } from "lucide-react";
import { NavLink } from "react-router-dom";

const links = [
  { to: "/app", label: "Bosh sahifa", icon: Home },
  { to: "/saves", label: "Saqlangan", icon: Heart },
  { to: "/profile", label: "Profil", icon: UserCircle2 }
];

export default function BottomNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-20 border-t border-slate-200 bg-white/95 pb-[var(--tg-content-safe-area-bottom)] backdrop-blur">
      <ul className="mx-auto grid max-w-2xl grid-cols-3 px-[var(--tg-content-safe-area-left)] pr-[var(--tg-content-safe-area-right)]">
        {links.map((item) => (
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
