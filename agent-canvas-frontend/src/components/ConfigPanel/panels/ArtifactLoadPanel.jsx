import { BaseFields, Field, SelectInput, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function ArtifactLoadPanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, backend: 'Local', key: 'artifact', targetScope: 'state', outputKey: 'current_output', ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}>
    <Field label="Storage backend"><SelectInput value={data.backend} onChange={(backend) => setData({ backend })} options={['Local', 'S3']} /></Field>
    <Field label="Artifact key"><TextInput value={data.key} onChange={(key) => setData({ key })} placeholder="artifact" /></Field>
    <Field label="Artifact id state key"><TextInput value={data.artifactIdKey} onChange={(artifactIdKey) => setData({ artifactIdKey })} placeholder="optional, e.g. artifacts.current_id" /></Field>
    <Field label="Target scope"><SelectInput value={data.targetScope} onChange={(targetScope) => setData({ targetScope })} options={['state', 'runtime']} /></Field>
    <Field label="Output key"><TextInput value={data.outputKey} onChange={(outputKey) => setData({ outputKey })} placeholder={data.targetScope === 'runtime' ? 'loaded_artifact' : 'current_output'} /></Field>
    {data.backend === 'S3' ? <><Field label="Bucket"><TextInput value={data.bucket} onChange={(bucket) => setData({ bucket })} /></Field><Field label="Region"><TextInput value={data.region} onChange={(region) => setData({ region })} /></Field><Field label="Access key"><TextInput value={data.accessKey} onChange={(accessKey) => setData({ accessKey })} /></Field><Field label="Secret key"><TextInput type="password" value={data.secretKey} onChange={(secretKey) => setData({ secretKey })} /></Field></> : null}
  </BaseFields>;
}
