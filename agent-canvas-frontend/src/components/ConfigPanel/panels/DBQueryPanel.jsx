import { BaseFields, EditorField, Field, KeyValueField, SelectInput, TextInput, useDbAliases } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function DBQueryPanel({ node }) {
  const aliases = useDbAliases();
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, queryType: 'SQL', query: '', params: [], ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}><Field label="Connection alias"><SelectInput value={data.connectionAlias} onChange={(connectionAlias) => setData({ connectionAlias })} options={aliases.length ? aliases : ['']} /></Field><Field label="Query type"><SelectInput value={data.queryType} onChange={(queryType) => setData({ queryType })} options={['SQL', 'Redis Command']} /></Field><Field label="Query editor"><EditorField value={data.query} onChange={(query) => setData({ query })} language="sql" height={220} /></Field><Field label="Params"><KeyValueField value={data.params} onChange={(params) => setData({ params })} /></Field><Field label="Output key"><TextInput value={data.outputKey} onChange={(outputKey) => setData({ outputKey })} /></Field></BaseFields>;
}
