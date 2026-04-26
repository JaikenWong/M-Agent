import { useEffect, useMemo, useState } from "react";
import { useConfigStore } from "@/store/configStore";
import { api, type ModelUpsertRequest } from "@/api/endpoints";
import type {
  AppConfig,
  CredentialSource,
  DoctorCheck,
  ModelConfig,
  Provider,
  Template,
} from "@/types";
import {
  CheckCircle,
  Eye,
  EyeOff,
  KeyRound,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  XCircle,
} from "lucide-react";

const PROVIDERS: Provider[] = ["anthropic", "openai", "openai_compatible", "litellm"];

const SOURCE_LABELS: Record<CredentialSource, string> = {
  config: "本配置",
  claude_settings: "已读取 Claude settings",
  env: "环境变量",
  none: "未设置",
};

const SOURCE_TONE: Record<CredentialSource, string> = {
  config: "text-emerald-400",
  claude_settings: "text-sky-400",
  env: "text-amber-300",
  none: "text-red-400",
};

export function ConfigPage() {
  const config = useConfigStore((s) => s.config);
  const configError = useConfigStore((s) => s.error);
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

  if (configError) {
    return (
      <div className="p-6 max-w-lg space-y-3">
        <p className="text-red-400 text-sm whitespace-pre-wrap">{configError}</p>
        <button
          type="button"
          onClick={() => void fetchConfig()}
          className="px-3 py-1.5 rounded-lg text-sm bg-accent/20 text-accent hover:bg-accent/30"
        >
          重试
        </button>
      </div>
    );
  }

  if (!config) {
    return <div className="p-6 text-gray-500">加载中…</div>;
  }

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {/* Project settings */}
      <section>
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
          项目配置
          {saving && <span className="text-xs font-normal text-gray-500">保存中…</span>}
        </h2>
        <div className="space-y-3 bg-bg-panel rounded-lg p-4 border border-gray-800">
          <Field label="项目名称" value={config.project_name} onSave={(v) => handleUpdate({ project_name: v })} />
          <Field label="工作目录" value={config.workspace_root} onSave={(v) => handleUpdate({ workspace_root: v })} />
          <label className="flex items-start gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              className="mt-0.5 rounded border-gray-600"
              checked={config.use_claude_code_settings !== false}
              onChange={(e) => void handleUpdate({ use_claude_code_settings: e.target.checked })}
            />
            <span>
              <span className="text-gray-200">合并 Claude Code settings</span>
              <span className="block text-xs text-gray-500 mt-0.5">
                开启时从 ~/.claude 等注入模型与密钥；关则仅用本配置与环境变量。切换后若从 YAML 启动会重新载入该文件（见 serve -c）
              </span>
            </span>
          </label>
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
          {config.workflow.liaison_agent ? (
            <p className="text-xs text-gray-500 mt-2">
              对用户的总接口（YAML 中 liaison_agent 约定，常见为 PM）：{config.workflow.liaison_agent}
            </p>
          ) : null}
        </div>
      </section>

      <ModelsSection
        config={config}
        defaultModel={config.default_model}
        onChanged={setConfig}
      />

      {/* Default model picker */}
      <section>
        <h2 className="text-lg font-semibold mb-3">默认模型</h2>
        <div className="bg-bg-panel rounded-lg p-4 border border-gray-800 space-y-2">
          <select
            value={config.default_model}
            onChange={(e) => void handleUpdate({ default_model: e.target.value })}
            className="w-full bg-bg-base rounded px-3 py-1.5 text-sm border border-gray-700 focus:outline-none focus:border-accent"
          >
            {Object.keys(config.models).map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500">
            未为某 Agent 显式指定 model 时使用该项；建议命名为 default 或与团队约定一致。
          </p>
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

interface ModelsSectionProps {
  config: AppConfig;
  defaultModel: string;
  onChanged: (cfg: AppConfig) => void;
}

function ModelsSection({ config, defaultModel, onChanged }: ModelsSectionProps) {
  const [adding, setAdding] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [error, setError] = useState<string | null>(null);

  const entries = useMemo(() => Object.entries(config.models), [config.models]);

  const handleCreate = async () => {
    setError(null);
    const key = newKey.trim();
    if (!key) {
      setError("请输入 model key（例如 default / xfyun / openai-mini）");
      return;
    }
    if (config.models[key]) {
      setError(`已存在 model: ${key}`);
      return;
    }
    try {
      const updated = await api.upsertModel(key, { provider: "anthropic", model: "claude-sonnet-4-5" });
      onChanged(updated);
      setAdding(false);
      setNewKey("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">模型</h2>
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg bg-accent/15 text-accent hover:bg-accent/25"
        >
          <Plus size={14} /> 新增模型
        </button>
      </div>

      <p className="text-xs text-gray-500 mb-3 leading-relaxed">
        系统已合并的有效凭据会显示来源（本配置 / Claude settings / 环境变量）。留空则运行时回退到合并 settings 与
        环境变量；填入后以这里的为准，避免误用。
      </p>

      {adding ? (
        <div className="bg-bg-panel rounded-lg p-3 border border-gray-800 mb-3 space-y-2 text-sm">
          <label className="text-xs text-gray-500">新模型 key</label>
          <div className="flex gap-2">
            <input
              autoFocus
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="default / xfyun / openrouter ..."
              className="flex-1 bg-bg-base rounded px-3 py-1.5 text-sm border border-gray-700 focus:outline-none focus:border-accent"
            />
            <button
              type="button"
              onClick={() => void handleCreate()}
              className="px-3 py-1.5 rounded text-xs bg-accent/20 text-accent hover:bg-accent/30"
            >
              创建
            </button>
            <button
              type="button"
              onClick={() => {
                setAdding(false);
                setNewKey("");
                setError(null);
              }}
              className="px-3 py-1.5 rounded text-xs text-gray-400 hover:text-white"
            >
              取消
            </button>
          </div>
          {error ? <p className="text-xs text-red-400">{error}</p> : null}
        </div>
      ) : null}

      <div className="space-y-3">
        {entries.length === 0 ? (
          <p className="text-sm text-gray-500">暂无模型，点「新增模型」开始配置。</p>
        ) : null}
        {entries.map(([key, m]) => (
          <ModelEditor
            key={key}
            modelKey={key}
            model={m}
            isDefault={defaultModel === key}
            onSaved={onChanged}
          />
        ))}
      </div>
    </section>
  );
}

interface ModelEditorProps {
  modelKey: string;
  model: ModelConfig;
  isDefault: boolean;
  onSaved: (cfg: AppConfig) => void;
}

function ModelEditor({ modelKey, model, isDefault, onSaved }: ModelEditorProps) {
  const [provider, setProvider] = useState<Provider>(model.provider);
  const [modelId, setModelId] = useState(model.model);
  const [apiKey, setApiKey] = useState("");
  const [apiKeyTouched, setApiKeyTouched] = useState(false);
  const [baseUrl, setBaseUrl] = useState(model.base_url ?? "");
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setProvider(model.provider);
    setModelId(model.model);
    setBaseUrl(model.base_url ?? "");
    setApiKey("");
    setApiKeyTouched(false);
  }, [
    model.provider,
    model.model,
    model.base_url,
    model.resolved_api_key_present,
    model.resolved_api_key_source,
  ]);

  const dirty =
    provider !== model.provider ||
    modelId !== (model.model ?? "") ||
    baseUrl !== (model.base_url ?? "") ||
    apiKeyTouched;

  const keySource: CredentialSource = model.resolved_api_key_source ?? "none";
  const baseSource: CredentialSource = model.resolved_base_url_source ?? "none";

  const handleSave = async () => {
    setSaving(true);
    setErr(null);
    try {
      const payload: ModelUpsertRequest = { provider, model: modelId, base_url: baseUrl };
      if (apiKeyTouched) payload.api_key = apiKey;
      const updated = await api.upsertModel(modelKey, payload);
      onSaved(updated);
      setApiKey("");
      setApiKeyTouched(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`删除模型 ${modelKey}？该操作不可撤销。`)) return;
    try {
      const updated = await api.deleteModel(modelKey);
      onSaved(updated);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="bg-bg-panel rounded-lg p-4 border border-gray-800 space-y-3 text-sm">
      <div className="flex items-center gap-2">
        <KeyRound size={14} className="text-gray-500 shrink-0" />
        <span className="font-medium text-gray-100">{modelKey}</span>
        {isDefault ? (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/20 text-accent">default</span>
        ) : null}
        <span className={`ml-auto text-xs ${SOURCE_TONE[keySource]}`}>
          {model.resolved_api_key_present ? "已解析到 api_key" : "未解析到 api_key"}
          <span className="text-gray-500"> · 来源 {SOURCE_LABELS[keySource]}</span>
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500">provider</label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as Provider)}
            className="w-full mt-1 bg-bg-base rounded px-3 py-1.5 text-sm border border-gray-700 focus:outline-none focus:border-accent"
          >
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500">model</label>
          <input
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            placeholder="claude-sonnet-4-5 / gpt-4o / xfyun-x1 ..."
            className="w-full mt-1 bg-bg-base rounded px-3 py-1.5 text-sm border border-gray-700 focus:outline-none focus:border-accent"
          />
        </div>
      </div>

      <div>
        <label className="text-xs text-gray-500 flex items-center gap-2">
          base_url
          <span className={`text-[10px] ${SOURCE_TONE[baseSource]}`}>
            {model.resolved_base_url
              ? `当前生效：${model.resolved_base_url} · ${SOURCE_LABELS[baseSource]}`
              : `未设置 · ${SOURCE_LABELS[baseSource]}`}
          </span>
        </label>
        <input
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="留空则使用合并 settings 或环境变量；OpenAI 兼容网关写完整 base_url"
          className="w-full mt-1 bg-bg-base rounded px-3 py-1.5 text-sm border border-gray-700 focus:outline-none focus:border-accent font-mono"
        />
      </div>

      <div>
        <label className="text-xs text-gray-500">api_key</label>
        <div className="mt-1 flex gap-2">
          <input
            type={showKey ? "text" : "password"}
            value={apiKey}
            onChange={(e) => {
              setApiKey(e.target.value);
              setApiKeyTouched(true);
            }}
            placeholder={
              model.resolved_api_key_present
                ? `已从${SOURCE_LABELS[keySource]}解析到 key（留空保持，输入则覆盖）`
                : "粘贴 sk-... / sk-ant-... 等密钥"
            }
            className="flex-1 bg-bg-base rounded px-3 py-1.5 text-sm border border-gray-700 focus:outline-none focus:border-accent font-mono"
          />
          <button
            type="button"
            onClick={() => setShowKey((v) => !v)}
            className="px-2 rounded border border-gray-700 text-gray-400 hover:text-gray-200"
            title={showKey ? "隐藏" : "显示"}
          >
            {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
        {apiKeyTouched ? (
          <p className="text-[11px] text-gray-500 mt-1">
            保存后该 key 将固化到本配置；留空字符串保存可清空回退到合并 settings 与环境变量。
          </p>
        ) : null}
      </div>

      {err ? <p className="text-xs text-red-400 whitespace-pre-wrap">{err}</p> : null}

      <div className="flex items-center gap-2 pt-1">
        <button
          type="button"
          disabled={!dirty || saving}
          onClick={() => void handleSave()}
          className="flex items-center gap-1 px-3 py-1.5 rounded text-xs bg-accent/20 text-accent hover:bg-accent/30 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Save size={13} /> {saving ? "保存中…" : "保存"}
        </button>
        {!isDefault ? (
          <button
            type="button"
            onClick={() => void handleDelete()}
            className="flex items-center gap-1 px-3 py-1.5 rounded text-xs text-red-400 hover:bg-red-500/10"
          >
            <Trash2 size={13} /> 删除
          </button>
        ) : null}
      </div>
    </div>
  );
}
