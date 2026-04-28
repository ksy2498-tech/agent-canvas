import { BaseFields, Field, KeyValueField } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function StateSetPanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, values: [], ...node.data };
  return <BaseFields data={data} setData={(patch) => updateNodeData(node.id, patch)}><Field label="Key-value pairs"><KeyValueField typed value={data.values} onChange={(values) => updateNodeData(node.id, { values })} /></Field></BaseFields>;
}
