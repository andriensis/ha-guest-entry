import { useState, useEffect } from "preact/hooks";
import { discover, login, type DiscoverResponse, type LoginResponse } from "../lib/api";
import { t } from "../lib/i18n";

interface Props {
  onLogin: (token: string, user: LoginResponse["user"], instanceName: string) => void;
}

export function Login({ onLogin }: Props) {
  const [info, setInfo] = useState<DiscoverResponse | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    discover()
      .then((data) => {
        setInfo(data);
        document.title = data.instance_name;
      })
      .catch(() => setError(t.serverUnreachable));
  }, []);

  async function handleSubmit(e: Event) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const resp = await login(username.trim(), password);
      localStorage.setItem("token", resp.token);
      localStorage.setItem("user", JSON.stringify(resp.user));
      onLogin(resp.token, resp.user, info?.instance_name ?? "Home");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const instanceName = info?.instance_name ?? "Home";

  if (!info && !error) {
    return (
      <div class="login-wrap">
        <div class="login-card">
          <div class="login-header">
            <HouseIcon />
            <p class="login-subtitle" style={{ marginTop: "1rem" }}>{t.connecting}</p>
          </div>
        </div>
      </div>
    );
  }

  if (error && !info) {
    return (
      <div class="login-wrap">
        <div class="login-card">
          <div class="login-header">
            <HouseIcon />
            <p class="login-title" style={{ marginTop: "0.75rem" }}>{t.connectionError}</p>
          </div>
          <p class="error-msg">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div class="login-wrap">
      <div class="login-card">
        <div class="login-header">
          <HouseIcon />
          <h1 class="login-title" style={{ marginTop: "0.75rem" }}>{instanceName}</h1>
          <p class="login-subtitle">{t.signInTo}</p>
        </div>
        <form class="login-form" onSubmit={handleSubmit}>
          <div class="field">
            <label for="username">{t.username}</label>
            <input
              id="username"
              type="text"
              autocomplete="username"
              value={username}
              onInput={(e) => setUsername((e.target as HTMLInputElement).value)}
              placeholder={t.usernamePlaceholder}
              required
            />
          </div>
          <div class="field">
            <label for="password">{t.password}</label>
            <input
              id="password"
              type="password"
              autocomplete="current-password"
              value={password}
              onInput={(e) => setPassword((e.target as HTMLInputElement).value)}
              placeholder={t.passwordPlaceholder}
              required
            />
          </div>
          {error && <p class="error-msg">{error}</p>}
          <button type="submit" class="btn-primary" disabled={loading}>
            {loading ? t.signingIn : t.signIn}
          </button>
        </form>
      </div>
    </div>
  );
}

function HouseIcon() {
  return (
    <div class="login-icon">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 12L12 3l9 9" />
        <path d="M9 21V12h6v9" />
        <path d="M3 12v9h18v-9" />
      </svg>
    </div>
  );
}
