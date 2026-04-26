import { useState, useRef, useEffect, type ReactNode } from "react";
import type { ClientMessage } from "@/types";
import { useRunStore } from "@/store/runStore";
import { useConfigStore } from "@/store/configStore";
import { AGENT_COLORS } from "@/types/models";
import ReactMarkdown from "react-markdown";
import { Send, Square, Loader2, X, CheckCircle2, AlertCircle, Ban } from "lucide-react";
import type { RunOutcome } from "@/store/runStore";

interface ChatPageProps {
  send: (msg: ClientMessage) => boolean;
  isConnected: boolean;
}

export function ChatPage({ send, isConnected }: ChatPageProps) {
  const [input, setInput] = useState("");
  const [sendHint, setSendHint] = useState<string | null>(null);
  const { events, running, error, lastOutcome, clear, dismissLastOutcome } = useRunStore();
  const config = useConfigStore((s) => s.config);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const handleSubmit = () => {
    const prompt = input.trim();
    if (!prompt || running) return;
    if (!isConnected) {
      setSendHint("未连上后端 WebSocket。请在本机先启动：magent-tui serve（默认 8765），再发任务。");
      return;
    }
    const ok = send({ type: "start_task", prompt });
    if (!ok) {
      setSendHint("消息未发出（连接未就绪）。请等左侧 Wi‑Fi 变绿，或刷新页面后重试。");
      return;
    }
    setSendHint(null);
    setInput("");
  };

  const handleCancel = () => {
    void send({ type: "cancel_task", task_id: "" });
  };

  const agentColorMap = new Map<string, string>();
  let colorIdx = 0;
  const outcomeBar = (o: RunOutcome) => {
    const base =
      "flex items-start gap-2 px-3 py-2.5 text-sm border-b border-gray-800 shrink-0";
    if (o.kind === "success") {
      return {
        className: `${base} bg-emerald-950/40 text-emerald-100 border-emerald-800/50`,
        icon: <CheckCircle2 size={18} className="text-emerald-400 shrink-0 mt-0.5" />,
        title: "任务已完成",
      };
    }
    if (o.kind === "cancelled") {
      return {
        className: `${base} bg-amber-950/35 text-amber-100 border-amber-800/50`,
        icon: <Ban size={18} className="text-amber-400 shrink-0 mt-0.5" />,
        title: "已取消",
      };
    }
    return {
      className: `${base} bg-red-950/35 text-red-100 border-red-800/50`,
      icon: <AlertCircle size={18} className="text-red-400 shrink-0 mt-0.5" />,
      title: "未成功",
    };
  };

  const getColor = (agent?: string | null) => {
    if (!agent || agent === "system") return "text-gray-400";
    if (!agentColorMap.has(agent)) {
      agentColorMap.set(agent, AGENT_COLORS[colorIdx % AGENT_COLORS.length]);
      colorIdx++;
    }
    return agentColorMap.get(agent)!;
  };

  let lastOutcomeBar: ReactNode = null;
  if (lastOutcome) {
    const bar = outcomeBar(lastOutcome);
    lastOutcomeBar = (
      <div className={bar.className}>
        {bar.icon}
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-100">{bar.title}</p>
          <p className="text-gray-300/95 mt-0.5 leading-relaxed whitespace-pre-wrap">
            {lastOutcome.message}
          </p>
        </div>
        <button
          type="button"
          onClick={dismissLastOutcome}
          className="p-1 rounded text-gray-400 hover:text-white hover:bg-white/10 shrink-0"
          title="关闭"
        >
          <X size={16} />
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {!isConnected ? (
        <div className="shrink-0 px-3 py-2 text-xs sm:text-sm text-amber-100 bg-amber-950/50 border-b border-amber-800/60">
          <strong className="text-amber-50">未连接后端。</strong>{" "}
          在仓库根目录另开终端执行{" "}
          <code className="rounded bg-black/30 px-1.5 py-0.5 text-amber-200">magent-tui serve</code>
          {" "}（或 <code className="rounded bg-black/30 px-1.5 py-0.5">magent-tui serve -c configs/default.yaml</code>
          ），看到左侧栏 Wi‑Fi 变绿后再输入「傅立叶变换」等任务。
        </div>
      ) : null}
      {sendHint ? (
        <div className="shrink-0 px-3 py-1.5 text-xs text-red-200 bg-red-950/40 border-b border-red-900/50 flex justify-between gap-2">
          <span>{sendHint}</span>
          <button
            type="button"
            className="shrink-0 text-red-300 hover:text-white underline"
            onClick={() => setSendHint(null)}
          >
            关闭
          </button>
        </div>
      ) : null}
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
              <div
                key={i}
                className="max-w-md mx-auto rounded-lg border border-emerald-800/60 bg-emerald-950/30 px-3 py-2 text-sm text-center text-emerald-200"
              >
                <span className="font-medium">✓ {ev.content ?? "运行完成"}</span>
              </div>
            );
          }
          if (ev.event_type === "run_failed") {
            return (
              <div
                key={i}
                className="max-w-md mx-auto rounded-lg border border-red-800/60 bg-red-950/30 px-3 py-2 text-sm text-center text-red-200"
              >
                <span className="font-medium">✗ {ev.content ?? "运行失败"}</span>
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

      {lastOutcomeBar}

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
