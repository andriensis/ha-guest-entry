import { useState, useEffect, useCallback } from "preact/hooks";
import { getEntities, logout, type Entity, type LoginResponse } from "../lib/api";
import { GuestWsClient } from "../lib/ws";
import { EntityCard } from "../components/EntityCard";
import { t } from "../lib/i18n";

interface Props {
  token: string;
  user: LoginResponse["user"];
  instanceName: string;
  onLogout: () => void;
}

export function Dashboard({ token, user, instanceName, onLogout }: Props) {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.title = instanceName;
  }, [instanceName]);

  const updateEntityState = useCallback(
    (entityId: string, newState: string, attributes: Record<string, unknown>) => {
      setEntities((prev) =>
        prev.map((e) =>
          e.entity_id === entityId
            ? { ...e, state: newState, attributes: { ...e.attributes, ...attributes } }
            : e
        )
      );
    },
    []
  );

  useEffect(() => {
    getEntities(token)
      .then((data) => setEntities(data.entities))
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    const ws = new GuestWsClient(
      token,
      (msg) => updateEntityState(msg.entity_id, msg.state, msg.attributes),
      () => {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        onLogout();
      }
    );
    return () => ws.stop();
  }, [token, updateEntityState, onLogout]);

  async function handleLogout() {
    await logout(token).catch(() => {});
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    onLogout();
  }

  return (
    <div class="dashboard">
      <header class="topbar">
        <span class="topbar-title">{instanceName}</span>
        <div class="topbar-user">
          <span class="topbar-name">{user.display_name}</span>
          <button class="logout-btn" onClick={handleLogout} title={t.signOut}>
            <SignOutIcon />
            <span>{t.signOut}</span>
          </button>
        </div>
      </header>

      <main class="dashboard-body">
        {loading && <p class="status-msg">{t.loading}</p>}
        {error && <p class="status-msg" style={{ color: "var(--danger)" }}>{error}</p>}
        {!loading && !error && entities.length === 0 && (
          <p class="status-msg">{t.noDevices}</p>
        )}
        <div class="grid">
          {entities.map((entity) => (
            <EntityCard key={entity.entity_id} entity={entity} token={token} />
          ))}
        </div>
      </main>
    </div>
  );
}

function SignOutIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}
