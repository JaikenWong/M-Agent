import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";
import { ChatPage } from "@/pages/ChatPage";
import { AgentsPage } from "@/pages/AgentsPage";
import { WorkspacePage } from "@/pages/WorkspacePage";
import { ConfigPage } from "@/pages/ConfigPage";
import { HistoryPage } from "@/pages/HistoryPage";
import { useWebSocket } from "@/ws/useWebSocket";
import { handleServerMessage } from "@/ws/messageHandler";
import { useConfigStore } from "@/store/configStore";
import { useTaskStore } from "@/store/taskStore";
import { useEffect, useState } from "react";

export default function App() {
  const { isConnected, send } = useWebSocket(handleServerMessage);
  const fetchConfig = useConfigStore((s) => s.fetchConfig);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);
  const [backendError, setBackendError] = useState<string | null>(null);

  useEffect(() => {
    fetchConfig();
    fetchTasks();
  }, []);

  // Tauri 里若子进程未拉起（magent-tui 不在 PATH 等），在界面提示原因
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const s = await invoke<{ last_error: string | null; running: boolean }>("get_server_status");
        if (alive && s?.last_error) setBackendError(s.last_error);
      } catch {
        // 仅浏览器/无 Tauri
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <BrowserRouter>
      <Layout isConnected={isConnected} send={send} backendError={backendError}>
        <Routes>
          <Route path="/" element={<ChatPage send={send} isConnected={isConnected} />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/workspace" element={<WorkspacePage />} />
          <Route path="/config" element={<ConfigPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
