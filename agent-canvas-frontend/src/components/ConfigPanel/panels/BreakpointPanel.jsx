import { useState } from 'react';
import { Plus } from 'lucide-react';
import { BaseFields, Field, SelectInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';

const knownKeys = ['query', 'current_output', 'metadata', 'nlp_result'];

export default function BreakpointPanel({ node }) {
  const { updateNodeData, breakpoints, setBreakpointConfig } = useGraphStore();
  const config = breakpoints[node.id] || { mode: 'inspect', editableKeys: [] };
  const [customKey, setCustomKey] = useState('');
  const setConfig = (patch) => setBreakpointConfig(node.id, { ...config, ...patch });
  return (
    <BaseFields data={{ id: node.id, ...node.data }} setData={(patch) => updateNodeData(node.id, patch)}>
      <Field label="Mode">
        <SelectInput value={config.mode === 'edit' ? 'pause and edit' : 'pause and inspect'} onChange={(value) => setConfig({ mode: value.includes('edit') ? 'edit' : 'inspect' })} options={['pause and inspect', 'pause and edit']} />
      </Field>
      {config.mode === 'edit' ? (
        <div className="space-y-2">
          {knownKeys.map((key) => (
            <label key={key} className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={config.editableKeys.includes(key)}
                onChange={(event) =>
                  setConfig({
                    editableKeys: event.target.checked
                      ? [...config.editableKeys, key]
                      : config.editableKeys.filter((item) => item !== key),
                  })
                }
              />
              {key}
            </label>
          ))}
          <div className="flex gap-2">
            <input className="field" value={customKey} onChange={(e) => setCustomKey(e.target.value)} placeholder="Custom key" />
            <button
              className="icon-btn"
              onClick={() => {
                if (customKey) setConfig({ editableKeys: [...new Set([...config.editableKeys, customKey])] });
                setCustomKey('');
              }}
            >
              <Plus size={16} />
            </button>
          </div>
        </div>
      ) : null}
      <p className="rounded-md bg-yellow-50 p-3 text-xs text-yellow-800 dark:bg-yellow-950/30 dark:text-yellow-200">
        Breakpoints can also be added to edges via right-click
      </p>
    </BaseFields>
  );
}
