import { useState } from "preact/hooks";
import { type Entity, callAction } from "../lib/api";
import { t } from "../lib/i18n";

interface Props {
  entity: Entity;
  token: string;
  displayName: string;
}

export function LightCard({ entity, token, displayName }: Props) {
  const isOn = entity.state === "on";
  const [pending, setPending] = useState(false);

  async function toggle() {
    if (pending) return;
    setPending(true);
    try {
      await callAction(token, entity.entity_id, "toggle");
    } finally {
      setPending(false);
    }
  }

  return (
    <div class={`card card--light ${isOn ? "is-on" : ""}`}>
      <div class="card-header">
        <div class="card-icon">{isOn ? "💡" : "🔆"}</div>
      </div>
      <div class="card-body">
        <div class="card-name">{displayName}</div>
        <div class="card-state">{isOn ? t.on : t.off}</div>
      </div>
      <div class="card-control">
        <label class="toggle toggle--light" title={isOn ? t.off : t.on}>
          <input type="checkbox" checked={isOn} disabled={pending} onChange={toggle} />
          <span class="toggle-slider" />
        </label>
      </div>
    </div>
  );
}
