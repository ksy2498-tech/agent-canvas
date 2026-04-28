import { BaseFields, EditorField, Field, KeyValueField, SelectInput, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function HTTPRequestPanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, method: 'GET', headers: [], body: '{}', ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  const hasBody = ['POST', 'PUT', 'PATCH'].includes(data.method);
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}><Field label="Method"><SelectInput value={data.method} onChange={(method) => setData({ method })} options={['GET', 'POST', 'PUT', 'DELETE', 'PATCH']} /></Field><Field label="URL"><TextInput value={data.url} onChange={(url) => setData({ url })} placeholder="https://api.example.com/{state.id}" /></Field><Field label="Headers"><KeyValueField value={data.headers} onChange={(headers) => setData({ headers })} /></Field>{hasBody ? <Field label="Body"><EditorField value={data.body} onChange={(body) => setData({ body })} language="json" height={180} /></Field> : null}<Field label="Output key"><TextInput value={data.outputKey} onChange={(outputKey) => setData({ outputKey })} /></Field></BaseFields>;
}
