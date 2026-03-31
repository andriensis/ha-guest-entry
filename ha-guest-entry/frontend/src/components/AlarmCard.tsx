import { useState } from "preact/hooks";
import { type Entity, callAction } from "../lib/api";

interface Props {
  entity: Entity;
  token: string;
  displayName: string;
}

type ArmMode = "arm_home" | "arm_away" | "arm_night";

// HA alarm_control_panel states
const ARMED_STATES = new Set([
  "armed_home", "armed_away", "armed_night", "armed_vacation", "armed_custom_bypass",
]);
const PENDING_STATES = new Set(["arming", "disarming", "pending"]);

function stateLabel(state: string): string {
  const map: Record<string, string> = {
    disarmed: "Disarmed",
    armed_home: "Armed Home",
    armed_away: "Armed Away",
    armed_night: "Armed Night",
    armed_vacation: "Armed Vacation",
    armed_custom_bypass: "Armed Custom",
    arming: "Arming…",
    disarming: "Disarming…",
    pending: "Pending…",
    triggered: "TRIGGERED",
    unavailable: "Unavailable",
    unknown: "Unknown",
  };
  return map[state] ?? state;
}

export function AlarmCard({ entity, token, displayName }: Props) {
  const state = entity.state;
  const attrs = entity.attributes as Record<string, unknown>;
  const codeRequired: boolean = (attrs.code_required as boolean) ?? false;
  const codeFormat: string = (attrs.code_format as string) ?? "number";

  const isDisarmed = state === "disarmed";
  const isArmed = ARMED_STATES.has(state);
  const isPending = PENDING_STATES.has(state);
  const isTriggered = state === "triggered";

  const [code, setCode] = useState("");
  const [pendingAction, setPendingAction] = useState<ArmMode | "disarm" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function execute(action: ArmMode | "disarm") {
    setBusy(true);
    setError(null);
    const serviceAction = action === "disarm" ? "alarm_disarm" : `alarm_${action}` as string;
    const params: Record<string, string> = codeRequired && code ? { code } : {};
    try {
      await callAction(token, entity.entity_id, serviceAction, params);
      setCode("");
      setPendingAction(null);
    } catch (e) {
      setError((e as Error).message ?? "Failed");
    } finally {
      setBusy(false);
    }
  }

  function selectAction(action: ArmMode | "disarm") {
    setPendingAction(action);
    setError(null);
    if (!codeRequired) {
      execute(action);
    }
  }

  const cardClass = `card card--alarm ${
    isTriggered ? "is-triggered" : isArmed ? "is-armed" : isPending ? "is-pending" : "is-disarmed"
  }`;

  return (
    <div class={cardClass}>
      <div class="card-header">
        <div class="card-icon">
          {isTriggered ? "🚨" : isArmed ? "🛡️" : isPending ? "⏳" : "🔔"}
        </div>
      </div>
      <div class="card-body">
        <div class="card-name">{displayName}</div>
        <div class="card-state">{stateLabel(state)}</div>
      </div>
      <div class="card-control alarm-actions">
        {!isPending && (
          <>
            {isDisarmed && (
              <div class="alarm-arm-buttons">
                <button class="btn-alarm btn-alarm--home" onClick={() => selectAction("arm_home")} disabled={busy}>Home</button>
                <button class="btn-alarm btn-alarm--away" onClick={() => selectAction("arm_away")} disabled={busy}>Away</button>
                <button class="btn-alarm btn-alarm--night" onClick={() => selectAction("arm_night")} disabled={busy}>Night</button>
              </div>
            )}
            {(isArmed || isTriggered) && (
              <button class="btn-alarm btn-alarm--disarm" onClick={() => selectAction("disarm")} disabled={busy}>
                Disarm
              </button>
            )}
            {codeRequired && pendingAction !== null && (
              <div class="alarm-code-entry">
                <input
                  type={codeFormat === "number" ? "tel" : "text"}
                  inputMode={codeFormat === "number" ? "numeric" : "text"}
                  class="alarm-code-input"
                  placeholder="Code"
                  value={code}
                  onInput={(e) => setCode((e.target as HTMLInputElement).value)}
                  maxLength={10}
                  autoFocus
                />
                <button
                  class="btn-alarm btn-alarm--confirm"
                  onClick={() => execute(pendingAction)}
                  disabled={busy || !code}
                >
                  {busy ? "…" : "OK"}
                </button>
              </div>
            )}
            {error && <div class="alarm-error">{error}</div>}
          </>
        )}
      </div>
    </div>
  );
}
