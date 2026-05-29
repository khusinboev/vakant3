import axios from "axios";

const client = axios.create({
  baseURL: "/api"
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("session_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // Saves endpoints can identify user by Telegram initData even without webapp session auth.
  const initData = window.Telegram?.WebApp?.initData;
  if (initData) {
    config.headers["X-Telegram-Init-Data"] = initData;
  }

  const tgUserId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  if (tgUserId) {
    config.headers["X-Telegram-User-Id"] = String(tgUserId);
  }

  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  }
);

export default client;
