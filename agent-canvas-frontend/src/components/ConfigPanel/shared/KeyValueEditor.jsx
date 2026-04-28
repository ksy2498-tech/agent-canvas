import { Plus, Trash2 } from 'lucide-react';

export default function KeyValueEditor({ value = [], onChange, typed = false }) {
  const rows = Array.isArray(value)
    ? value
    : Object.entries(value || {}).map(([key, val]) => ({ key, value: String(val), type: 'string' }));
  const update = (index, patch) => onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  const remove = (index) => onChange(rows.filter((_, i) => i !== index));
  return (
    <div className="space-y-2">
      {rows.map((row, index) => (
        <div key={index} className="grid grid-cols-[1fr_1fr_auto] gap-2">
          <input className="field" placeholder="Key" value={row.key || ''} onChange={(e) => update(index, { key: e.target.value })} />
          <input className="field" placeholder="Value" value={row.value || ''} onChange={(e) => update(index, { value: e.target.value })} />
          <button className="icon-btn" onClick={() => remove(index)} title="Remove">
            <Trash2 size={15} />
          </button>
          {typed ? (
            <select className="field col-span-2" value={row.type || 'string'} onChange={(e) => update(index, { type: e.target.value })}>
              <option>string</option>
              <option>number</option>
              <option>bool</option>
              <option>json</option>
            </select>
          ) : null}
        </div>
      ))}
      <button className="secondary-btn w-full" onClick={() => onChange([...rows, { key: '', value: '', type: 'string' }])}>
        <Plus size={15} /> Add row
      </button>
    </div>
  );
}
