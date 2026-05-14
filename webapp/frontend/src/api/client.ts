import axios from "axios";
import { useAuthStore } from "../store/auth";

const client = axios.create({
  baseURL: "/api"
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("session_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const requestUrl = String(error?.config?.url || "");
    const isAuthEndpoint =
      requestUrl.includes("/auth/telegram") ||
      requestUrl.includes("/auth/handoff") ||
      requestUrl.includes("/auth/tg-webapp");

    if (status === 401 && !isAuthEndpoint) {
      // Only trigger re-auth once. If isInitializing is already true, a re-auth
      // cycle is already running — don't call clearSession() again or every
      // parallel 401 would increment sessionVersion N times, causing N auth
      // requests and hitting the rate limit (429).
      const state = useAuthStore.getState();
      if (!state.isInitializing) {
        state.clearSession();
      }
    }
    return Promise.reject(error);
  }
);

export default client;
