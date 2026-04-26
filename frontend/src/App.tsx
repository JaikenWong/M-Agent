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
import { useEffect } from "react";

export default function App() {
  const { isConnected, send } = useWebSocket(handleServerMessage);
  const fetchConfig = useConfigStore((s) => s.fetchConfig);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);

  useEffect(() => {
    fetchConfig();
    fetchTasks();
  }, []);

  return (
    <BrowserRouter>
      <Layout isConnected={isConnected} send={send}>
        <Routes>
          <Route path="/" element={<ChatPage send={send} />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/workspace" element={<WorkspacePage />} />
          <Route path="/config" element={<ConfigPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
