import { Plus, Trash2 } from 'lucide-react';
import { BaseFields, Field, SelectInput, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';

const providers = ['OpenAI', 'Gemini', 'Claude', 'Custom'];
const defaultModels = {
  OpenAI: 'gpt-4o-mini',
  Custom: 'gpt-4o-mini',
  Gemini: 'gemini-1.5-flash',
  Claude: 'claude-3-5-haiku-latest',
};

export default function RouterNodePanel({ node }) {
  const updateNodeData = useGraphStore((state) => state.updateNodeData);
  const data = { id: node.id, routingMode: 'llm-based', provider: 'OpenAI', conditions: [], ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  const provider = data.provider || 'OpenAI';
  const setProvider = (nextProvider) =>
    setData({
      provider: nextProvider,
      model: data.model || defaultModels[nextProvider],
      baseUrl: nextProvider === 'Custom' ? data.baseUrl : '',
    });
  return <BaseFields data={data} setData={setData} mcpModes={['auto', 'tool-only']}>
    <Field label="Routing Mode"><SelectInput value={data.routingMode} onChange={(routingMode) => setData({ routingMode })} options={['llm-based', 'keyword-match']} /></Field>
    {data.routingMode === 'llm-based' ? <>
      <Field label="Provider"><SelectInput value={provider} onChange={setProvider} options={providers} /></Field>
      {provider === 'Custom' ? <Field label="Base URL"><TextInput value={data.baseUrl} onChange={(baseUrl) => setData({ baseUrl })} placeholder="https://api.example.com/v1" /></Field> : null}
      <Field label="API Key"><TextInput type="password" value={data.apiKey} onChange={(apiKey) => setData({ apiKey })} /></Field>
      <Field label="Model"><TextInput value={data.model || defaultModels[provider]} onChange={(model) => setData({ model })} /></Field>
    </> : null}
    <div className="space-y-2"><span className="text-xs font-medium">Conditions</span>{data.conditions.map((row, i) => <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2"><input className="field" value={row.condition || ''} onChange={(e) => setData({ conditions: data.conditions.map((r, idx) => idx === i ? { ...r, condition: e.target.value } : r) })} placeholder="Condition" /><input className="field" value={row.route || ''} onChange={(e) => setData({ conditions: data.conditions.map((r, idx) => idx === i ? { ...r, route: e.target.value } : r) })} placeholder="Route" /><button className="icon-btn" onClick={() => setData({ conditions: data.conditions.filter((_, idx) => idx !== i) })}><Trash2 size={15} /></button></div>)}<button className="secondary-btn w-full" onClick={() => setData({ conditions: [...data.conditions, { condition: '', route: '' }] })}><Plus size={15} /> Add condition</button></div>
    <Field label="Default route"><TextInput value={data.defaultRoute} onChange={(defaultRoute) => setData({ defaultRoute })} /></Field>
  </BaseFields>;
}
