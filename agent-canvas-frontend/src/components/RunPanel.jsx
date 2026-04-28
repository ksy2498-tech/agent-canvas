import { useState } from 'react';
import { Send, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { runGraph } from '../api/client';
import { useGraphStore } from '../store/graphStore';

export default function RunPanel() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const { graphId, breakpoints, edgeBreakpoints, setPanelMode, validateGraph, saveGraph, runStatus, setRunStatus, pausedState, pausedAt, resumeExecution, trace, setTrace, setRunningNodeId, setPausedState } = useGraphStore();
  const appendTrace = (item) => setTrace([...(useGraphStore.getState().trace || []), item]);

  const handlePayload = (payload) => {
    if (payload.type === 'trace') appendTrace(payload);
    if (payload.type === 'node' || payload.type === 'node_start') {
      setRunningNodeId(payload.nodeId);
    }
    if (payload.type === 'node_end') {
      setRunningNodeId(null);
      appendTrace({ ...payload, status: payload.status || 'ok' });
    }
    if (payload.type === 'paused') setPausedState(payload.state, payload.at);
    if (payload.type === 'message') setMessages((items) => [...items, { role: 'assistant', text: payload.text }]);
    if (payload.type === 'error') {
      const message = payload.message || 'Run failed';
      setMessages((items) => [...items, { role: 'error', text: message }]);
      appendTrace({ ...payload, label: payload.label || 'Error', status: 'error' });
      toast.error(message);
      setRunStatus('error');
      setRunningNodeId(null);
    }
    if (payload.type === 'done') {
      setRunStatus('done');
      setRunningNodeId(null);
      if (payload.output) setMessages((items) => [...items, { role: 'assistant', text: payload.output }]);
    }
  };

  const send = async () => {
    if (!query.trim() || !validateGraph()) return;
    setMessages([...messages, { role: 'user', text: query }]);
    setRunStatus('running');
    let runGraphId = graphId;
    try {
      runGraphId = await saveGraph({ validate: false });
    } catch (error) {
      toast.error(error.message || 'Could not save graph before run');
      setRunStatus('error');
      return;
    }
    runGraph(runGraphId, query, breakpoints, edgeBreakpoints, handlePayload).catch((error) => {
      const message = error.message || 'Run failed';
      toast.error(message);
      setMessages((items) => [...items, { role: 'error', text: message }]);
      setRunStatus('error');
      setRunningNodeId(null);
    });
    setQuery('');
  };
  return (
    <aside className="fixed right-0 top-0 z-30 flex h-full w-[420px] flex-col border-l border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between border-b border-slate-200 p-4 dark:border-slate-800"><h2 className="font-semibold">Run</h2><button className="icon-btn" onClick={() => setPanelMode(null)}><X size={17} /></button></div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <section className="space-y-3"><h3 className="text-xs font-semibold">Chat</h3><div className="h-52 space-y-2 overflow-y-auto rounded-md border border-slate-200 p-3 dark:border-slate-700">{messages.map((m, i) => <div key={i} className={`rounded-md px-2.5 py-1.5 text-xs ${m.role === 'user' ? 'ml-8 bg-blue-600 text-white' : m.role === 'error' ? 'mr-8 border border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200' : 'mr-8 bg-slate-100 dark:bg-slate-800'}`}>{m.text}</div>)}</div><div className="flex gap-2"><input className="field" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()} /><button className="primary-btn" onClick={send}><Send size={16} /></button></div></section>
        <section className="space-y-2"><h3 className="text-xs font-semibold">Execution Trace</h3>{trace.map((item, i) => <details key={i} className={`rounded-md border p-2 ${item.status === 'error' ? 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/20' : 'border-slate-200 dark:border-slate-700'}`}><summary className="cursor-pointer text-xs">{item.label || item.nodeId || item.type} <span className={`rounded px-2 py-0.5 text-[11px] ${item.status === 'error' ? 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-200' : 'bg-slate-100 dark:bg-slate-800'}`}>{item.status || 'success'}</span></summary><pre className="mt-2 max-h-32 overflow-auto text-[11px]">{JSON.stringify(item.output || item, null, 2)}</pre></details>)}</section>
        {runStatus === 'paused' ? <BreakpointResume pausedAt={pausedAt} pausedState={pausedState} onResume={(state) => resumeExecution(state).catch(() => toast.error('Resume failed'))} /> : null}
      </div>
    </aside>
  );
}

function BreakpointResume({ pausedAt, pausedState, onResume }) {
  const [draft, setDraft] = useState(pausedState || {});
  return <section className="space-y-3 rounded-md border border-yellow-300 bg-yellow-50 p-3 dark:bg-yellow-950/20"><h3 className="font-semibold">Paused at {pausedAt}</h3><pre className="max-h-48 overflow-auto rounded bg-white p-2 text-xs dark:bg-slate-950">{JSON.stringify(draft, null, 2)}</pre>{Object.entries(draft || {}).map(([key, value]) => <label key={key} className="block text-xs font-medium">{key}<input className="field mt-1 bg-white" value={typeof value === 'string' ? value : JSON.stringify(value)} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} /></label>)}<div className="flex gap-2"><button className="primary-btn" onClick={() => onResume(draft)}>Resume</button><button className="secondary-btn" onClick={() => onResume(pausedState)}>Skip</button></div></section>;
}
