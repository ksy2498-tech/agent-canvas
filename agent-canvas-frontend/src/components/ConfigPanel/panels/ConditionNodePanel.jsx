import { BaseFields, Field, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function ConditionNodePanel({ node }) {
  const updateNodeData = useGraphStore((state) => state.updateNodeData);
  const data = { id: node.id, ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData}><Field label="Condition expression"><TextInput value={data.expression} onChange={(expression) => setData({ expression })} placeholder='state["score"] > 0.5' /></Field><Field label="True route label"><TextInput value={data.trueRoute} onChange={(trueRoute) => setData({ trueRoute })} /></Field><Field label="False route label"><TextInput value={data.falseRoute} onChange={(falseRoute) => setData({ falseRoute })} /></Field></BaseFields>;
}
