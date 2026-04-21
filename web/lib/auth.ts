"use client";

import { useRouter } from "next/navigation";
import { api } from "./api";

export async function login(email: string, password: string): Promise<void> {
  await api.auth.login(email, password);
}

export async function logout(router: ReturnType<typeof useRouter>): Promise<void> {
  await api.auth.logout();
  router.push("/login");
}

export async function requireAuth(): Promise<{ id: string; email: string }> {
  return api.auth.me();
}
