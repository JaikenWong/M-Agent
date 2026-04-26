import { useState, useRef, useEffect } from "react";
import type { ClientMessage } from "@/types";
import { useRunStore } from "@/store/runStore";
import { useConfigStore } from "@/store/configStore";
import { AGENT_COLORS, TASK_STATUS_COLORS } from "@/types/models";
import ReactMarkdown from "react-markdown";
import { Send, Square, Loader2 } from "lucide-react";

interface ChatPageProps {
  send: (msg: ClientMessage) => void;
}

export function ChatPage({ send }: ChatPageProps) {
  const [input, setInput] = useState("");
  const { events, running, error, clear } = useRunStore();
  const config = useConfigStore((s) => s.config);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const handleSubmit = () => {
    const prompt = input.trim();
    if (!prompt || running) return;
    send({ type: "start_task", prompt });
    setInput("");
  };

  const handleCancel = () => {
    send({ type: "cancel_task", task_id: "" });
  };

  const agentColorMap = new Map<string, string>();
  let colorIdx = 0;
  const getColor = (agent?: string | null) => {
    if (!agent || agent === "system") return "text-gray-400";
    if (!agentColorMap.has(agent)) {
      agentColorMap.set(agent, AGENT_COLORS[colorIdx % AGENT_COLORS.length]);
      colorIdx++;
    }
    return agentColorMap.get(agent)!;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Status bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-800 text-sm text-gray-400">
        <span className="font-medium text-gray-200">
          {config?.project_name ?? "m-agent"}
        </span>
        <span>·</span>
        <span>{config?.workflow.mode ?? "—"}</span>
        <span>·</span>
        <span>{config?.agents.length ?? 0} agents</span>
        {running && (
          <>
            <span>·</span>
            <Loader2 size={14} className="animate-spin text-blue-400" />
            <span className="text-blue-400">运行中</span>
          </>
        )}
        {error && (
          <>
            <span>·</span>
            <span className="text-red-400">{error}</span>
          </>
        )}
        {events.length > 0 && (
          <button
            onClick={clear}
            className="ml-auto text-xs text-gray-500 hover:text-gray-300"
          >
            清空
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {events.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-600">
            输入任务开始协作...
          </div>
        )}
        {events.map((ev, i) => {
          if (ev.event_type === "run_started" || ev.event_type === "run_state_changed") {
            return (
              <div key={i} className="text-xs text-gray-500 text-center">
                {ev.content ?? (ev.event_type === "run_started" ? "运行启动" : "状态变更")}
              </div>
            );
          }
          if (ev.event_type === "run_completed") {
            return (
              <div key={i} className="text-xs text-green-400 text-center">
                ✓ {ev.content ?? "运行完成"}
              </div>
            );
          }
          if (ev.event_type === "run_failed") {
            return (
              <div key={i} className="text-xs text-red-400 text-center">
                ✗ {ev.content ?? "运行失败"}
              </div>
            );
          }
          const isSystem = ev.agent === "system";
          const color = isSystem ? "text-gray-400" : getColor(ev.agent);
          return (
            <div key={i} className={isSystem ? "text-sm text-gray-500" : ""}>
              {!isSystem && ev.agent && (
                <div className={`text-xs font-semibold mb-1 ${color}`}>
                  {ev.agent}
                  {ev.role ? <span className="font-normal text-gray-500 ml-2">({ev.role})</span> : ""}
                </div>
              )}
              <div className={isSystem ? "" : "bg-bg-panel/50 rounded-lg px-3 py-2 text-sm leading-relaxed"}>
                {ev.content ? (
                  <ReactMarkdown className="prose prose-invert prose-sm max-w-none">
                    {ev.content}
                  </ReactMarkdown>
                ) : null}
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex items-center gap-2 px-4 py-3 border-t border-gray-800">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSubmit()}
          placeholder="输入任务..."
          disabled={running}
          className="flex-1 bg-bg-panel rounded-lg px-4 py-2.5 text-sm text-gray-100 placeholder-gray-600 border border-gray-700 focus:border-accent focus:outline-none disabled:opacity-50"
        />
        {running ? (
          <button
            onClick={handleCancel}
            className="p-2.5 rounded-lg bg-red-600/20 text-red-400 hover:bg-red-600/30"
          >
            <Square size={18} />
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!input.trim()}
            className="p-2.5 rounded-lg bg-accent/20 text-accent hover:bg-accent/30 disabled:opacity-30"
          >
            <Send size={18} />
          </button>
        )}
      </div>
    </div>
  );
}
