import { useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, ChevronRight, Plus, Trash2, X } from 'lucide-react';
import { useGraphStore } from '../../../store/graphStore';
import { useMCPStore } from '../../../store/mcpStore';

const defaultModes = ['tool-only'];

function ToolRow({ tool, executionModes, onMode, onRemove }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-slate-200 dark:border-slate-700">
      <div className="flex items-center gap-2 px-2 py-2 text-xs">
        <button onClick={() => setOpen(!open)}>{open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</button>
        <div className="min-w-0 flex-1 truncate">
          <span className="font-semibold">{tool.serverName}</span> &gt; {tool.name}
        </div>
        <select className="field max-w-[96px] py-1 text-xs" value={tool.executionMode} onChange={(e) => onMode(e.target.value)}>
          {executionModes.map((mode) => (
            <option key={mode} value={mode}>
              {mode}
            </option>
          ))}
        </select>
        <button onClick={onRemove} title="Remove">
          <Trash2 size={14} />
        </button>
      </div>
      {open ? (
        <div className="space-y-2 border-t border-slate-200 p-2 text-xs text-slate-600 dark:border-slate-700 dark:text-slate-300">
          <p>{tool.description || 'No description provided.'}</p>
          <pre className="max-h-40 overflow-auto rounded bg-slate-100 p-2 dark:bg-slate-950">
            {JSON.stringify(tool.inputSchema || {}, null, 2)}
          </pre>
        </div>
      ) : null}
    </div>
  );
}

function Picker({ onClose, onPick, graphId }) {
  const [tab, setTab] = useState('global');
  const { globalServers, graphServers } = useMCPStore();
  const servers = tab === 'global' ? globalServers : graphServers[graphId] || [];
  const picker = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/40" onMouseDown={onClose}>
      <div className="max-h-[88vh] w-[560px] max-w-[92vw] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h3 className="font-semibold">Attach MCP Tool</h3>
          <button className="icon-btn" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="flex gap-2 p-4">
          {['global', 'graph'].map((next) => (
            <button key={next} className={tab === next ? 'primary-btn' : 'secondary-btn'} onClick={() => setTab(next)}>
              {next === 'global' ? 'Global Servers' : 'Graph Servers'}
            </button>
          ))}
        </div>
        <div className="max-h-[55vh] space-y-3 overflow-auto px-4 pb-4">
          {servers.map((server) => (
            <details key={server.id} className="rounded-md border border-slate-200 p-3 dark:border-slate-700">
              <summary className="cursor-pointer text-xs font-medium">
                <span className={`mr-2 inline-block h-2 w-2 rounded-full ${server.status === 'connected' ? 'bg-green-500' : server.status === 'error' ? 'bg-red-500' : 'bg-slate-400'}`} />
                {server.name} <span className="text-xs text-slate-500">({server.transport})</span>
              </summary>
              <div className="mt-3 space-y-2">
                {(Array.isArray(server.tools) ? server.tools : []).map((tool) => (
                  <label key={tool.name} className="flex items-center gap-2 text-xs">
                    <input type="checkbox" onChange={(e) => e.target.checked && onPick(server, tool)} />
                    {tool.name}
                  </label>
                ))}
                {!(Array.isArray(server.tools) && server.tools.length) ? <p className="text-xs text-slate-500">No tools loaded.</p> : null}
              </div>
            </details>
          ))}
          {!servers.length ? <div className="rounded-md border border-dashed border-slate-300 p-4 text-xs text-slate-500 dark:border-slate-700">No MCP servers configured for this scope.</div> : null}
        </div>
      </div>
    </div>
  );
  return createPortal(picker, document.body);
}

export default function MCPToolsSection({ nodeId, executionModes = defaultModes }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const { graphId, nodes, updateNodeData } = useGraphStore();
  const node = nodes.find((item) => item.id === nodeId);
  const attachedTools = node?.data?.attachedTools || [];
  const setAttached = (attached) => updateNodeData(nodeId, { attachedTools: attached });

  const pickTool = (server, tool) => {
    const exists = attachedTools.some((item) => item.serverId === server.id && item.name === tool.name);
    if (exists) return;
    setAttached([
      ...attachedTools,
      {
        ...tool,
        serverId: server.id,
        serverName: server.name,
        executionMode: executionModes[0],
      },
    ]);
  };

  return (
    <section className="mt-5 border-t border-slate-200 pt-4 dark:border-slate-700">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-xs font-semibold">MCP Tools</h4>
        <button className="icon-btn" onClick={() => setPickerOpen(true)} title="Attach tool">
          <Plus size={16} />
        </button>
      </div>
      <div className="space-y-2">
        {attachedTools.map((tool, index) => (
          <ToolRow
            key={`${tool.serverId}-${tool.name}`}
            tool={tool}
            executionModes={executionModes}
            onMode={(executionMode) => setAttached(attachedTools.map((item, i) => (i === index ? { ...item, executionMode } : item)))}
            onRemove={() => setAttached(attachedTools.filter((_, i) => i !== index))}
          />
        ))}
        {!attachedTools.length ? <p className="text-xs text-slate-500">No MCP tools attached.</p> : null}
      </div>
      {pickerOpen ? <Picker graphId={graphId} onClose={() => setPickerOpen(false)} onPick={pickTool} /> : null}
    </section>
  );
}
