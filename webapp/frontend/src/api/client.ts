import axios from "axios";

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
    const skipAutoLogout = requestUrl.includes("/auth/telegram") || requestUrl.includes("/auth/handoff");

    if (status === 401 && !skipAutoLogout) {
      localStorage.removeItem("session_token");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default client;
