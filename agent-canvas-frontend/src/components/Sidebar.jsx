import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { nodeDefinitions } from './nodes/nodeFactory.jsx';

const groups = [
  ['Control', ['start', 'end']],
  ['LLM', ['llm']],
  ['MCP', ['mcpTool']],
  ['Logic', ['code', 'router', 'condition']],
  ['Session / State', ['sessionLoad', 'sessionSave', 'stateSet', 'stateGet']],
  ['Database', ['dbConnection', 'dbQuery']],
  ['Artifact', ['artifactStore', 'artifactLoad']],
  ['I/O', ['httpRequest', 'inputTransform', 'outputFormat']],
  ['NLP', ['nlp']],
];

export default function Sidebar() {
  const [open, setOpen] = useState(Object.fromEntries(groups.map(([name]) => [name, true])));
  return (
    <aside className="fixed left-0 top-0 z-20 h-full w-[220px] overflow-y-auto bg-slate-950 px-3 py-4 text-slate-100">
      <div className="mb-5 px-2 text-base font-bold">Agent Canvas</div>
      <div className="space-y-3">
        {groups.map(([name, types]) => (
          <section key={name}>
            <button className="flex w-full items-center justify-between px-2 py-1 text-xs font-semibold uppercase text-slate-400" onClick={() => setOpen({ ...open, [name]: !open[name] })}>
              {name} <ChevronDown size={14} className={open[name] ? '' : '-rotate-90'} />
            </button>
            {open[name] ? (
              <div className="space-y-1">
                {types.map((type) => {
                  const definition = nodeDefinitions[type];
                  const Icon = definition.icon;
                  return (
                    <div
                      key={type}
                      draggable
                      onDragStart={(event) => {
                        event.dataTransfer.setData('application/reactflow', type);
                        event.dataTransfer.effectAllowed = 'move';
                      }}
                      className="flex cursor-grab items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-slate-800"
                    >
                      <Icon size={16} /> {definition.label}
                    </div>
                  );
                })}
              </div>
            ) : null}
          </section>
        ))}
      </div>
    </aside>
  );
}
