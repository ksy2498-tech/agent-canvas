import { BaseFields, Field, SelectInput, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';

const sections = ['scratch', 'tool_results', 'session', 'nlp', 'artifacts'];
const targetScopes = ['state', 'runtime'];

export default function RuntimeGetPanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = {
    id: node.id,
    section: 'scratch',
    key: 'value',
    targetScope: 'state',
    targetSection: 'scratch',
    outputKey: 'current_output',
    ...node.data,
  };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}>
    <Field label="Runtime section"><SelectInput value={data.section} onChange={(section) => setData({ section })} options={sections} /></Field>
    <Field label="Runtime key"><TextInput value={data.key} onChange={(key) => setData({ key })} placeholder="value" /></Field>
    <Field label="Target scope"><SelectInput value={data.targetScope} onChange={(targetScope) => setData({ targetScope })} options={targetScopes} /></Field>
    {data.targetScope === 'runtime' ? <Field label="Target runtime section"><SelectInput value={data.targetSection} onChange={(targetSection) => setData({ targetSection })} options={sections} /></Field> : null}
    <Field label="Output key"><TextInput value={data.outputKey} onChange={(outputKey) => setData({ outputKey })} placeholder={data.targetScope === 'runtime' ? 'copied_value' : 'current_output'} /></Field>
    <p className="text-xs text-slate-500">Reads a value from runtime and writes it to state or another runtime section.</p>
  </BaseFields>;
}
