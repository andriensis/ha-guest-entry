import { useState } from "preact/hooks";
import { type Entity, callAction } from "../lib/api";
import { t } from "../lib/i18n";

interface Props {
  entity: Entity;
  token: string;
  displayName: string;
}

// HA lock states: locked | unlocked | open | locking | unlocking | opening | jammed
export function LockCard({ entity, token, displayName }: Props) {
  const state = entity.state;
  const isLocked = state === "locked" || state === "locking";
  const isUnlocked = state === "unlocked" || state === "unlocking";
  const isOpen = state === "open" || state === "opening";

  const [confirming, setConfirming] = useState<"open" | "unlock" | null>(null);

  function requestConfirm(action: "open" | "unlock") {
    setConfirming(action);
    setTimeout(() => setConfirming(null), 4000);
  }

  async function handleOpen() {
    if (confirming !== "open") { requestConfirm("open"); return; }
    setConfirming(null);
    await callAction(token, entity.entity_id, "open");
  }

  async function handleUnlock() {
    if (confirming !== "unlock") { requestConfirm("unlock"); return; }
    setConfirming(null);
    await callAction(token, entity.entity_id, "unlock");
  }

  async function handleLock() {
    setConfirming(null);
    await callAction(token, entity.entity_id, "lock");
  }

  return (
    <div class={`card card--lock ${isLocked ? "is-locked" : isOpen ? "is-open" : "is-unlocked"}`}>
      <div class="card-header">
        <div class="card-icon">{isLocked ? "🔒" : isOpen ? "🚪" : "🔓"}</div>
      </div>
      <div class="card-body">
        <div class="card-name">{displayName}</div>
        <div class="card-state">{isLocked ? t.locked : isOpen ? t.open : t.unlocked}</div>
      </div>
      <div class="card-control lock-actions">
        {isLocked && (
          <>
            <button
              class={`btn-lock btn-lock--open ${confirming === "open" ? "confirming" : ""}`}
              onClick={handleOpen}
            >
              {confirming === "open" ? t.confirm : t.open}
            </button>
            <button
              class={`btn-lock btn-lock--unlock ${confirming === "unlock" ? "confirming" : ""}`}
              onClick={handleUnlock}
            >
              {confirming === "unlock" ? t.confirm : t.unlock}
            </button>
          </>
        )}
        {isUnlocked && (
          <>
            <button
              class={`btn-lock btn-lock--open ${confirming === "open" ? "confirming" : ""}`}
              onClick={handleOpen}
            >
              {confirming === "open" ? t.confirm : t.open}
            </button>
            <button class="btn-lock btn-lock--lock" onClick={handleLock}>{t.lock}</button>
          </>
        )}
        {isOpen && (
          <button class="btn-lock btn-lock--lock" onClick={handleLock}>{t.lock}</button>
        )}
      </div>
    </div>
  );
}
