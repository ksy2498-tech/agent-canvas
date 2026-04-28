import { BaseFields, Field, KeyValueField, SelectInput, Textarea, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';

const providers = ['OpenAI', 'Gemini', 'Claude', 'Custom'];
const defaultModels = {
  OpenAI: 'gpt-4o-mini',
  Custom: 'gpt-4o-mini',
  Gemini: 'gemini-1.5-flash',
  Claude: 'claude-3-5-haiku-latest',
};

export default function LLMNodePanel({ node }) {
  const updateNodeData = useGraphStore((state) => state.updateNodeData);
  const data = { id: node.id, provider: 'OpenAI', temperature: 0.7, ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  const provider = data.provider || 'OpenAI';
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
      <Field label="System Prompt"><Textarea rows={6} value={data.systemPrompt} onChange={(systemPrompt) => setData({ systemPrompt })} /></Field>
      <Field label={`Temperature ${data.temperature}`}><input className="w-full" type="range" min="0" max="2" step="0.1" value={data.temperature} onChange={(e) => setData({ temperature: Number(e.target.value) })} /></Field>
      <p className="text-xs text-slate-500">auto means LLM decides when to call, tool-only skips LLM entirely</p>
    </BaseFields>
  );
}
