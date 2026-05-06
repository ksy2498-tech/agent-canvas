import { BaseFields, EditorField, Field, TextInput, listToText, textToList, transformTemplate } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function InputTransformPanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, code: transformTemplate, ...node.data };
  return (
    <BaseFields data={data} setData={(patch) => updateNodeData(node.id, patch)} mcpModes={['manual', 'tool-only']}>
      <Field label="Transform code">
        <EditorField value={data.code} onChange={(code) => updateNodeData(node.id, { code })} language="python" height={200} />
      </Field>
      <Field label="Output state keys">
        <TextInput
          value={listToText(data.declared_output_keys || data.declaredOutputKeys)}
          onChange={(value) => updateNodeData(node.id, { declared_output_keys: textToList(value) })}
          placeholder="transformed, result.items"
        />
      </Field>
    </BaseFields>
  );
}
