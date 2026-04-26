import { useEffect, useState } from "react";
import { useConfigStore } from "@/store/configStore";
import { api } from "@/api/endpoints";
import type { DoctorCheck, Template } from "@/types";
import { CheckCircle, XCircle, RefreshCw } from "lucide-react";

export function ConfigPage() {
  const config = useConfigStore((s) => s.config);
  const setConfig = useConfigStore((s) => s.setConfig);
  const fetchConfig = useConfigStore((s) => s.fetchConfig);
  const [checks, setChecks] = useState<DoctorCheck[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.runDoctor().then(setChecks).catch(() => {});
    api.listTemplates().then(setTemplates).catch(() => {});
  }, []);

  const handleUpdate = async (updates: Record<string, unknown>) => {
    setSaving(true);
    try {
      const updated = await api.updateConfig(updates);
      setConfig(updated);
    } finally {
      setSaving(false);
    }
  };

  const handleApplyTemplate = async (name: string) => {
    await api.applyTemplate(name);
    await fetchConfig();
  };

  if (!config) return <div className="p-6 text-gray-500">加载中...</div>;

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {/* Project settings */}
      <section>
        <h2 className="text-lg font-semibold mb-3">项目配置</h2>
        <div className="space-y-3 bg-bg-panel rounded-lg p-4 border border-gray-800">
          <Field label="项目名称" value={config.project_name} onSave={(v) => handleUpdate({ project_name: v })} />
          <Field label="工作目录" value={config.workspace_root} onSave={(v) => handleUpdate({ workspace_root: v })} />
          <div className="flex gap-4">
            <div className="flex-1">
              <label className="text-xs text-gray-500">协作模式</label>
              <select
                value={config.workflow.mode}
                onChange={(e) => handleUpdate({ workflow_mode: e.target.value })}
                className="w-full mt-1 bg-bg-base rounded px-3 py-1.5 text-sm border border-gray-700 focus:outline-none focus:border-accent"
              >
                <option value="round_robin">round_robin</option>
                <option value="selector">selector</option>
                <option value="single">single</option>
                <option value="pipeline">pipeline</option>
              </select>
            </div>
            <div className="w-32">
              <label className="text-xs text-gray-500">最大轮数</label>
              <input
                type="number"
                value={config.workflow.max_turns}
                onChange={(e) => handleUpdate({ max_turns: Number(e.target.value) })}
                className="w-full mt-1 bg-bg-base rounded px-3 py-1.5 text-sm border border-gray-700 focus:outline-none focus:border-accent"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Models */}
      <section>
        <h2 className="text-lg font-semibold mb-3">模型</h2>
        <div className="space-y-2">
          {Object.entries(config.models).map(([key, m]) => (
            <div key={key} className="bg-bg-panel rounded-lg p-3 border border-gray-800 text-sm">
              <span className="font-medium text-gray-200">{key}</span>
              <span className="text-gray-500 ml-2">{m.provider}/{m.model}</span>
              {m.api_key && <span className="text-green-500 ml-2 text-xs">✓ key</span>}
              {!m.api_key && <span className="text-red-400 ml-2 text-xs">✗ no key</span>}
            </div>
          ))}
        </div>
      </section>

      {/* Templates */}
      {templates.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-3">模板</h2>
          <div className="flex gap-2 flex-wrap">
            {templates.map((t) => (
              <button
                key={t.name}
                onClick={() => handleApplyTemplate(t.name)}
                className="px-3 py-1.5 rounded-lg text-xs bg-gray-800 text-gray-300 hover:bg-gray-700"
              >
                {t.name}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Doctor */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-lg font-semibold">环境诊断</h2>
          <button
            onClick={() => api.runDoctor().then(setChecks)}
            className="text-gray-500 hover:text-gray-300"
          >
            <RefreshCw size={14} />
          </button>
        </div>
        <div className="space-y-1">
          {checks.map((c, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              {c.ok ? <CheckCircle size={14} className="text-green-400" /> : <XCircle size={14} className="text-red-400" />}
              <span className="text-gray-300">{c.label}</span>
              <span className="text-gray-600 text-xs ml-auto">{c.detail}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Field({ label, value, onSave }: { label: string; value: string; onSave: (v: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  return (
    <div>
      <label className="text-xs text-gray-500">{label}</label>
      {editing ? (
        <div className="flex gap-2 mt-1">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="flex-1 bg-bg-base rounded px-3 py-1.5 text-sm border border-gray-700 focus:outline-none focus:border-accent"
          />
          <button onClick={() => { onSave(draft); setEditing(false); }} className="text-xs text-accent">保存</button>
          <button onClick={() => { setDraft(value); setEditing(false); }} className="text-xs text-gray-500">取消</button>
        </div>
      ) : (
        <div
          onClick={() => setEditing(true)}
          className="mt-1 text-sm text-gray-200 cursor-pointer hover:text-accent"
        >
          {value || "—"}
        </div>
      )}
    </div>
  );
}
