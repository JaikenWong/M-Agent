import { useEffect, useState } from "react";
import { useConfigStore } from "@/store/configStore";
import { api } from "@/api/endpoints";
import type { AgentConfig, Template } from "@/types";
import { Plus, Trash2, Download } from "lucide-react";

export function AgentsPage() {
  const config = useConfigStore((s) => s.config);
  const setConfig = useConfigStore((s) => s.setConfig);
  const agents = config?.agents ?? [];
  const [templates, setTemplates] = useState<Template[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newAgent, setNewAgent] = useState({ name: "", role: "", system_prompt: "" });

  useEffect(() => {
    api.listTemplates().then(setTemplates).catch(() => {});
  }, []);

  const handleDelete = async (index: number) => {
    await api.deleteAgent(index);
    const updated = await api.listAgents();
    if (config) setConfig({ ...config, agents: updated });
  };

  const handleAdd = async () => {
    if (!newAgent.name || !newAgent.system_prompt) return;
    await api.addAgent(newAgent);
    const updated = await api.listAgents();
    if (config) setConfig({ ...config, agents: updated });
    setNewAgent({ name: "", role: "", system_prompt: "" });
    setShowAdd(false);
  };

  const handleApplyTemplate = async (name: string) => {
    await api.applyTemplate(name);
    const updated = await api.listAgents();
    if (config) setConfig({ ...config, agents: updated });
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Agent 列表</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-accent/20 text-accent hover:bg-accent/30"
          >
            <Plus size={16} /> 添加
          </button>
        </div>
      </div>

      {/* Templates */}
      {templates.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm text-gray-400">模板</h3>
          <div className="flex gap-2 flex-wrap">
            {templates.map((t) => (
              <button
                key={t.name}
                onClick={() => handleApplyTemplate(t.name)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-gray-800 text-gray-300 hover:bg-gray-700"
              >
                <Download size={12} /> {t.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Add form */}
      {showAdd && (
        <div className="bg-bg-panel rounded-lg p-4 space-y-3 border border-gray-700">
          <input
            value={newAgent.name}
            onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
            placeholder="Agent 名称"
            className="w-full bg-bg-base rounded px-3 py-2 text-sm border border-gray-700 focus:border-accent focus:outline-none"
          />
          <input
            value={newAgent.role}
            onChange={(e) => setNewAgent({ ...newAgent, role: e.target.value })}
            placeholder="角色 (可选)"
            className="w-full bg-bg-base rounded px-3 py-2 text-sm border border-gray-700 focus:border-accent focus:outline-none"
          />
          <textarea
            value={newAgent.system_prompt}
            onChange={(e) => setNewAgent({ ...newAgent, system_prompt: e.target.value })}
            placeholder="系统提示词"
            rows={4}
            className="w-full bg-bg-base rounded px-3 py-2 text-sm border border-gray-700 focus:border-accent focus:outline-none resize-none"
          />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 text-sm text-gray-400 hover:text-gray-200">
              取消
            </button>
            <button onClick={handleAdd} className="px-3 py-1.5 text-sm bg-accent/20 text-accent rounded-lg hover:bg-accent/30">
              确认
            </button>
          </div>
        </div>
      )}

      {/* Agent cards */}
      {agents.length === 0 ? (
        <div className="text-gray-600 text-sm">暂无 Agent，请添加或导入模板。</div>
      ) : (
        <div className="space-y-2">
          {agents.map((a, i) => (
            <div key={i} className="bg-bg-panel rounded-lg p-4 flex items-start gap-3 border border-gray-800">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-100">{a.name}</div>
                {a.role && <div className="text-xs text-gray-500 mt-0.5">{a.role}</div>}
                <div className="text-xs text-gray-600 mt-1 line-clamp-2">{a.system_prompt}</div>
                <div className="flex gap-3 mt-2 text-xs text-gray-500">
                  {a.model && <span>模型: {a.model}</span>}
                  {a.workspace && <span>目录: {a.workspace}</span>}
                  {a.tools.length > 0 && <span>工具: {a.tools.join(", ")}</span>}
                </div>
              </div>
              <button
                onClick={() => handleDelete(i)}
                className="text-gray-600 hover:text-red-400 transition-colors"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
