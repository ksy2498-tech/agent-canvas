import { Plus } from 'lucide-react';
import { useState } from 'react';
import { useGraphStore } from '../../../store/graphStore';

const knownKeys = ['query', 'current_output', 'metadata', 'nlp_result'];

export default function BreakpointSettings({ nodeId }) {
  const [customKey, setCustomKey] = useState('');
  const { breakpoints, toggleBreakpointOnNode, setBreakpointConfig } = useGraphStore();
  const config = breakpoints[nodeId];
  const enabled = Boolean(config);
  const current = config || { mode: 'inspect', editableKeys: [] };
  const setConfig = (patch) => setBreakpointConfig(nodeId, { ...current, ...patch });

  return (
    <section className="mt-5 border-t border-slate-200 pt-4 dark:border-slate-700">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h4 className="text-xs font-semibold">Breakpoint</h4>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">Pause execution when this node is reached.</p>
        </div>
        <label className="relative inline-flex cursor-pointer items-center">
          <input
            type="checkbox"
            className="peer sr-only"
            checked={enabled}
            onChange={() => toggleBreakpointOnNode(nodeId)}
          />
          <span className="h-5 w-9 rounded-full bg-slate-300 after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-white after:transition peer-checked:bg-red-500 peer-checked:after:translate-x-4" />
        </label>
      </div>

      {enabled ? (
        <div className="space-y-3 rounded-md border border-red-200 bg-red-50/60 p-3 dark:border-red-900 dark:bg-red-950/20">
          <label className="block space-y-1 text-xs">
            <span className="font-medium text-slate-700 dark:text-slate-200">Mode</span>
            <select
              className="field"
              value={current.mode}
              onChange={(event) => setConfig({ mode: event.target.value })}
            >
              <option value="inspect">pause and inspect</option>
              <option value="edit">pause and edit</option>
            </select>
          </label>

          {current.mode === 'edit' ? (
            <div className="space-y-2">
              <span className="text-xs font-medium text-slate-700 dark:text-slate-200">Editable state keys</span>
              {knownKeys.map((key) => (
                <label key={key} className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={current.editableKeys.includes(key)}
                    onChange={(event) =>
                      setConfig({
                        editableKeys: event.target.checked
                          ? [...current.editableKeys, key]
                          : current.editableKeys.filter((item) => item !== key),
                      })
                    }
                  />
                  {key}
                </label>
              ))}
              <div className="flex gap-2">
                <input
                  className="field"
                  value={customKey}
                  onChange={(event) => setCustomKey(event.target.value)}
                  placeholder="Custom key"
                />
                <button
                  className="icon-btn"
                  onClick={() => {
                    if (customKey.trim()) {
                      setConfig({ editableKeys: [...new Set([...current.editableKeys, customKey.trim()])] });
                    }
                    setCustomKey('');
                  }}
                  title="Add editable key"
                >
                  <Plus size={15} />
                </button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
