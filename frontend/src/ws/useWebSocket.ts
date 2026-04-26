import { useEffect, useRef, useState, useCallback } from "react";
import { WsConnection, WS_URL } from "./connection";
import type { ClientMessage } from "@/types";

interface UseWebSocketReturn {
  isConnected: boolean;
  send: (msg: ClientMessage) => void;
}

export function useWebSocket(onMessage: (data: unknown) => void): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const connRef = useRef<WsConnection | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    const conn = new WsConnection(
      (data) => onMessageRef.current(data),
      setIsConnected
    );
    connRef.current = conn;
    conn.connect(WS_URL);
    return () => conn.close();
  }, []);

  const send = useCallback((msg: ClientMessage) => {
    connRef.current?.send(msg);
  }, []);

  return { isConnected, send };
}
