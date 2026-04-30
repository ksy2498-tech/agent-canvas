import { BaseFields, Field, SelectInput, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function ArtifactStorePanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, backend: 'Local', key: 'artifact', sourceScope: 'state', stateKey: 'current_output', outputKey: 'artifacts.current_id', cleanupSource: false, cleanupValue: null, ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}>
    <Field label="Storage backend"><SelectInput value={data.backend} onChange={(backend) => setData({ backend })} options={['Local', 'S3']} /></Field>
    <Field label="Artifact key"><TextInput value={data.key} onChange={(key) => setData({ key })} placeholder="artifact" /></Field>
    <Field label="Source scope"><SelectInput value={data.sourceScope} onChange={(sourceScope) => setData({ sourceScope })} options={['state', 'runtime']} /></Field>
    <Field label="Source key"><TextInput value={data.stateKey} onChange={(stateKey) => setData({ stateKey })} placeholder={data.sourceScope === 'runtime' ? 'tool_results.tool_result or nlp.nlp_result' : 'current_output or node_results.tool_result'} /></Field>
    <Field label="Output artifact id key"><TextInput value={data.outputKey} onChange={(outputKey) => setData({ outputKey })} placeholder="artifacts.current_id" /></Field>
    <label className="flex items-start gap-2 rounded-md border border-slate-200 p-3 text-xs dark:border-slate-700">
      <input type="checkbox" checked={Boolean(data.cleanupSource)} onChange={(event) => setData({ cleanupSource: event.target.checked })} />
      <span><span className="block font-medium text-slate-700 dark:text-slate-200">Cleanup source after store</span><span className="text-slate-500">Store the value as an artifact, then replace the source value.</span></span>
    </label>
    {data.cleanupSource ? <Field label="Cleanup value"><TextInput value={data.cleanupValue === null || data.cleanupValue === undefined ? '' : String(data.cleanupValue)} onChange={(cleanupValue) => setData({ cleanupValue: cleanupValue || null })} placeholder="empty = null" /></Field> : null}
    {data.backend === 'S3' ? <S3Fields data={data} setData={setData} /> : null}
  </BaseFields>;
}
function S3Fields({ data, setData }) { return <><Field label="Bucket"><TextInput value={data.bucket} onChange={(bucket) => setData({ bucket })} /></Field><Field label="Region"><TextInput value={data.region} onChange={(region) => setData({ region })} /></Field><Field label="Access key"><TextInput value={data.accessKey} onChange={(accessKey) => setData({ accessKey })} /></Field><Field label="Secret key"><TextInput type="password" value={data.secretKey} onChange={(secretKey) => setData({ secretKey })} /></Field></>; }
