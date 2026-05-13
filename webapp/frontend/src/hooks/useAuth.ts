import { useQuery } from "@tanstack/react-query";

import client from "../api/client";
import { useAuthStore } from "../store/auth";
import type { UserProfile } from "../types";

export function useAuth() {
  const store = useAuthStore();

  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const { data } = await client.get<UserProfile>("/auth/me");
      return data;
    },
    enabled: Boolean(localStorage.getItem("session_token"))
  });

  return {
    ...store,
    me
  };
}
