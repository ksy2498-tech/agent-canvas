import MCPToolsSection from '../shared/MCPToolsSection';
import KeyValueEditor from '../shared/KeyValueEditor';
import CodeEditor from '../shared/CodeEditor';
import { useGraphStore } from '../../../store/graphStore';
import { testDBConnection } from '../../../api/client';
import toast from 'react-hot-toast';

export const codeTemplate = `# state: dict - current agent state
# mcp: dict - attached MCP tools, call via mcp["server_name"]["tool_name"](args)
# Must return dict to merge into state

def run(state, mcp):
    return {"current_output": state.get("query", "")}
`;

export const transformTemplate = `def transform(state, mcp):
   return {"transformed": state["current_output"]}
`;

export function Field({ label, children }) {
  return (
    <label className="block space-y-1 text-xs">
      <span className="font-medium text-slate-700 dark:text-slate-200">{label}</span>
      {children}
    </label>
  );
}

export function TextInput({ value, onChange, type = 'text', placeholder }) {
  return <input className="field" type={type} value={value || ''} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />;
}

export function SelectInput({ value, onChange, options }) {
  return (
    <select className="field" value={value || options[0]} onChange={(e) => onChange(e.target.value)}>
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </select>
  );
}

export function Textarea({ value, onChange, rows = 4, placeholder }) {
  return <textarea className="field resize-y" rows={rows} value={value || ''} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />;
}

export function BaseFields({ data, setData, children, mcpModes }) {
  return (
    <div className="space-y-4">
      <Field label="Label">
        <TextInput value={data.label} onChange={(label) => setData({ label })} />
      </Field>
      {children}
      {mcpModes ? <MCPToolsSection nodeId={data.id} executionModes={mcpModes} /> : null}
    </div>
  );
}

export function LabelOnlyPanel({ node, includeMcp = false }) {
  const updateNodeData = useGraphStore((state) => state.updateNodeData);
  return (
    <BaseFields data={{ id: node.id, ...node.data }} setData={(patch) => updateNodeData(node.id, patch)} mcpModes={includeMcp ? ['tool-only'] : null} />
  );
}

export function KeyValueField({ value, onChange, typed = false }) {
  return <KeyValueEditor value={value || []} onChange={onChange} typed={typed} />;
}

export function EditorField({ value, onChange, language, height }) {
  return <CodeEditor value={value} onChange={onChange} language={language} height={height} />;
}

export function useDbAliases() {
  return useGraphStore((state) =>
    state.nodes.filter((node) => node.type === 'dbConnection').map((node) => node.data?.alias).filter(Boolean),
  );
}

export async function testDb(data) {
  try {
    await testDBConnection(data.connectionString, data.dbType);
    toast.success('DB connection succeeded');
  } catch (error) {
    toast.error('DB connection failed');
  }
}
