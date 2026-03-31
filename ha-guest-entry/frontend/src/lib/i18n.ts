const translations = {
  en: {
    connecting: "Connecting…",
    connectionError: "Connection error",
    accessDisabled: "Guest access is currently disabled",
    accessDisabledSub: "Please check back later",
    signInTo: "Sign in to continue",
    username: "Username",
    usernamePlaceholder: "your username",
    password: "Password",
    passwordPlaceholder: "••••••••",
    signIn: "Sign in",
    signingIn: "Signing in…",
    serverUnreachable: "Could not reach the server",
    signOut: "Sign out",
    loading: "Loading...",
    noDevices: "No devices assigned to your account.",
    on: "On",
    off: "Off",
    open: "Open",
    close: "Close",
    unlock: "Unlock",
    lock: "Lock",
    confirm: "Confirm",
    locked: "Locked",
    unlocked: "Unlocked",
    targetTemp: (t: number) => `Target ${t}°`,
    currentTemp: "Current temperature",
  },
  it: {
    connecting: "Connessione in corso…",
    connectionError: "Errore di connessione",
    accessDisabled: "L'accesso è attualmente disabilitato",
    accessDisabledSub: "Riprova più tardi",
    signInTo: "Accedi per continuare",
    username: "Nome utente",
    usernamePlaceholder: "il tuo nome utente",
    password: "Password",
    passwordPlaceholder: "••••••••",
    signIn: "Accedi",
    signingIn: "Accesso in corso...",
    serverUnreachable: "Impossibile raggiungere il server",
    signOut: "Esci",
    loading: "Caricamento…",
    noDevices: "Nessun dispositivo assegnato al tuo account.",
    on: "Acceso",
    off: "Spento",
    open: "Apri",
    close: "Chiudi",
    unlock: "Sblocca",
    lock: "Blocca",
    confirm: "Conferma",
    locked: "Bloccato",
    unlocked: "Sbloccato",
    targetTemp: (t: number) => `Impostata ${t}°`,
    currentTemp: "Temperatura attuale",
  },
} as const;

type Lang = keyof typeof translations;

function detectLang(): Lang {
  const param = new URLSearchParams(window.location.search).get("lang");
  if (param && param in translations) return param as Lang;
  const preferred = navigator.language.split("-")[0].toLowerCase();
  return preferred in translations ? (preferred as Lang) : "en";
}

export const t = translations[detectLang()];
