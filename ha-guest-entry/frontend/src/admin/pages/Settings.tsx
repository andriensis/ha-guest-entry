import { useState, useEffect } from "preact/hooks";
import { api, type AppConfig } from "../lib/api";

export function SettingsPage() {
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; error?: boolean } | null>(null);

  useEffect(() => {
    api.getConfig().then(setCfg).catch(() => showToast("Failed to load config", true));
  }, []);

  function showToast(msg: string, error = false) {
    setToast({ msg, error });
    setTimeout(() => setToast(null), 2500);
  }

  async function handleSave(e: Event) {
    e.preventDefault();
    if (!cfg) return;
    setSaving(true);
    try {
      await api.saveConfig(cfg);
      showToast("Settings saved");
    } catch (err) {
      showToast((err as Error).message, true);
    } finally {
      setSaving(false);
    }
  }

  if (!cfg) return <div class="loading-wrap"><div class="spinner" /></div>;

  return (
    <div>
      {toast && <div class={`toast${toast.error ? " error" : ""}`}>{toast.msg}</div>}

      <div class="admin-section-header">
        <h2 class="admin-section-title">Settings</h2>
      </div>

      <form onSubmit={handleSave}>
        <div class="admin-card">
          <div class="form-grid form-grid-2" style={{ gap: "1rem" }}>
            <div class="form-field" style={{ gridColumn: "1 / -1" }}>
              <label class="form-label">Instance Name</label>
              <input
                class="form-input"
                type="text"
                value={cfg.instance_name}
                onInput={(e) => setCfg({ ...cfg, instance_name: (e.target as HTMLInputElement).value })}
                required
              />
              <span class="form-hint">Shown on the guest login page</span>
            </div>

            <div class="form-field">
              <label class="form-label">Session Duration (hours)</label>
              <input
                class="form-input"
                type="number"
                min={1}
                max={720}
                value={cfg.session_duration_hours}
                onInput={(e) => setCfg({ ...cfg, session_duration_hours: parseInt((e.target as HTMLInputElement).value) || 24 })}
              />
            </div>

            <div class="form-field">
              <label class="form-label">Max Login Attempts</label>
              <input
                class="form-input"
                type="number"
                min={1}
                max={20}
                value={cfg.max_login_attempts}
                onInput={(e) => setCfg({ ...cfg, max_login_attempts: parseInt((e.target as HTMLInputElement).value) || 5 })}
              />
            </div>

            <div class="form-field">
              <label class="form-label">Lockout Duration (minutes)</label>
              <input
                class="form-input"
                type="number"
                min={1}
                max={1440}
                value={cfg.lockout_duration_minutes}
                onInput={(e) => setCfg({ ...cfg, lockout_duration_minutes: parseInt((e.target as HTMLInputElement).value) || 15 })}
              />
              <span class="form-hint">How long to lock an IP after too many failed attempts</span>
            </div>
          </div>

          <div style={{ marginTop: "1.25rem", display: "flex", justifyContent: "flex-end" }}>
            <button type="submit" class="btn btn-primary" disabled={saving}>
              {saving ? "Saving…" : "Save Settings"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
