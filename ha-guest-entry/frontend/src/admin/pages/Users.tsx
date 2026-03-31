import { useState, useEffect } from "preact/hooks";
import { api, type User, type HAEntity } from "../lib/api";

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [entities, setEntities] = useState<HAEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [editUser, setEditUser] = useState<User | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<User | null>(null);
  const [toast, setToast] = useState<{ msg: string; error?: boolean } | null>(null);

  function showToast(msg: string, error = false) {
    setToast({ msg, error });
    setTimeout(() => setToast(null), 2500);
  }

  async function load() {
    setLoading(true);
    try {
      const [uRes, eRes] = await Promise.all([api.getUsers(), api.getEntities()]);
      setUsers(uRes.users);
      setEntities(eRes.entities);
    } catch (err) {
      showToast((err as Error).message, true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleSaveUser(data: Partial<User> & { password?: string }, userId?: string) {
    try {
      if (userId) {
        const updated = await api.updateUser(userId, data);
        setUsers(users.map((u) => (u.id === userId ? updated : u)));
        showToast("User updated");
      } else {
        const created = await api.createUser(data as Parameters<typeof api.createUser>[0]);
        setUsers([...users, created]);
        showToast("User created");
      }
    } catch (err) {
      showToast((err as Error).message, true);
      throw err;
    }
  }

  async function handleToggleEnabled(user: User) {
    try {
      const updated = await api.updateUser(user.id, { enabled: !user.enabled });
      setUsers(users.map((u) => (u.id === user.id ? updated : u)));
    } catch (err) {
      showToast((err as Error).message, true);
    }
  }

  async function handleDelete(user: User) {
    try {
      await api.deleteUser(user.id);
      setUsers(users.filter((u) => u.id !== user.id));
      setConfirmDelete(null);
      showToast("User deleted");
    } catch (err) {
      showToast((err as Error).message, true);
    }
  }

  return (
    <div>
      {toast && <div class={`toast${toast.error ? " error" : ""}`}>{toast.msg}</div>}

      <div class="admin-section-header">
        <h2 class="admin-section-title">Users</h2>
        <button class="btn btn-primary btn-sm" onClick={() => setShowCreate(true)}>
          + Add User
        </button>
      </div>

      {loading ? (
        <div class="loading-wrap"><div class="spinner" /></div>
      ) : users.length === 0 ? (
        <div class="admin-card" style={{ textAlign: "center", color: "var(--text-muted)", padding: "2.5rem" }}>
          No users yet. Add one to get started.
        </div>
      ) : (
        <div class="user-list">
          {users.map((user) => (
            <div class={`user-row${!user.enabled ? " user-disabled" : ""}`} key={user.id}>
              <div class="user-avatar">{(user.display_name || user.username)[0]}</div>
              <div class="user-info">
                <div class="user-name">{user.display_name || user.username}</div>
                <div class="user-meta">
                  @{user.username} · {user.allowed_entities.length} {user.allowed_entities.length === 1 ? "entity" : "entities"}
                  {!user.enabled && " · Disabled"}
                </div>
              </div>
              <div class="user-actions">
                <label class="toggle" title={user.enabled ? "Disable user" : "Enable user"}>
                  <input type="checkbox" checked={user.enabled} onChange={() => handleToggleEnabled(user)} />
                  <span class="toggle-slider" />
                </label>
                <button class="btn btn-ghost btn-sm" onClick={() => setEditUser(user)}>Edit</button>
                <button class="btn btn-danger btn-sm" onClick={() => setConfirmDelete(user)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {(showCreate || editUser) && (
        <UserModal
          user={editUser ?? undefined}
          entities={entities}
          onSave={async (data) => {
            await handleSaveUser(data, editUser?.id);
            setEditUser(null);
            setShowCreate(false);
          }}
          onClose={() => { setEditUser(null); setShowCreate(false); }}
        />
      )}

      {confirmDelete && (
        <ConfirmModal
          message={`Delete user "${confirmDelete.username}"? This cannot be undone.`}
          onConfirm={() => handleDelete(confirmDelete)}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}

interface UserModalProps {
  user?: User;
  entities: HAEntity[];
  onSave: (data: Partial<User> & { password?: string }) => Promise<void>;
  onClose: () => void;
}

function UserModal({ user, entities, onSave, onClose }: UserModalProps) {
  const [username, setUsername] = useState(user?.username ?? "");
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [password, setPassword] = useState("");
  const [enabled, setEnabled] = useState(user?.enabled ?? true);
  const [selectedEntities, setSelectedEntities] = useState<string[]>(
    user?.allowed_entities.map(e => e.entity_id) ?? []
  );
  const [entityLabels, setEntityLabels] = useState<Record<string, string>>(
    Object.fromEntries((user?.allowed_entities ?? []).filter(e => e.label).map(e => [e.entity_id, e.label!]))
  );
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [entitySearch, setEntitySearch] = useState("");

  const isEdit = !!user;

  const filteredEntities = entities.filter((e) => {
    const q = entitySearch.toLowerCase();
    return e.entity_id.includes(q) || e.name.toLowerCase().includes(q) || e.domain.includes(q);
  });

  function toggleEntity(entityId: string) {
    setSelectedEntities((prev) => {
      if (prev.includes(entityId)) return prev.filter((e) => e !== entityId);
      return [...prev, entityId];
    });
  }

  function setLabel(entityId: string, label: string) {
    setEntityLabels((prev) => ({ ...prev, [entityId]: label }));
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const data: Partial<User> & { password?: string } = {
        display_name: displayName.trim() || username.trim(),
        enabled,
        allowed_entities: selectedEntities.map(id => ({ entity_id: id, label: entityLabels[id] || null })),
      };
      if (!isEdit) data.username = username.trim().toLowerCase();
      if (password) data.password = password;
      else if (!isEdit) { setError("Password is required"); setSaving(false); return; }
      await onSave(data);
    } catch (err) {
      setError((err as Error).message || "Failed to save user");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div class="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">{isEdit ? `Edit "${user.username}"` : "Add User"}</h2>
          <button class="modal-close" onClick={onClose} aria-label="Close">&#x2715;</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div class="modal-body">
            {/* Basic fields */}
            <div class="form-grid form-grid-2">
              <div class="form-field">
                <label class="form-label">Username</label>
                <input
                  class="form-input"
                  type="text"
                  value={username}
                  disabled={isEdit}
                  onInput={(e) => setUsername((e.target as HTMLInputElement).value)}
                  placeholder="guest"
                  required={!isEdit}
                  autocomplete="off"
                />
              </div>
              <div class="form-field">
                <label class="form-label">Display Name</label>
                <input
                  class="form-input"
                  type="text"
                  value={displayName}
                  onInput={(e) => setDisplayName((e.target as HTMLInputElement).value)}
                  placeholder={username || "Guest"}
                />
              </div>
              <div class="form-field" style={{ gridColumn: "1 / -1" }}>
                <label class="form-label">{isEdit ? "New Password (leave blank to keep)" : "Password"}</label>
                <div style={{ position: "relative" }}>
                  <input
                    class="form-input"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onInput={(e) => setPassword((e.target as HTMLInputElement).value)}
                    placeholder={isEdit ? "••••••••" : ""}
                    required={!isEdit}
                    autocomplete="new-password"
                    style={{ paddingRight: "2.75rem" }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    style={{
                      position: "absolute", right: "0.75rem", top: "50%", transform: "translateY(-50%)",
                      background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)",
                      fontSize: "0.875rem", padding: "0.25rem",
                    }}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? "🙈" : "👁"}
                  </button>
                </div>
              </div>
            </div>

            <div class="toggle-wrap">
              <label class="toggle">
                <input type="checkbox" checked={enabled} onChange={(e) => setEnabled((e.target as HTMLInputElement).checked)} />
                <span class="toggle-slider" />
              </label>
              <span>Account enabled</span>
            </div>

            {/* Entity picker */}
            <div>
              <div class="entity-picker-header">
                <span class="entity-picker-label">Allowed Entities</span>
                <span class="selected-count">
                  {selectedEntities.length} selected
                </span>
              </div>
              <input
                class="entity-search"
                type="search"
                placeholder="Search entities…"
                value={entitySearch}
                onInput={(e) => setEntitySearch((e.target as HTMLInputElement).value)}
              />
              <div class="entity-list-scroll">
                {filteredEntities.length === 0 ? (
                  <div class="no-entities">
                    {entities.length === 0 ? "No supported entities found in HA" : "No matches"}
                  </div>
                ) : (
                  filteredEntities.map((entity) => {
                    const checked = selectedEntities.includes(entity.entity_id);
                    return (
                      <div
                        class={`entity-item${checked ? " selected" : ""}`}
                        key={entity.entity_id}
                        onClick={() => toggleEntity(entity.entity_id)}
                      >
                        <input type="checkbox" checked={checked} onChange={() => toggleEntity(entity.entity_id)} onClick={(e) => e.stopPropagation()} />
                        <div class="entity-item-info">
                          <div class="entity-item-name">{entity.name}</div>
                          <div class="entity-item-id">{entity.entity_id}</div>
                        </div>
                        <span class="entity-domain-badge">{entity.domain}</span>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {selectedEntities.length > 0 && (
              <div style={{ marginTop: "0.75rem" }}>
                <div class="entity-picker-label" style={{ marginBottom: "0.5rem" }}>Display Labels <span style={{ fontWeight: 400, color: "var(--text-muted)", fontSize: "0.8125rem" }}>(optional)</span></div>
                {selectedEntities.map(id => {
                  const entity = entities.find(e => e.entity_id === id);
                  return (
                    <div key={id} style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.375rem" }}>
                      <span style={{ flex: "0 0 auto", fontSize: "0.8125rem", color: "var(--text-secondary)", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "45%" }}>{entity?.name ?? id}</span>
                      <input
                        class="form-input"
                        type="text"
                        style={{ flex: 1, padding: "0.3rem 0.6rem", fontSize: "0.8125rem" }}
                        placeholder="Label shown to guest…"
                        value={entityLabels[id] ?? ""}
                        onInput={(e) => setLabel(id, (e.target as HTMLInputElement).value)}
                      />
                    </div>
                  );
                })}
              </div>
            )}

            {error && <p style={{ color: "var(--danger)", fontSize: "0.875rem" }}>{error}</p>}
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" class="btn btn-primary" disabled={saving}>
              {saving ? "Saving…" : isEdit ? "Save Changes" : "Create User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ConfirmModal({ message, onConfirm, onCancel }: { message: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div class="modal-overlay" onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <div class="modal" style={{ maxWidth: "400px" }}>
        <div class="modal-header">
          <h2 class="modal-title">Confirm Delete</h2>
          <button class="modal-close" onClick={onCancel}>&#x2715;</button>
        </div>
        <div class="modal-body">
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9375rem" }}>{message}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button class="btn btn-danger" onClick={onConfirm}>Delete</button>
        </div>
      </div>
    </div>
  );
}
