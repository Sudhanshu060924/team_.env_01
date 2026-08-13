"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { WSMessage } from "@/types/ai";

export type WSStatus = "disconnected" | "connecting" | "connected" | "error";

interface UseLectureWebSocketOptions {
  lectureId: string | null;
  onMessage: (msg: WSMessage) => void;
}

export function useLectureWebSocket({
  lectureId,
  onMessage,
}: UseLectureWebSocketOptions) {
  const [status, setStatus] = useState<WSStatus>("disconnected");

  const wsRef = useRef<WebSocket | null>(null);
  const mountedRef = useRef(false);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const connectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const onMessageRef = useRef(onMessage);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const clearTimers = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    if (connectTimerRef.current !== null) {
      clearTimeout(connectTimerRef.current);
      connectTimerRef.current = null;
    }
  }, []);

  const closeSocket = useCallback(() => {
    const ws = wsRef.current;

    if (!ws) {
      return;
    }

    // Remove handlers first so intentional cleanup
    // cannot trigger reconnect.
    ws.onopen = null;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;

    if (
      ws.readyState === WebSocket.CONNECTING ||
      ws.readyState === WebSocket.OPEN
    ) {
      ws.close();
    }

    wsRef.current = null;
  }, []);

  const disconnect = useCallback(() => {
    clearTimers();
    closeSocket();

    if (mountedRef.current) {
      setStatus("disconnected");
    }
  }, [clearTimers, closeSocket]);

  const connect = useCallback(() => {
    if (!lectureId || !mountedRef.current) {
      return;
    }

    clearTimers();

    // Never create a second socket.
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.CONNECTING ||
        wsRef.current.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

    const url = `${wsBase}/ws/lectures/${lectureId}`;

    console.log("[LectureWS] connecting:", url);

    setStatus("connecting");

    const ws = new WebSocket(url);

    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current || wsRef.current !== ws) {
        return;
      }

      console.log("[LectureWS] connected:", lectureId);

      setStatus("connected");
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current || wsRef.current !== ws) {
        return;
      }

      try {
        const message: WSMessage = JSON.parse(event.data);

        console.log("[LectureWS] received:", message);

        onMessageRef.current(message);
      } catch (error) {
        console.error("[LectureWS] invalid message:", event.data, error);
      }
    };

    ws.onerror = (event) => {
      if (!mountedRef.current || wsRef.current !== ws) {
        return;
      }

      console.error("[LectureWS] error:", event);

      setStatus("error");
    };

    ws.onclose = (event) => {
      if (wsRef.current === ws) {
        wsRef.current = null;
      }

      console.log(
        "[LectureWS] closed",
        "code:",
        event.code,
        "reason:",
        event.reason,
      );

      if (!mountedRef.current) {
        return;
      }

      setStatus("disconnected");

      // Reconnect after 3 seconds.
      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current && lectureId && wsRef.current === null) {
          connect();
        }
      }, 3000);
    };
  }, [lectureId, clearTimers]);

  /*
   * IMPORTANT:
   *
   * Delay the first connection slightly.
   *
   * In Next.js development mode React Strict Mode can do:
   *
   * mount
   * -> effect
   * -> cleanup
   * -> mount again
   *
   * Without this delay, the first WebSocket can be created
   * and immediately closed, producing:
   *
   * "WebSocket is closed before the connection is established"
   */
  useEffect(() => {
    mountedRef.current = true;

    clearTimers();
    closeSocket();

    if (!lectureId) {
      setStatus("disconnected");

      return () => {
        mountedRef.current = false;
        clearTimers();
        closeSocket();
      };
    }

    connectTimerRef.current = setTimeout(() => {
      if (mountedRef.current && lectureId) {
        connect();
      }
    }, 100);

    return () => {
      mountedRef.current = false;

      clearTimers();
      closeSocket();
    };
  }, [lectureId, connect, clearTimers, closeSocket]);

  const sendMessage = useCallback((message: object) => {
    const ws = wsRef.current;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn("[LectureWS] Cannot send — WebSocket is not open");
      return;
    }

    console.log("[LectureWS] sending:", message);

    ws.send(JSON.stringify(message));
  }, []);

  // Keepalive
  useEffect(() => {
    if (status !== "connected") {
      return;
    }

    const interval = setInterval(() => {
      sendMessage({
        type: "ping",
      });
    }, 20_000);

    return () => {
      clearInterval(interval);
    };
  }, [status, sendMessage]);

  return {
    status,
    sendMessage,
    disconnect,
    connect,
  };
}
