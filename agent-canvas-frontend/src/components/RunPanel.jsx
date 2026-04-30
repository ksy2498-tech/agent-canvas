import { useEffect, useRef, useState } from 'react';
import { Send, Trash2, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { runGraph, resumeExecution } from '../api/client';
import { useGraphStore } from '../store/graphStore';

const traceEventKey = (runId, event, index = 0) => `${runId}:${event.type}:${event.nodeId || event.label || 'event'}:${event.timestamp || index}`;

export default function RunPanel() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [runHistory, setRunHistory] = useState([]);
  const [selectedStateEvent, setSelectedStateEvent] = useState(null);
  const [pausedRunId, setPausedRunId] = useState(null);
  const activeRunIdRef = useRef(null);
  const { graphId, breakpoints, edgeBreakpoints, setPanelMode, validateGraph, saveGraph, runStatus, setRunStatus, pausedState, pausedAt, setTrace, setRunningNodeId, setPausedState } = useGraphStore();

  useEffect(() => {
    const handler = (event) => {
      if (event.key === 'Escape' && selectedStateEvent) {
        event.preventDefault();
        event.stopPropagation();
        setSelectedStateEvent(null);
      }
    };
    window.addEventListener('keydown', handler, true);
    return () => window.removeEventListener('keydown', handler, true);
  }, [selectedStateEvent]);

  const appendTrace = (item) => setTrace([...(useGraphStore.getState().trace || []), item]);
  const appendRunEvent = (runId, event) => {
    setRunHistory((runs) => runs.map((run) => run.id === runId ? { ...run, events: [...run.events, event] } : run));
  };
  const updateRun = (runId, patch) => {
    setRunHistory((runs) => runs.map((run) => run.id === runId ? { ...run, ...patch } : run));
  };
  const toggleStateEvent = (event) => {
    setSelectedStateEvent((current) => current?.key === event.key ? null : event);
  };

  const handlePayload = (payload) => {
    const runId = payload.runId || activeRunIdRef.current;
    if (runId && ['node_start', 'node_end', 'trace', 'error', 'done', 'paused'].includes(payload.type)) {
      appendRunEvent(runId, { ...payload, timestamp: new Date().toISOString() });
    }
    if (payload.type === 'trace') appendTrace(payload);
    if (payload.type === 'node' || payload.type === 'node_start') {
      setRunningNodeId(payload.nodeId);
    }
    if (payload.type === 'node_end') {
      setRunningNodeId(null);
      appendTrace({ ...payload, status: payload.status || 'ok' });
    }
    if (payload.type === 'paused') {
      setPausedRunId(runId);
      setPausedState(payload.state, payload.at);
      setRunStatus('paused');
      setRunningNodeId(null);
      if (runId) updateRun(runId, { status: 'paused' });
    }
    if (payload.type === 'message') setMessages((items) => [...items, { role: 'assistant', text: payload.text }]);
    if (payload.type === 'error') {
      const message = payload.message || 'Run failed';
      setMessages((items) => [...items, { role: 'error', text: message }]);
      appendTrace({ ...payload, label: payload.label || 'Error', status: 'error' });
      toast.error(message);
      setRunStatus('error');
      setRunningNodeId(null);
      if (runId) updateRun(runId, { status: 'error', finishedAt: new Date().toISOString() });
    }
    if (payload.type === 'done') {
      setRunStatus('done');
      setPausedRunId(null);
      setRunningNodeId(null);
      if (payload.output) setMessages((items) => [...items, { role: 'assistant', text: payload.output }]);
      if (runId) updateRun(runId, { status: 'done', finishedAt: new Date().toISOString(), output: payload.output });
    }
  };

  const clearRunPanel = () => {
    setMessages([]);
    setRunHistory([]);
    setSelectedStateEvent(null);
    setPausedRunId(null);
    setTrace([]);
    setRunningNodeId(null);
  };

  const resumePausedRun = async (editedState) => {
    if (!pausedRunId) {
      toast.error('No paused run to resume');
      return;
    }
    activeRunIdRef.current = pausedRunId;
    setRunStatus('running');
    updateRun(pausedRunId, { status: 'running' });
    try {
      await resumeExecution(graphId, pausedRunId, editedState, handlePayload);
    } catch (error) {
      const message = error.message || 'Resume failed';
      toast.error(message);
      setRunStatus('error');
      updateRun(pausedRunId, { status: 'error', finishedAt: new Date().toISOString() });
    }
  };

  const send = async () => {
    if (!query.trim() || !validateGraph()) return;
    const runId = crypto.randomUUID();
    const runQuery = query;
    activeRunIdRef.current = runId;
    setMessages((items) => [...items, { role: 'user', text: runQuery }]);
    setRunHistory((runs) => [{ id: runId, query: runQuery, status: 'running', startedAt: new Date().toISOString(), events: [] }, ...runs]);
    setSelectedStateEvent(null);
    setPausedRunId(null);
    setRunStatus('running');
    let runGraphId = graphId;
    try {
      runGraphId = await saveGraph({ validate: false });
    } catch (error) {
      toast.error(error.message || 'Could not save graph before run');
      setRunStatus('error');
      updateRun(runId, { status: 'error', finishedAt: new Date().toISOString() });
      return;
    }
    runGraph(runGraphId, runQuery, breakpoints, edgeBreakpoints, handlePayload, runId).catch((error) => {
      const message = error.message || 'Run failed';
      toast.error(message);
      setMessages((items) => [...items, { role: 'error', text: message }]);
      setRunStatus('error');
      setRunningNodeId(null);
      updateRun(runId, { status: 'error', finishedAt: new Date().toISOString() });
    });
    setQuery('');
  };

  return (
    <>
      {selectedStateEvent ? <StateDrawer event={selectedStateEvent} onClose={() => setSelectedStateEvent(null)} /> : null}
      <aside className="fixed right-0 top-0 z-30 flex h-full w-[420px] flex-col border-l border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900">
        <div className="border-b border-slate-200 p-4 dark:border-slate-800">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Run</h2>
            <div className="flex items-center gap-2">
              <button className="icon-btn" title="Clear run history" onClick={clearRunPanel}><Trash2 size={16} /></button>
              <button className="icon-btn" onClick={() => setPanelMode(null)}><X size={17} /></button>
            </div>
          </div>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          <ChatSection messages={messages} query={query} setQuery={setQuery} send={send} />
          <TraceSection runs={runHistory} selectedKey={selectedStateEvent?.key} onSelectState={toggleStateEvent} />
          {runStatus === 'paused' ? <BreakpointResume pausedAt={pausedAt} pausedState={pausedState} onResume={resumePausedRun} /> : null}
        </div>
      </aside>
    </>
  );
}

function ChatSection({ messages, query, setQuery, send }) {
  return <section className="space-y-3"><h3 className="text-xs font-semibold">Chat</h3><div className="h-44 space-y-2 overflow-y-auto rounded-md border border-slate-200 p-3 dark:border-slate-700">{messages.map((m, i) => <div key={i} className={`rounded-md px-2.5 py-1.5 text-xs ${m.role === 'user' ? 'ml-8 bg-blue-600 text-white' : m.role === 'error' ? 'mr-8 border border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200' : 'mr-8 bg-slate-100 dark:bg-slate-800'}`}>{m.text}</div>)}</div><div className="flex gap-2"><input className="field" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()} /><button className="primary-btn" onClick={send}><Send size={16} /></button></div></section>;
}

function TraceSection({ runs, selectedKey, onSelectState }) {
  return <section className="space-y-2"><div className="flex items-center justify-between"><h3 className="text-xs font-semibold">Trace</h3><span className="text-[11px] text-slate-500">Click node end to inspect state</span></div>{runs.length ? runs.map((run, index) => <RunTrace key={run.id} run={run} index={runs.length - index} selectedKey={selectedKey} onSelectState={onSelectState} />) : <p className="text-xs text-slate-500">No trace yet. Run the graph to see request-level traces.</p>}</section>;
}

function RunTrace({ run, index, selectedKey, onSelectState }) {
  const nodeEvents = run.events.filter((event) => ['node_start', 'node_end', 'error', 'paused', 'done'].includes(event.type));
  return <details className={`rounded-md border p-2 ${run.status === 'error' ? 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/20' : 'border-slate-200 dark:border-slate-700'}`} open={run.status === 'running' || run.status === 'paused'}><summary className="cursor-pointer text-xs"><span className="font-semibold">Run {index}</span> <span className="ml-1 text-slate-500">{run.query}</span> <span className={`ml-1 rounded px-2 py-0.5 text-[11px] ${run.status === 'error' ? 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-200' : run.status === 'running' ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-200' : run.status === 'paused' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-200' : 'bg-slate-100 dark:bg-slate-800'}`}>{run.status}</span></summary><div className="mt-2 space-y-1">{nodeEvents.map((event, i) => <TraceEvent key={traceEventKey(run.id, event, i)} event={{ ...event, key: traceEventKey(run.id, event, i) }} selected={selectedKey === traceEventKey(run.id, event, i)} onSelectState={onSelectState} />)}</div></details>;
}

function TraceEvent({ event, selected, onSelectState }) {
  const clickable = Boolean(event.state);
  const label = event.label || event.nodeId || event.type;
  const status = event.status || (event.type === 'node_start' ? 'start' : event.type === 'done' ? 'end' : event.type);
  return <button type="button" disabled={!clickable} onClick={() => clickable && onSelectState(event)} className={`w-full rounded-md border px-2 py-1.5 text-left text-xs transition ${selected ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-300 dark:border-blue-500 dark:bg-blue-950/30 dark:ring-blue-800' : clickable ? 'cursor-pointer hover:border-blue-300 hover:bg-blue-50 dark:hover:border-blue-800 dark:hover:bg-blue-950/20' : 'cursor-default'} ${!selected && event.type === 'node_start' ? 'border-slate-100 text-slate-500 dark:border-slate-800' : !selected ? 'border-slate-200 dark:border-slate-700' : ''}`}><span className="font-medium">{label}</span><span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">{status}</span>{event.output_preview ? <div className="mt-1 truncate text-[11px] text-slate-500">{event.output_preview}</div> : null}</button>;
}

function StateDrawer({ event, onClose }) {
  const state = event.state;
  return <aside className="fixed right-[420px] top-0 z-40 h-full w-[420px] overflow-y-auto border-l border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900"><div className="sticky top-0 z-10 border-b border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"><div className="flex items-center justify-between"><div><h2 className="font-semibold">State</h2><p className="text-xs text-slate-500">{event.label || event.nodeId || event.type}</p></div><button className="icon-btn" onClick={onClose}><X size={17} /></button></div></div><div className="space-y-2 p-4">{state ? Object.entries(state).map(([key, value]) => <details key={key} className="rounded-md border border-slate-200 p-2 dark:border-slate-700" open={['current_output', 'node_results', 'loaded_session'].includes(key)}><summary className="cursor-pointer text-xs font-medium">{key}</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words text-[11px]">{JSON.stringify(value, null, 2)}</pre></details>) : <p className="text-xs text-slate-500">No state snapshot for this event.</p>}</div></aside>;
}

function BreakpointResume({ pausedAt, pausedState, onResume }) {
  const [draftText, setDraftText] = useState(() => JSON.stringify(pausedState || {}, null, 2));
  const resume = () => {
    try {
      onResume(JSON.parse(draftText || '{}'));
    } catch {
      toast.error('State JSON is invalid');
    }
  };
  return <section className="mt-4 space-y-3 rounded-md border border-yellow-300 bg-yellow-50 p-3 dark:bg-yellow-950/20"><h3 className="font-semibold">Paused at {pausedAt}</h3><p className="text-xs text-slate-600 dark:text-slate-300">Edit state JSON, then resume from the next node. The messages key is kept from the original runtime state.</p><textarea className="field h-64 resize-y bg-white font-mono text-xs dark:bg-slate-950" value={draftText} onChange={(e) => setDraftText(e.target.value)} /><div className="flex gap-2"><button className="primary-btn" onClick={resume}>Resume</button><button className="secondary-btn" onClick={() => onResume(pausedState)}>Skip edits</button></div></section>;
}
