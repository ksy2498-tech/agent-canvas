import { BaseFields, Field, SelectInput, TextInput, useDbAliases } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
const keys = ['query', 'messages', 'current_output', 'node_results', 'metadata', 'nlp_result'];
export default function SessionSavePanel({ node }) {
  const aliases = useDbAliases();
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, sessionStore: 'Local SQLite', path: './sessions.db', sessionIdExpression: 'state["query"]', keysToSave: ['messages', 'node_results'], mode: 'overwrite', ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  const stores = ['Local SQLite', ...aliases];
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}><Field label="Session Store"><SelectInput value={data.sessionStore} onChange={(sessionStore) => setData({ sessionStore })} options={stores} /></Field>{data.sessionStore === 'Local SQLite' ? <Field label="SQLite path"><TextInput value={data.path} onChange={(path) => setData({ path })} /></Field> : null}<Field label="Session ID expression"><TextInput value={data.sessionIdExpression} onChange={(sessionIdExpression) => setData({ sessionIdExpression })} placeholder='state["session_id"] or state["query"]' /></Field><div className="space-y-2"><span className="text-xs font-medium">Keys to save</span>{keys.map((key) => <label key={key} className="flex items-center gap-2 text-xs"><input type="checkbox" checked={data.keysToSave.includes(key)} onChange={(e) => setData({ keysToSave: e.target.checked ? [...data.keysToSave, key] : data.keysToSave.filter((item) => item !== key) })} />{key}</label>)}</div><Field label="Mode"><SelectInput value={data.mode} onChange={(mode) => setData({ mode })} options={['overwrite', 'append']} /></Field></BaseFields>;
}
