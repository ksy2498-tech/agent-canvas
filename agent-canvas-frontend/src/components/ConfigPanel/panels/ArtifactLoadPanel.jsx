import { BaseFields, Field, SelectInput, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function ArtifactLoadPanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, backend: 'Local', ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}><Field label="Storage backend"><SelectInput value={data.backend} onChange={(backend) => setData({ backend })} options={['Local', 'S3']} /></Field><Field label="Key expression"><TextInput value={data.keyExpression} onChange={(keyExpression) => setData({ keyExpression })} /></Field><Field label="Output key"><TextInput value={data.outputKey} onChange={(outputKey) => setData({ outputKey })} /></Field>{data.backend === 'S3' ? <><Field label="Bucket"><TextInput value={data.bucket} onChange={(bucket) => setData({ bucket })} /></Field><Field label="Region"><TextInput value={data.region} onChange={(region) => setData({ region })} /></Field><Field label="Access key"><TextInput value={data.accessKey} onChange={(accessKey) => setData({ accessKey })} /></Field><Field label="Secret key"><TextInput type="password" value={data.secretKey} onChange={(secretKey) => setData({ secretKey })} /></Field></> : null}</BaseFields>;
}
