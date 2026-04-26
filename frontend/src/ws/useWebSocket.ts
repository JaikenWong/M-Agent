import { useEffect, useRef, useState, useCallback } from "react";
import { WsConnection, getWebSocketConnectUrl, subscribeWsMessage, subscribeWsStatus } from "./connection";
import type { ClientMessage } from "@/types";

interface UseWebSocketReturn {
  isConnected: boolean;
  send: (msg: ClientMessage) => boolean;
}

export function useWebSocket(onMessage: (data: unknown) => void): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const connRef = useRef<WsConnection | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    const conn = new WsConnection();
    connRef.current = conn;
    const unsubMsg = subscribeWsMessage((data: unknown) => onMessageRef.current(data));
    const unsubStatus = subscribeWsStatus(setIsConnected);
    conn.connect(getWebSocketConnectUrl());
    return () => {
      unsubMsg();
      unsubStatus();
      conn.close();
    };
  }, []);

  const send = useCallback((msg: ClientMessage) => {
    return connRef.current?.send(msg) ?? false;
  }, []);

  return { isConnected, send };
}
