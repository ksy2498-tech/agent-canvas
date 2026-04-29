import { useEffect } from 'react';
import { ReactFlowProvider } from 'reactflow';
import Canvas from './components/Canvas';
import ConfigPanel from './components/ConfigPanel';
import RunPanel from './components/RunPanel';
import Sidebar from './components/Sidebar';
import Toolbar from './components/Toolbar';
import { useGraphStore } from './store/graphStore';
import { useMCPStore } from './store/mcpStore';

export default function App() {
  const panelMode = useGraphStore((state) => state.panelMode);
  const loadServers = useMCPStore((state) => state.loadServers);

  useEffect(() => {
    loadServers().catch(() => {});
  }, [loadServers]);

  return (
    <ReactFlowProvider>
      <div className="h-full bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        <Sidebar />
        <Toolbar />
        <Canvas />
        {panelMode === 'config' ? <ConfigPanel /> : null}
        {panelMode === 'run' ? <RunPanel /> : null}
      </div>
    </ReactFlowProvider>
  );
}
