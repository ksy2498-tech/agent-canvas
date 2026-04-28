import { Download, Moon, Play, Save, ServerCog, Sun, Upload } from 'lucide-react';
import { useState } from 'react';
import toast from 'react-hot-toast';
import { downloadCode, listGraphs } from '../api/client';
import { useGraphStore } from '../store/graphStore';
import MCPRegistry from './MCPRegistry';

export default function Toolbar() {
  const [mcpOpen, setMcpOpen] = useState(false);
  const [loadOpen, setLoadOpen] = useState(false);
  const [graphs, setGraphs] = useState([]);
  const { graphId, graphName, setGraphName, saveGraph, loadGraph, setPanelMode, darkMode, toggleDarkMode, validationErrors } = useGraphStore();
  return (
    <header className="fixed left-[220px] right-0 top-0 z-20 flex h-14 items-center gap-2 border-b border-slate-200 bg-white px-4 dark:border-slate-800 dark:bg-slate-950">
      <div className="font-bold">AC</div>
      <input className="field max-w-[260px] font-medium" value={graphName} onChange={(e) => setGraphName(e.target.value)} />
      <button className="secondary-btn" onClick={() => saveGraph().then(() => toast.success('Saved')).catch(() => {})}><Save size={16} /> Save</button>
      <button className="secondary-btn" onClick={() => listGraphs().then((items) => { setGraphs(items); setLoadOpen(true); }).catch(() => toast.error('Could not load graph list'))}><Upload size={16} /> Load</button>
      <button className="secondary-btn" onClick={() => setMcpOpen(true)}><ServerCog size={16} /> MCP</button>
      <button className="primary-btn" onClick={() => setPanelMode('run')}><Play size={16} /> Run</button>
      <button className="secondary-btn" onClick={() => downloadCode(graphId).catch(() => toast.error('Download failed'))}><Download size={16} /> Download Code</button>
      {validationErrors.length ? (
        <div className="group relative rounded-md border border-red-200 bg-red-50 px-2 py-1 text-[11px] font-medium text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
          {validationErrors.length} validation issue{validationErrors.length > 1 ? 's' : ''}
          <div className="pointer-events-none absolute right-0 top-[calc(100%+8px)] z-50 hidden w-72 whitespace-pre-wrap rounded-md border border-red-200 bg-white p-3 text-[11px] font-normal leading-4 shadow-xl group-hover:block dark:border-red-900 dark:bg-slate-950">
            {validationErrors.join('\n')}
          </div>
        </div>
      ) : null}
      <button className="icon-btn ml-auto" onClick={toggleDarkMode} title="Toggle dark mode">{darkMode ? <Sun size={17} /> : <Moon size={17} />}</button>
      {mcpOpen ? <MCPRegistry onClose={() => setMcpOpen(false)} /> : null}
      {loadOpen ? <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40"><div className="w-[420px] rounded-lg bg-white p-4 shadow-xl dark:bg-slate-900"><h2 className="mb-3 font-semibold">Load Graph</h2><div className="space-y-2">{graphs.map((graph) => <button key={graph.id} className="w-full rounded-md border border-slate-200 p-3 text-left hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800" onClick={() => { loadGraph(graph.id); setLoadOpen(false); }}>{graph.name || graph.graphName || graph.id}</button>)}</div><button className="secondary-btn mt-4" onClick={() => setLoadOpen(false)}>Close</button></div></div> : null}
    </header>
  );
}
