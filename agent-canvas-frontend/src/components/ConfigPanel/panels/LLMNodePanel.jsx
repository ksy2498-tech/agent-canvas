import { BaseFields, Field, KeyValueField, SelectInput, Textarea, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';

const providers = ['OpenAI', 'Gemini', 'Claude', 'Custom'];
const toolHandlingModes = ['bind-tools', 'prompt-only'];
const defaultModels = {
  OpenAI: 'gpt-4o-mini',
  Custom: 'gpt-4o-mini',
  Gemini: 'gemini-1.5-flash',
  Claude: 'claude-3-5-haiku-latest',
};

function Switch({ checked, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition ${checked ? 'bg-blue-500' : 'bg-slate-300 dark:bg-slate-600'}`}
    >
      <span
        className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5' : 'translate-x-1'}`}
      />
    </button>
  );
}

export default function LLMNodePanel({ node }) {
  const updateNodeData = useGraphStore((state) => state.updateNodeData);
  const data = {
    id: node.id,
    provider: 'OpenAI',
    temperature: 0.7,
    outputKey: 'current_output',
    toolResultKey: 'current_output',
    toolHandlingMode: 'bind-tools',
    useTools: false,
    updateCurrentOutput: true,
    ...node.data,
  };
  const setData = (patch) => updateNodeData(node.id, patch);
  const provider = data.provider || 'OpenAI';
  const useTools = Boolean(data.useTools);
  const toolHandlingMode = data.toolHandlingMode || 'bind-tools';
  const showToolResultFields = useTools && toolHandlingMode !== 'prompt-only';
  const setProvider = (nextProvider) =>
    setData({
      provider: nextProvider,
      model: data.model || defaultModels[nextProvider],
      baseUrl: nextProvider === 'Custom' ? data.baseUrl : '',
    });
  return (
    <BaseFields data={data} setData={setData} mcpModes={useTools ? ['auto', 'tool-only'] : null}>
      <Field label="Provider"><SelectInput value={provider} onChange={setProvider} options={providers} /></Field>
      {provider === 'Custom' ? <Field label="Base URL"><TextInput value={data.baseUrl} onChange={(baseUrl) => setData({ baseUrl })} placeholder="https://api.example.com/v1" /></Field> : null}
      <Field label="API Key"><TextInput type="password" value={data.apiKey} onChange={(apiKey) => setData({ apiKey })} /></Field>
      <Field label="Model"><TextInput value={data.model || defaultModels[provider]} onChange={(model) => setData({ model })} /></Field>
      {provider === 'Custom' ? <Field label="Custom Headers"><KeyValueField value={data.headers} onChange={(headers) => setData({ headers })} /></Field> : null}
      <div className="flex items-center justify-between rounded-lg border border-slate-200 p-3 dark:border-slate-700">
        <div>
          <div className="text-xs font-medium text-slate-700 dark:text-slate-200">Use tools</div>
          <div className="text-xs text-slate-500">Enable MCP tools for this LLM call.</div>
        </div>
        <Switch checked={useTools} onChange={(nextUseTools) => setData({ useTools: nextUseTools })} />
      </div>
      {useTools ? <Field label="Tool handling mode"><SelectInput value={toolHandlingMode} onChange={(nextToolHandlingMode) => setData({ toolHandlingMode: nextToolHandlingMode })} options={toolHandlingModes} /></Field> : null}
      <Field label="System Prompt"><Textarea rows={6} value={data.systemPrompt} onChange={(systemPrompt) => setData({ systemPrompt })} /></Field>
      <Field label="Output key"><TextInput value={data.outputKey} onChange={(outputKey) => setData({ outputKey })} placeholder="current_output or selected_tool" /></Field>
      {useTools ? <Field label="Tool name state key"><TextInput value={data.toolNameKey} onChange={(toolNameKey) => setData({ toolNameKey })} placeholder="selected_tool" /></Field> : null}
      {useTools ? <Field label="Tool args state key"><TextInput value={data.toolArgsKey} onChange={(toolArgsKey) => setData({ toolArgsKey })} placeholder="tool_args" /></Field> : null}
      {showToolResultFields ? <Field label="Tool result key"><TextInput value={data.toolResultKey} onChange={(toolResultKey) => setData({ toolResultKey })} placeholder="tool_result" /></Field> : null}
      {showToolResultFields ? <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={Boolean(data.updateCurrentOutput)} onChange={(e) => setData({ updateCurrentOutput: e.target.checked })} />
        Also update current_output
      </label> : null}
      <Field label={`Temperature ${data.temperature}`}><input className="w-full" type="range" min="0" max="2" step="0.1" value={data.temperature} onChange={(e) => setData({ temperature: Number(e.target.value) })} /></Field>
      <p className="text-xs text-slate-500">Turn on tools only when this LLM should use or select MCP tools. bind-tools uses native model tool calling; prompt-only selects a tool and args for a following MCP Tool Call node.</p>
    </BaseFields>
  );
}
