import { useState } from "preact/hooks";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import type { LoginResponse } from "./lib/api";

type User = LoginResponse["user"];

export function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem("user");
    return stored ? (JSON.parse(stored) as User) : null;
  });
  const [instanceName, setInstanceName] = useState<string>(
    localStorage.getItem("instanceName") ?? "Home"
  );

  function handleLogin(newToken: string, newUser: User, name: string) {
    setToken(newToken);
    setUser(newUser);
    setInstanceName(name);
    localStorage.setItem("instanceName", name);
  }

  function handleLogout() {
    setToken(null);
    setUser(null);
  }

  if (token && user) {
    return <Dashboard token={token} user={user} instanceName={instanceName} onLogout={handleLogout} />;
  }
  return <Login onLogin={handleLogin} />;
}
