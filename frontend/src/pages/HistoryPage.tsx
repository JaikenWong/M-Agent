import { useEffect, useState, useRef } from "react";
import { useLocation } from "react-router-dom";
import { api } from "@/api/endpoints";
import { useTaskStore } from "@/store/taskStore";
import { useRunListStore } from "@/store/runListStore";
import type { RunEvent, RunDetail, Task } from "@/types";
import { TASK_STATUS_LABELS, TASK_STATUS_COLORS } from "@/types/models";
import ReactMarkdown from "react-markdown";
import { Clock, ChevronDown, ChevronRight, Trash2, FileText, AlertCircle, X } from "lucide-react";

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "-";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m${s}s`;
}

/** 删除按钮：点一次变红色确认态，再点执行删除，点外部或 X 取消 */
function ConfirmDeleteButton({ onConfirm, label }: { onConfirm: () => void; label: string }) {
  const [confirming, setConfirming] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!confirming) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setConfirming(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [confirming]);

  if (confirming) {
    return (
      <div ref={ref} className="flex items-center gap-1 ml-2">
        <button
          onClick={() => { setConfirming(false); onConfirm(); }}
          className="text-xs bg-red-500/20 text-red-400 border border-red-500/40 rounded px-2 py-0.5 hover:bg-red-500/30 transition-colors"
        >
          确认删除
        </button>
        <button
          onClick={() => setConfirming(false)}
          className="text-gray-500 hover:text-gray-300 transition-colors"
        >
          <X size={12} />
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={() => setConfirming(true)}
      className="text-gray-600 hover:text-red-400 transition-colors ml-2"
      title={label}
    >
      <Trash2 size={14} />
    </button>
  );
}

function TaskRow({ task }: { task: Task }) {
  const deleteTask = useTaskStore((s) => s.deleteTask);
  const [expanded, setExpanded] = useState(false);

  const duration =
    task.started_at && task.finished_at
      ? (new Date(task.finished_at).getTime() - new Date(task.started_at).getTime()) / 1000
      : null;

  return (
    <div className="bg-bg-panel rounded-lg border border-gray-800">
      <div className="flex items-center gap-3 px-4 py-2">
        <button onClick={() => setExpanded(!expanded)} className="flex-shrink-0">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <span className={`text-xs font-medium ${TASK_STATUS_COLORS[task.status]}`}>
          {TASK_STATUS_LABELS[task.status]}
        </span>
        <span className="text-sm text-gray-200 truncate flex-1">{task.name}</span>
        <span className="text-xs text-gray-600">
          <Clock size={10} className="inline mr-1" />
          {task.created_at}
        </span>
        <ConfirmDeleteButton label="删除任务" onConfirm={() => deleteTask(task.id)} />
      </div>
      {expanded && (
        <div className="border-t border-gray-800 px-4 py-3 space-y-2 text-sm">
          <div>
            <span className="text-gray-500 text-xs">Prompt</span>
            <p className="text-gray-300 mt-0.5 whitespace-pre-wrap">{task.prompt}</p>
          </div>
          {task.started_at && (
            <div className="flex gap-4 text-xs text-gray-500">
              <span>开始: {task.started_at}</span>
              {task.finished_at && <span>结束: {task.finished_at}</span>}
              <span>耗时: {formatDuration(duration)}</span>
            </div>
          )}
          {task.run_dir && (
            <div className="text-xs text-gray-500">
              <FileText size={10} className="inline mr-1" />
              {task.run_dir}
            </div>
          )}
          {task.error_message && (
            <div className="flex items-start gap-1 text-xs text-red-400">
              <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />
              <span>{task.error_message}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function HistoryPage() {
  const location = useLocation();
  const { tasks, fetchTasks } = useTaskStore();
  const runs = useRunListStore((s) => s.runs);
  const fetchRuns = useRunListStore((s) => s.fetchRuns);
  const deleteRun = useRunListStore((s) => s.deleteRun);
  const [expandedRun, setExpandedRun] = useState<string | null>(null);
  const [runEvents, setRunEvents] = useState<RunEvent[]>([]);
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);

  useEffect(() => {
    if (location.pathname !== "/history") return;
    fetchTasks();
    void fetchRuns();
  }, [location.pathname, fetchTasks, fetchRuns]);

  const handleExpandRun = async (runId: string) => {
    if (expandedRun === runId) {
      setExpandedRun(null);
      setRunEvents([]);
      setRunDetail(null);
      return;
    }
    setExpandedRun(runId);
    const [events, detail] = await Promise.all([
      api.getRunEvents(runId),
      api.getRunDetail(runId),
    ]);
    setRunEvents(events);
    setRunDetail(detail);
  };

  const handleDeleteRun = async (runId: string) => {
    await deleteRun(runId);
    if (expandedRun === runId) {
      setExpandedRun(null);
      setRunEvents([]);
      setRunDetail(null);
    }
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
              <TaskRow key={t.id} task={t} />
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
                  <div className="flex items-center gap-2 w-full px-4 py-2">
                    <button onClick={() => handleExpandRun(r.run_id)} className="flex-shrink-0">
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                    <span className="text-sm text-gray-200">{r.project}</span>
                    <span className="text-sm text-gray-500">{r.workflow}</span>
                    <span className="text-xs text-gray-600 ml-auto">{r.started_at}</span>
                    <ConfirmDeleteButton label="删除运行记录" onConfirm={() => handleDeleteRun(r.run_id)} />
                  </div>
                  {isExpanded && (
                    <div className="border-t border-gray-800 px-4 py-3 space-y-4 max-h-[36rem] overflow-y-auto">
                      {runDetail && (
                        <div className="space-y-3">
                          {runDetail.task_content && (
                            <div>
                              <h3 className="text-xs font-medium text-gray-500 mb-1">任务描述</h3>
                              <div className="bg-gray-900/50 rounded p-3 text-sm">
                                <ReactMarkdown className="prose prose-invert prose-sm max-w-none">
                                  {runDetail.task_content}
                                </ReactMarkdown>
                              </div>
                            </div>
                          )}
                          {runDetail.summary_content && (
                            <div>
                              <h3 className="text-xs font-medium text-gray-500 mb-1">运行摘要</h3>
                              <div className="bg-gray-900/50 rounded p-3 text-sm">
                                <ReactMarkdown className="prose prose-invert prose-sm max-w-none">
                                  {runDetail.summary_content}
                                </ReactMarkdown>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                      <div>
                        <h3 className="text-xs font-medium text-gray-500 mb-1">事件流</h3>
                        <div className="space-y-2">
                          {runEvents.map((ev, i) => (
                            <div key={i} className="text-sm">
                              {ev.agent && (
                                <span className="text-xs font-medium text-cyan-400">{ev.agent}: </span>
                              )}
                              {ev.content && (
                                <ReactMarkdown className="prose prose-invert prose-sm max-w-none inline">
                                  {ev.content}
                                </ReactMarkdown>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
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
