import { type Entity, callAction } from "../lib/api";
import { t } from "../lib/i18n";

interface Props {
  entity: Entity;
  token: string;
  displayName: string;
}

export function ClimateCard({ entity, token, displayName }: Props) {
  const hvacMode = entity.attributes.hvac_mode as string | undefined;
  const hvacModes = (entity.attributes.hvac_modes as string[] | undefined) ?? [];
  const temp = entity.attributes.temperature as number | undefined;
  const currentTemp = entity.attributes.current_temperature as number | undefined;

  async function adjustTemp(delta: number) {
    if (temp === undefined) return;
    await callAction(token, entity.entity_id, "set_temperature", {
      temperature: Math.round((temp + delta) * 2) / 2,
    });
  }

  return (
    <div class="card card--climate">
      <div class="card-header">
        <div class="card-icon">🌡️</div>
        {currentTemp !== undefined && (
          <span style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.02em", marginLeft: "auto" }}>
            {currentTemp}°
          </span>
        )}
      </div>
      <div class="card-body">
        <div class="card-name">{displayName}</div>
        {temp !== undefined && (
          <div class="card-state">{t.targetTemp(temp)}</div>
        )}
      </div>
      {hvacModes.length > 1 && (
        <div class="climate-mode">
          {hvacModes.map((mode) => (
            <button
              key={mode}
              class={`mode-btn ${mode === hvacMode ? "active" : ""}`}
              onClick={() => callAction(token, entity.entity_id, "set_hvac_mode", { hvac_mode: mode })}
            >
              {mode}
            </button>
          ))}
        </div>
      )}
      {temp !== undefined && (
        <div class="temp-adjuster">
          <button class="temp-btn" onClick={() => adjustTemp(-0.5)}>−</button>
          <div class="temp-value">{temp}°</div>
          <button class="temp-btn" onClick={() => adjustTemp(0.5)}>+</button>
        </div>
      )}
    </div>
  );
}
