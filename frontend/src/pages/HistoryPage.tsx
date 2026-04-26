import { useEffect, useState } from "react";
import { api } from "@/api/endpoints";
import { useTaskStore } from "@/store/taskStore";
import type { RunEvent, RunSummary } from "@/types";
import { TASK_STATUS_LABELS, TASK_STATUS_COLORS } from "@/types/models";
import ReactMarkdown from "react-markdown";
import { Clock, ChevronDown, ChevronRight } from "lucide-react";

export function HistoryPage() {
  const { tasks, fetchTasks } = useTaskStore();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [expandedRun, setExpandedRun] = useState<string | null>(null);
  const [runEvents, setRunEvents] = useState<RunEvent[]>([]);

  useEffect(() => {
    fetchTasks();
    api.listRuns().then(setRuns).catch(() => {});
  }, []);

  const handleExpand = async (runId: string) => {
    if (expandedRun === runId) {
      setExpandedRun(null);
      return;
    }
    setExpandedRun(runId);
    const events = await api.getRunEvents(runId);
    setRunEvents(events);
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {/* Tasks */}
      <section>
        <h2 className="text-lg font-semibold mb-3">任务</h2>
        {tasks.length === 0 ? (
          <div className="text-sm text-gray-600">暂无任务</div>
        ) : (
          <div className="space-y-1">
            {tasks.map((t) => (
              <div key={t.id} className="flex items-center gap-3 bg-bg-panel rounded-lg px-4 py-2 border border-gray-800">
                <span className={`text-xs font-medium ${TASK_STATUS_COLORS[t.status]}`}>
                  {TASK_STATUS_LABELS[t.status]}
                </span>
                <span className="text-sm text-gray-200 truncate">{t.name}</span>
                <span className="text-xs text-gray-600 ml-auto">
                  <Clock size={10} className="inline mr-1" />
                  {t.created_at}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Runs */}
      <section>
        <h2 className="text-lg font-semibold mb-3">运行记录</h2>
        {runs.length === 0 ? (
          <div className="text-sm text-gray-600">暂无运行记录</div>
        ) : (
          <div className="space-y-1">
            {runs.map((r) => {
              const isExpanded = expandedRun === r.run_id;
              return (
                <div key={r.run_id} className="bg-bg-panel rounded-lg border border-gray-800">
                  <button
                    onClick={() => handleExpand(r.run_id)}
                    className="flex items-center gap-2 w-full px-4 py-2 text-sm"
                  >
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    <span className="text-gray-200">{r.project}</span>
                    <span className="text-gray-500">{r.workflow}</span>
                    <span className="text-xs text-gray-600 ml-auto">{r.started_at}</span>
                  </button>
                  {isExpanded && (
                    <div className="border-t border-gray-800 px-4 py-2 space-y-2 max-h-96 overflow-y-auto">
                      {runEvents.map((ev, i) => (
                        <div key={i} className="text-sm">
                          {ev.agent && <span className="text-xs font-medium text-cyan-400">{ev.agent}: </span>}
                          {ev.content && (
                            <ReactMarkdown className="prose prose-invert prose-sm max-w-none inline">
                              {ev.content}
                            </ReactMarkdown>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
