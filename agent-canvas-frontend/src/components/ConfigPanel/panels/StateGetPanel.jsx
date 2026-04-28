import { BaseFields, Field, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function StateGetPanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData}><Field label="Key to read"><TextInput value={data.key} onChange={(key) => setData({ key })} /></Field><Field label="Output alias"><TextInput value={data.outputAlias} onChange={(outputAlias) => setData({ outputAlias })} /></Field></BaseFields>;
}
