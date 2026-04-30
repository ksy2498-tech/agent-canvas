import { BaseFields, Field, SelectInput, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';

const sections = ['scratch', 'tool_results', 'session', 'nlp', 'artifacts'];
const sourceScopes = ['literal', 'state', 'runtime'];
const valueTypes = ['string', 'number', 'bool', 'json'];

export default function RuntimeSetPanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = {
    id: node.id,
    section: 'scratch',
    key: 'value',
    sourceScope: 'literal',
    sourceKey: '',
    value: '',
    valueType: 'string',
    ...node.data,
  };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}>
    <Field label="Runtime section"><SelectInput value={data.section} onChange={(section) => setData({ section })} options={sections} /></Field>
    <Field label="Runtime key"><TextInput value={data.key} onChange={(key) => setData({ key })} placeholder="value" /></Field>
    <Field label="Source scope"><SelectInput value={data.sourceScope} onChange={(sourceScope) => setData({ sourceScope })} options={sourceScopes} /></Field>
    {data.sourceScope === 'literal' ? <>
      <Field label="Value type"><SelectInput value={data.valueType} onChange={(valueType) => setData({ valueType })} options={valueTypes} /></Field>
      <Field label="Value"><TextInput value={data.value} onChange={(value) => setData({ value })} placeholder={data.valueType === 'json' ? '{"a": 1}' : 'literal value'} /></Field>
    </> : <Field label="Source key"><TextInput value={data.sourceKey} onChange={(sourceKey) => setData({ sourceKey })} placeholder={data.sourceScope === 'runtime' ? 'tool_results.tool_result' : 'current_output'} /></Field>}
    <p className="text-xs text-slate-500">Stores a value in runtime without adding raw data to public state.</p>
  </BaseFields>;
}
