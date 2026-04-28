import { BaseFields, Field, SelectInput, TextInput, useDbAliases } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function SessionLoadPanel({ node }) {
  const aliases = useDbAliases();
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, outputKey: 'messages', ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}><Field label="Session Store"><SelectInput value={data.sessionStore} onChange={(sessionStore) => setData({ sessionStore })} options={[...aliases, 'Redis']} /></Field><Field label="Session ID expression"><TextInput value={data.sessionIdExpression} onChange={(sessionIdExpression) => setData({ sessionIdExpression })} placeholder='state["session_id"]' /></Field><Field label="Output key"><TextInput value={data.outputKey} onChange={(outputKey) => setData({ outputKey })} /></Field></BaseFields>;
}
