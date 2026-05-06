import { BaseFields, EditorField, Field, TextInput, codeTemplate, listToText, textToList } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function CodeNodePanel({ node }) {
  const updateNodeData = useGraphStore((state) => state.updateNodeData);
  const data = { id: node.id, code: codeTemplate, ...node.data };
  return (
    <BaseFields data={data} setData={(patch) => updateNodeData(node.id, patch)} mcpModes={['manual', 'tool-only']}>
      <Field label="Python Code">
        <EditorField value={data.code} onChange={(code) => updateNodeData(node.id, { code })} language="python" height={300} />
      </Field>
      <Field label="Output state keys">
        <TextInput
          value={listToText(data.declared_output_keys || data.declaredOutputKeys)}
          onChange={(value) => updateNodeData(node.id, { declared_output_keys: textToList(value) })}
          placeholder="lot_id, status, result.items"
        />
      </Field>
    </BaseFields>
  );
}
