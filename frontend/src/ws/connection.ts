export const WS_URL = "ws://127.0.0.1:8765/ws";

const MAX_BACKOFF_MS = 30_000;

type MessageHandler = (data: unknown) => void;
type StatusHandler = (connected: boolean) => void;

export class WsConnection {
  private ws: WebSocket | null = null;
  private backoffMs = 1000;
  private intentionalClose = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private onMessage: MessageHandler;
  private onStatus: StatusHandler;

  constructor(onMessage: MessageHandler, onStatus: StatusHandler) {
    this.onMessage = onMessage;
    this.onStatus = onStatus;
  }

  connect(url: string = WS_URL): void {
    this.intentionalClose = false;
    this._connect(url);
  }

  private _connect(url: string): void {
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
    }
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.backoffMs = 1000;
      this.onStatus(true);
    };

    ws.onmessage = (e) => {
      try {
        this.onMessage(JSON.parse(e.data as string));
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      this.onStatus(false);
      if (!this.intentionalClose) {
        this.reconnectTimer = setTimeout(() => {
          this.backoffMs = Math.min(this.backoffMs * 2, MAX_BACKOFF_MS);
          this._connect(url);
        }, this.backoffMs);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  send(msg: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  close(): void {
    this.intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }
}
