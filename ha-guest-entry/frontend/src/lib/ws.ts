/** WebSocket client with reconnect and per-entity state callbacks. */

export type WsMessage =
  | { type: "state_changed"; entity_id: string; state: string; attributes: Record<string, unknown>; changed_at: string }
  | { type: "access_revoked"; reason: string }
  | { type: "pong" }
  | { type: "error"; message: string };

type StateChangedHandler = (msg: Extract<WsMessage, { type: "state_changed" }>) => void;
type AccessRevokedHandler = (reason: string) => void;

const WS_PROTO = location.protocol === "https:" ? "wss:" : "ws:";
const WS_URL = `${WS_PROTO}//${location.host}/api/v1/ws`;
const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_DELAY_MS = 30000;

export class GuestWsClient {
  private ws: WebSocket | null = null;
  private token: string;
  private _onStateChanged: StateChangedHandler;
  private _onAccessRevoked: AccessRevokedHandler;
  private reconnectDelay = RECONNECT_DELAY_MS;
  private stopped = false;

  constructor(
    token: string,
    onStateChanged: StateChangedHandler,
    onAccessRevoked: AccessRevokedHandler
  ) {
    this.token = token;
    this._onStateChanged = onStateChanged;
    this._onAccessRevoked = onAccessRevoked;
    this._connect();
  }

  private _connect(): void {
    if (this.stopped) return;
    const url = WS_URL;
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.reconnectDelay = RECONNECT_DELAY_MS;
      // Send token via first message (fallback for browsers that can't set headers)
      ws.send(JSON.stringify({ type: "auth", token: this.token }));
    };

    ws.onmessage = (evt) => {
      let msg: WsMessage;
      try {
        msg = JSON.parse(evt.data as string) as WsMessage;
      } catch {
        return;
      }
      if (msg.type === "state_changed") {
        this._onStateChanged(msg);
      } else if (msg.type === "access_revoked") {
        this._onAccessRevoked(msg.reason);
        this.stop();
      } else if (msg.type === "pong") {
        // keepalive ack — ignore
      }
    };

    ws.onclose = () => {
      if (!this.stopped) {
        setTimeout(() => this._connect(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, MAX_RECONNECT_DELAY_MS);
      }
    };

    // Keepalive ping every 25s
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      } else {
        clearInterval(pingInterval);
      }
    }, 25000);
  }

  stop(): void {
    this.stopped = true;
    this.ws?.close();
  }
}
