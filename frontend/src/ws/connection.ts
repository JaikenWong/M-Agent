/** 与 `magent-tui serve --port` 一致；Tauri/静态页直连本机后端 */
export const WS_URL = "ws://127.0.0.1:8765/ws";

/**
 * 浏览器 `vite` 开发时走当前页的 `/ws`（由 vite 代理到 8765）；
 * 生产/Tauri 打包后用固定本机地址（与 tauri.conf CSP 一致）。
 */
export function getWebSocketConnectUrl(): string {
  if (typeof window === "undefined") {
    return WS_URL;
  }
  if (import.meta.env.DEV) {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/ws`;
  }
  return WS_URL;
}

const MAX_BACKOFF_MS = 30_000;

type MessageHandler = (data: unknown) => void;
type StatusHandler = (connected: boolean) => void;

/** 多播：多组件共用同一 Ws 单例时，各实例都能收到状态与消息。 */
const messageSubscribers = new Set<MessageHandler>();
const statusSubscribers = new Set<StatusHandler>();

function broadcastMessage(data: unknown): void {
  for (const fn of messageSubscribers) {
    try {
      fn(data);
    } catch (e) {
      console.error("[WebSocket] message handler", e);
    }
  }
}

function broadcastStatus(connected: boolean): void {
  for (const fn of statusSubscribers) {
    try {
      fn(connected);
    } catch (e) {
      console.error("[WebSocket] status handler", e);
    }
  }
}

export function subscribeWsMessage(fn: MessageHandler): () => void {
  messageSubscribers.add(fn);
  return () => {
    messageSubscribers.delete(fn);
  };
}

export function subscribeWsStatus(fn: StatusHandler): () => void {
  statusSubscribers.add(fn);
  return () => {
    statusSubscribers.delete(fn);
  };
}

/**
 * 底层连接：不感知 React；状态与消息经 subscribe 多播到所有当前订阅者。
 */
export class WsConnection {
  private ws: WebSocket | null = null;
  private backoffMs = 1000;
  private intentionalClose = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect(url: string = getWebSocketConnectUrl()): void {
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
      broadcastStatus(true);
    };

    ws.onmessage = (e) => {
      try {
        broadcastMessage(JSON.parse(e.data as string));
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      if (!this.intentionalClose) {
        broadcastStatus(false);
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

  /** @returns 是否已写入 socket（未连接时返回 false，调用方应提示用户） */
  send(msg: unknown): boolean {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
      return true;
    }
    return false;
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

  isOpen(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}
