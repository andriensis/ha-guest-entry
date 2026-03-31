import { type Entity, callAction } from "../lib/api";
import { t } from "../lib/i18n";

interface Props {
  entity: Entity;
  token: string;
  displayName: string;
}

export function CoverCard({ entity, token, displayName }: Props) {
  const position = entity.attributes.current_position as number | undefined;
  const isOpen = entity.state === "open";

  return (
    <div class="card card--cover">
      <div class="card-header">
        <div class="card-icon">{isOpen ? "🔓" : "🔒"}</div>
      </div>
      <div class="card-body">
        <div class="card-name">{displayName}</div>
        <div class="card-state">
          {position !== undefined ? `${position}%` : entity.state}
        </div>
      </div>
      <div class="card-control cover-controls">
        <button class="btn-cover" onClick={() => callAction(token, entity.entity_id, "open_cover")} title={t.open}>
          <UpIcon />
        </button>
        <button class="btn-cover" onClick={() => callAction(token, entity.entity_id, "close_cover")} title={t.close}>
          <DownIcon />
        </button>
      </div>
    </div>
  );
}

function UpIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="18 15 12 9 6 15" />
    </svg>
  );
}
function DownIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
