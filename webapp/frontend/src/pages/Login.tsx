import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LoginButton } from "@telegram-auth/react";
import type { TelegramAuthData } from "@telegram-auth/react";

import client from "../api/client";
import { useAuthStore } from "../store/auth";
import type { UserProfile } from "../types";

type AuthResponse = {
  session_token: string;
  user: UserProfile;
};

function isPrivateOrLocalHost(hostname: string) {
  if (hostname === "localhost" || hostname === "127.0.0.1") return true;
  if (/^10\./.test(hostname)) return true;
  if (/^192\.168\./.test(hostname)) return true;
  if (/^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(hostname)) return true;
  return /^\d+\.\d+\.\d+\.\d+$/.test(hostname);
}

export default function Login() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setSession = useAuthStore((state) => state.setSession);
  const botUsername = "alingniurmabot";
  const host = window.location.hostname;
  const showTelegramWidget = !isPrivateOrLocalHost(host);

  const handleAuth = (tgData: TelegramAuthData) => {
    void (async () => {
      setLoading(true);
      try {
        const { data } = await client.post<AuthResponse>("/auth/telegram", tgData);
        setSession(data.session_token, data.user);
        navigate("/");
      } finally {
        setLoading(false);
      }
    })();
  };

  return (
    <div className="flex min-h-[var(--app-viewport-height)] items-center justify-center px-[calc(1rem+var(--tg-content-safe-area-left))] pb-[calc(1rem+var(--tg-content-safe-area-bottom))] pt-[calc(1rem+var(--tg-content-safe-area-top))] pr-[calc(1rem+var(--tg-content-safe-area-right))]">
      <div className="card w-full max-w-md p-6 text-center">
        <p className="font-display text-3xl font-extrabold text-brand-700">IshBot</p>
        <p className="mt-2 text-sm text-slate-600">Telegram orqali tizimga kiring</p>
        <div className="mt-6 flex justify-center">
          {showTelegramWidget ? (
            <LoginButton botUsername={botUsername} onAuthCallback={handleAuth} />
          ) : (
            <p className="text-sm text-slate-600">
              Local/IP rejimda Telegram Login widget ishlamaydi. Botga qayting va /start orqali yuborilgan yangi havoladan kiring.
            </p>
          )}
        </div>
        {loading && <p className="mt-3 text-sm">Kutilmoqda...</p>}
      </div>
    </div>
  );
}
