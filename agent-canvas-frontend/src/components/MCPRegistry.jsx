import { useState } from 'react';
import { Plus, Trash2, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { useGraphStore } from '../store/graphStore';
import { useMCPStore } from '../store/mcpStore';
import KeyValueEditor from './ConfigPanel/shared/KeyValueEditor';

const emptyServer = { name: '', transport: 'stdio', command: '', args: [], url: '', headers: [], status: 'disconnected', tools: [] };

function ServerEditor({ server, scope }) {
  const [draft, setDraft] = useState(server);
  const { saveServer, removeServer, testConnection, fetchTools } = useMCPStore();
  const save = () => {
    saveServer(draft, scope)
      .then((saved) => {
        setDraft(saved);
        toast.success('MCP server saved');
      })
      .catch(() => toast.error('MCP server save failed'));
  };
  return (
    <div className="space-y-3 rounded-md border border-slate-200 p-3 dark:border-slate-700">
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${draft.status === 'connected' ? 'bg-green-500' : draft.status === 'error' ? 'bg-red-500' : 'bg-slate-400'}`} />
        <input className="field" value={draft.name} placeholder="Server name" onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        <button className="icon-btn" onClick={() => removeServer(draft.id, scope).catch(() => toast.error('Delete failed'))}><Trash2 size={16} /></button>
      </div>
      <select className="field" value={draft.transport} onChange={(e) => setDraft({ ...draft, transport: e.target.value })}>
        <option value="stdio">stdio</option>
        <option value="sse">sse</option>
      </select>
      {draft.transport === 'stdio' ? (
        <>
          <input className="field" placeholder="Command" value={draft.command || ''} onChange={(e) => setDraft({ ...draft, command: e.target.value })} />
          <KeyValueEditor value={(draft.args || []).map((arg, i) => ({ key: String(i), value: arg }))} onChange={(rows) => setDraft({ ...draft, args: rows.map((row) => row.value) })} />
        </>
      ) : (
        <>
          <input className="field" placeholder="SSE URL" value={draft.url || ''} onChange={(e) => setDraft({ ...draft, url: e.target.value })} />
          <KeyValueEditor value={draft.headers || []} onChange={(headers) => setDraft({ ...draft, headers })} />
        </>
      )}
      <div className="flex gap-2">
        <button className="secondary-btn" onClick={() => testConnection(draft, scope).then(() => toast.success('Connection tested')).catch(() => toast.error('Connection failed'))}>Test Connection</button>
        <button className="secondary-btn" onClick={() => fetchTools(draft, scope).catch(() => toast.error('Could not fetch tools'))}>Fetch Tools</button>
        <button className="primary-btn" onClick={save}>Save</button>
      </div>
    </div>
  );
}

export default function MCPRegistry({ onClose }) {
  const [tab, setTab] = useState('global');
  const graphId = useGraphStore((state) => state.graphId);
  const { globalServers, graphServers, upsertLocalServer } = useMCPStore();
  const scope = tab === 'global' ? 'global' : graphId;
  const servers = tab === 'global' ? globalServers : graphServers[graphId] || [];
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40">
      <div className="max-h-[88vh] w-[720px] max-w-[94vw] overflow-y-auto rounded-lg bg-white shadow-xl dark:bg-slate-900">
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="font-semibold">MCP Registry</h2>
          <button className="icon-btn" onClick={onClose}><X size={17} /></button>
        </div>
        <div className="flex gap-2 p-4">
          <button className={tab === 'global' ? 'primary-btn' : 'secondary-btn'} onClick={() => setTab('global')}>Global Servers</button>
          <button className={tab === 'graph' ? 'primary-btn' : 'secondary-btn'} onClick={() => setTab('graph')}>Graph Servers</button>
          <button className="secondary-btn ml-auto" onClick={() => upsertLocalServer({ ...emptyServer, id: crypto.randomUUID(), name: 'New MCP Server' }, scope)}><Plus size={15} /> Add Server</button>
        </div>
        <div className="space-y-3 p-4 pt-0">
          {servers.map((server) => <ServerEditor key={server.id} server={server} scope={scope} />)}
          {!servers.length ? <p className="text-xs text-slate-500">No MCP servers configured.</p> : null}
        </div>
      </div>
    </div>
  );
}
