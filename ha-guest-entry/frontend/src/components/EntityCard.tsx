import { type Entity, callAction } from "../lib/api";
import { LightCard } from "./LightCard";
import { SwitchCard } from "./SwitchCard";
import { CoverCard } from "./CoverCard";
import { ClimateCard } from "./ClimateCard";
import { LockCard } from "./LockCard";
import { AlarmCard } from "./AlarmCard";

interface Props {
  entity: Entity;
  token: string;
}

export function EntityCard({ entity, token }: Props) {
  const displayName = entity.label ?? entity.name;

  switch (entity.domain) {
    case "light":
      return <LightCard entity={entity} token={token} displayName={displayName} />;
    case "switch":
      return <SwitchCard entity={entity} token={token} displayName={displayName} />;
    case "cover":
      return <CoverCard entity={entity} token={token} displayName={displayName} />;
    case "climate":
      return <ClimateCard entity={entity} token={token} displayName={displayName} />;
    case "lock":
      return <LockCard entity={entity} token={token} displayName={displayName} />;
    case "alarm_control_panel":
      return <AlarmCard entity={entity} token={token} displayName={displayName} />;
    default:
      return <GenericCard entity={entity} token={token} displayName={displayName} />;
  }
}

function GenericCard({ entity, token, displayName }: Props & { displayName: string }) {
  const isOn = entity.state === "on";
  return (
    <div class={`card ${isOn ? "card--switch is-on" : ""}`}>
      <div class="card-header">
        <div class="card-icon">⚡</div>
      </div>
      <div class="card-body">
        <div class="card-name">{displayName}</div>
        <div class="card-state">{entity.state}</div>
      </div>
      <div class="card-control">
        <label class="toggle">
          <input type="checkbox" checked={isOn} onChange={() => callAction(token, entity.entity_id, "toggle")} />
          <span class="toggle-slider" />
        </label>
      </div>
    </div>
  );
}
