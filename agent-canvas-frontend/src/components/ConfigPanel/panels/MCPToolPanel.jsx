import { BaseFields, Field, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';

export default function MCPToolPanel({ node }) {
  const updateNodeData = useGraphStore((state) => state.updateNodeData);
  const data = {
    id: node.id,
    toolNameKey: 'selected_tool',
    toolArgsKey: 'tool_args',
    toolResultKey: 'tool_result',
    updateCurrentOutput: true,
    ...node.data,
  };
  const setData = (patch) => updateNodeData(node.id, patch);

  return (
    <BaseFields data={data} setData={setData} mcpModes={['tool-only']}>
      <Field label="Tool name state key"><TextInput value={data.toolNameKey} onChange={(toolNameKey) => setData({ toolNameKey })} placeholder="selected_tool" /></Field>
      <Field label="Tool args state key"><TextInput value={data.toolArgsKey} onChange={(toolArgsKey) => setData({ toolArgsKey })} placeholder="tool_args" /></Field>
      <Field label="Tool result key"><TextInput value={data.toolResultKey} onChange={(toolResultKey) => setData({ toolResultKey })} placeholder="tool_result" /></Field>
      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={Boolean(data.updateCurrentOutput)} onChange={(e) => setData({ updateCurrentOutput: e.target.checked })} />
        Also update current_output
      </label>
      <p className="text-xs text-slate-500">Attach one or more MCP tools below. If Tool name state key is set, this node calls the matching attached tool; otherwise it calls the first attached tool.</p>
    </BaseFields>
  );
}
