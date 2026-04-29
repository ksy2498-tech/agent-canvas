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

export default function LLMNodePanel({ node }) {
  const updateNodeData = useGraphStore((state) => state.updateNodeData);
  const data = {
    id: node.id,
    provider: 'OpenAI',
    temperature: 0.7,
    outputKey: 'current_output',
    toolResultKey: 'current_output',
    toolHandlingMode: 'bind-tools',
    updateCurrentOutput: true,
    ...node.data,
  };
  const setData = (patch) => updateNodeData(node.id, patch);
  const provider = data.provider || 'OpenAI';
  const toolHandlingMode = data.toolHandlingMode || 'bind-tools';
  const showToolResultFields = toolHandlingMode !== 'prompt-only';
  const setProvider = (nextProvider) =>
    setData({
      provider: nextProvider,
      model: data.model || defaultModels[nextProvider],
      baseUrl: nextProvider === 'Custom' ? data.baseUrl : '',
    });
  return (
    <BaseFields data={data} setData={setData} mcpModes={['auto', 'tool-only']}>
      <Field label="Provider"><SelectInput value={provider} onChange={setProvider} options={providers} /></Field>
      {provider === 'Custom' ? <Field label="Base URL"><TextInput value={data.baseUrl} onChange={(baseUrl) => setData({ baseUrl })} placeholder="https://api.example.com/v1" /></Field> : null}
      <Field label="API Key"><TextInput type="password" value={data.apiKey} onChange={(apiKey) => setData({ apiKey })} /></Field>
      <Field label="Model"><TextInput value={data.model || defaultModels[provider]} onChange={(model) => setData({ model })} /></Field>
      {provider === 'Custom' ? <Field label="Custom Headers"><KeyValueField value={data.headers} onChange={(headers) => setData({ headers })} /></Field> : null}
      <Field label="Tool handling mode"><SelectInput value={toolHandlingMode} onChange={(nextToolHandlingMode) => setData({ toolHandlingMode: nextToolHandlingMode })} options={toolHandlingModes} /></Field>
      <Field label="System Prompt"><Textarea rows={6} value={data.systemPrompt} onChange={(systemPrompt) => setData({ systemPrompt })} /></Field>
      <Field label="Output key"><TextInput value={data.outputKey} onChange={(outputKey) => setData({ outputKey })} placeholder="current_output or selected_tool" /></Field>
      <Field label="Tool name state key"><TextInput value={data.toolNameKey} onChange={(toolNameKey) => setData({ toolNameKey })} placeholder="selected_tool" /></Field>
      <Field label="Tool args state key"><TextInput value={data.toolArgsKey} onChange={(toolArgsKey) => setData({ toolArgsKey })} placeholder="tool_args" /></Field>
      {showToolResultFields ? <Field label="Tool result key"><TextInput value={data.toolResultKey} onChange={(toolResultKey) => setData({ toolResultKey })} placeholder="tool_result" /></Field> : null}
      {showToolResultFields ? <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={Boolean(data.updateCurrentOutput)} onChange={(e) => setData({ updateCurrentOutput: e.target.checked })} />
        Also update current_output
      </label> : null}
      <Field label={`Temperature ${data.temperature}`}><input className="w-full" type="range" min="0" max="2" step="0.1" value={data.temperature} onChange={(e) => setData({ temperature: Number(e.target.value) })} /></Field>
      <p className="text-xs text-slate-500">bind-tools uses native model tool calling. prompt-only selects a tool and args for a following MCP Tool Call node.</p>
    </BaseFields>
  );
}
