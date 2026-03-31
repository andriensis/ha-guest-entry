const BASE = "./admin/api";

export interface AppConfig {
  instance_name: string;
  session_duration_hours: number;
  max_login_attempts: number;
  lockout_duration_minutes: number;
}

export interface AllowedEntity {
  entity_id: string;
  label: string | null;
}

export interface User {
  id: string;
  username: string;
  display_name: string;
  enabled: boolean;
  allowed_entities: AllowedEntity[];
}

export interface HAEntity {
  entity_id: string;
  name: string;
  domain: string;
  state: string;
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText);
    throw new Error(text || `HTTP ${resp.status}`);
  }
  return resp.json();
}

export const api = {
  getConfig: () => req<AppConfig>("GET", "/config"),
  saveConfig: (cfg: AppConfig) => req<{ ok: boolean }>("PUT", "/config", cfg),
  getUsers: () => req<{ users: User[] }>("GET", "/users"),
  createUser: (u: Omit<User, "id"> & { password: string }) => req<User>("POST", "/users", u),
  updateUser: (id: string, u: Partial<User> & { password?: string }) => req<User>("PUT", `/users/${id}`, u),
  deleteUser: (id: string) => req<{ ok: boolean }>("DELETE", `/users/${id}`),
  getEntities: () => req<{ entities: HAEntity[] }>("GET", "/entities"),
};
