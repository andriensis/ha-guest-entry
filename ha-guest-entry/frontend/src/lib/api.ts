/** Typed REST API client. */

export interface DiscoverResponse {
  server: string;
  version: string;
  instance_name: string;
  capabilities: string[];
  auth_required: boolean;
}

export interface LoginResponse {
  token: string;
  expires_at: string;
  user: { id: string; username: string; display_name: string };
}

export interface EntityAttribute {
  brightness?: number;
  color_temp_kelvin?: number;
  hvac_mode?: string;
  hvac_modes?: string[];
  temperature?: number;
  current_temperature?: number;
  current_position?: number;
  supported_features: string[];
  [key: string]: unknown;
}

export interface Entity {
  entity_id: string;
  name: string;
  label: string | null;
  domain: string;
  state: string;
  attributes: EntityAttribute;
  last_changed: string | null;
}

export interface EntitiesResponse {
  entities: Entity[];
}

export interface ActionResponse {
  ok: boolean;
  state: string;
}

const BASE = "/api/v1";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function discover(): Promise<DiscoverResponse> {
  const resp = await fetch(`${BASE}/discover`);
  if (!resp.ok) throw new Error(`Discover failed: ${resp.status}`);
  return resp.json();
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const resp = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (resp.status === 401) throw new Error("Invalid credentials");
  if (resp.status === 403) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { error?: string }).error ?? "Access denied");
  }
  if (resp.status === 423) {
    const data = await resp.json();
    throw new Error(`Too many attempts. Try again in ${data.retry_after}s`);
  }
  if (resp.status === 503) throw new Error("Guest access is currently disabled");
  if (!resp.ok) throw new Error(`Login failed: ${resp.status}`);
  return resp.json();
}

export async function logout(token: string): Promise<void> {
  await fetch(`${BASE}/auth/logout`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function getEntities(token: string): Promise<EntitiesResponse> {
  const resp = await fetch(`${BASE}/entities`, { headers: authHeaders(token) });
  if (resp.status === 401) throw new Error("Unauthorized");
  if (!resp.ok) throw new Error(`Failed to fetch entities: ${resp.status}`);
  return resp.json();
}

export async function callAction(
  token: string,
  entityId: string,
  action: string,
  params: Record<string, unknown> = {}
): Promise<ActionResponse> {
  const resp = await fetch(`${BASE}/entities/${entityId}/action`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ action, params }),
  });
  if (resp.status === 403) throw new Error("Action not permitted");
  if (resp.status === 422) throw new Error("Invalid action for this entity");
  if (!resp.ok) throw new Error(`Action failed: ${resp.status}`);
  return resp.json();
}
