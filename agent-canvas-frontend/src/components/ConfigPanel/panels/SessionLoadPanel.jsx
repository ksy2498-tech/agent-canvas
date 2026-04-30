import { BaseFields, Field, SelectInput, TextInput, useDbAliases } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function SessionLoadPanel({ node }) {
  const aliases = useDbAliases();
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, sessionStore: 'Local SQLite', path: './sessions.db', sessionIdExpression: 'state["query"]', target: 'runtime', outputKey: 'session', ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  const stores = ['Local SQLite', ...aliases];
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}>
    <Field label="Session Store"><SelectInput value={data.sessionStore} onChange={(sessionStore) => setData({ sessionStore })} options={stores} /></Field>
    {data.sessionStore === 'Local SQLite' ? <Field label="SQLite path"><TextInput value={data.path} onChange={(path) => setData({ path })} /></Field> : null}
    <Field label="Session ID expression"><TextInput value={data.sessionIdExpression} onChange={(sessionIdExpression) => setData({ sessionIdExpression })} placeholder='state["session_id"] or state["query"]' /></Field>
    <Field label="Target"><SelectInput value={data.target} onChange={(target) => setData({ target })} options={['runtime', 'state', 'both']} /></Field>
    <Field label="Output key"><TextInput value={data.outputKey} onChange={(outputKey) => setData({ outputKey })} placeholder="session or metadata.session_summary" /></Field>
    <p className="text-xs text-slate-500">runtime keeps the loaded session out of public state. state/both writes a lightweight summary to metadata by default.</p>
  </BaseFields>;
}
