import { BaseFields, Field, SelectInput, Textarea } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function OutputFormatPanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, formatType: 'plain', ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}><Field label="Format type"><SelectInput value={data.formatType} onChange={(formatType) => setData({ formatType })} options={['plain', 'markdown', 'json', 'custom']} /></Field><Field label="Template"><Textarea value={data.template} onChange={(template) => setData({ template })} /></Field></BaseFields>;
}
