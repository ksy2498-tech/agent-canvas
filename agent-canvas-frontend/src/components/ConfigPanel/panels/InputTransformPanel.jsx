import { BaseFields, EditorField, Field, transformTemplate } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function InputTransformPanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, code: transformTemplate, ...node.data };
  return <BaseFields data={data} setData={(patch) => updateNodeData(node.id, patch)} mcpModes={['manual', 'tool-only']}><Field label="Transform code"><EditorField value={data.code} onChange={(code) => updateNodeData(node.id, { code })} language="python" height={200} /></Field></BaseFields>;
}
