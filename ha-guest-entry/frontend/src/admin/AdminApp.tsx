import { useState } from "preact/hooks";
import { UsersPage } from "./pages/Users";
import { SettingsPage } from "./pages/Settings";
import "./style.css";

type Tab = "users" | "settings";

export function AdminApp() {
  const [tab, setTab] = useState<Tab>("users");

  return (
    <div class="admin-shell">
      <header class="admin-header">
        <div class="admin-header-inner">
          <div class="admin-logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" width="22" height="22">
              <path d="M3 12L12 3l9 9" />
              <path d="M9 21V12h6v9" />
            </svg>
            <span>Guest Entry</span>
            <span class="admin-badge">Admin</span>
          </div>
          <nav class="admin-nav">
            <button class={`admin-nav-btn ${tab === "users" ? "active" : ""}`} onClick={() => setTab("users")}>
              Users
            </button>
            <button class={`admin-nav-btn ${tab === "settings" ? "active" : ""}`} onClick={() => setTab("settings")}>
              Settings
            </button>
          </nav>
        </div>
      </header>
      <main class="admin-main">
        {tab === "users" ? <UsersPage /> : <SettingsPage />}
      </main>
    </div>
  );
}
