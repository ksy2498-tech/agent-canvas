import { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';
import { Copy, Edit3, Trash2, CircleDot } from 'lucide-react';
import { useGraphStore } from '../../store/graphStore';

export const categoryColors = {
  start: '#22c55e',
  end: '#ef4444',
  llm: '#3b82f6',
  mcp: '#14b8a6',
  code: '#f97316',
  router: '#f97316',
  condition: '#f97316',
  breakpoint: '#ef4444',
  session: '#eab308',
  state: '#eab308',
  db: '#b91c1c',
  artifact: '#0d9488',
  io: '#6b7280',
  nlp: '#a855f7',
};

const ContextMenu = ({ x, y, onClose, onEdit, onBreakpoint, hasBreakpoint, onDuplicate, onDelete }) => (
  <div
    className="fixed z-50 w-44 overflow-hidden rounded-md border border-slate-200 bg-white text-xs shadow-xl dark:border-slate-700 dark:bg-slate-900"
    style={{ left: x, top: y }}
    onMouseLeave={onClose}
  >
    <button className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-slate-100 dark:hover:bg-slate-800" onClick={onEdit}>
      <Edit3 size={14} /> Edit
    </button>
    <button className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-slate-100 dark:hover:bg-slate-800" onClick={onBreakpoint}>
      <CircleDot size={14} /> {hasBreakpoint ? 'Remove Breakpoint' : 'Add Breakpoint'}
    </button>
    <button className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-slate-100 dark:hover:bg-slate-800" onClick={onDuplicate}>
      <Copy size={14} /> Duplicate
    </button>
    <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30" onClick={onDelete}>
      <Trash2 size={14} /> Delete
    </button>
  </div>
);

function BaseNode({ id, data, selected, icon: Icon, label, category = 'io', children }) {
  const [menu, setMenu] = useState(null);
  const {
    breakpoints,
    runningNodeId,
    selectNode,
    toggleBreakpointOnNode,
    nodes,
    edges,
    setNodes,
    setEdges,
    pushHistory,
  } = useGraphStore();
  const hasBreakpoint = Boolean(breakpoints[id]);
  const attachedCount = data?.attachedTools?.length || 0;
  const color = categoryColors[category] || '#6b7280';
  const hasError = data?.validationError;
  const running = runningNodeId === id || data?.status === 'running';
  const connectionTarget = data?.connectionTarget;

  const closeMenu = () => setMenu(null);
  const duplicate = () => {
    pushHistory();
    const current = nodes.find((node) => node.id === id);
    if (!current) return;
    setNodes([
      ...nodes,
      {
        ...current,
        id: `${current.type}-${crypto.randomUUID()}`,
        position: { x: current.position.x + 20, y: current.position.y + 20 },
        selected: false,
      },
    ]);
    closeMenu();
  };
  const remove = () => {
    pushHistory();
    setNodes(nodes.filter((node) => node.id !== id));
    setEdges(edges.filter((edge) => edge.source !== id && edge.target !== id));
    closeMenu();
  };

  return (
    <>
      <div
        onContextMenu={(event) => {
          event.preventDefault();
          setMenu({ x: event.clientX, y: event.clientY });
        }}
        className={[
          'group relative min-w-[180px] rounded-lg border bg-white shadow-node transition dark:bg-slate-900',
          selected ? 'ring-2 ring-blue-400' : '',
          running ? 'ring-4 ring-yellow-300/80' : '',
          connectionTarget ? 'ring-4 ring-blue-400/70 ring-offset-2 ring-offset-slate-50 dark:ring-offset-slate-950' : '',
          hasError ? 'border-dashed border-red-500' : 'border-slate-200 dark:border-slate-700',
          category === 'breakpoint' ? 'animate-pulseBorder' : '',
        ].join(' ')}
        style={{ borderLeft: `6px solid ${color}` }}
      >
        {[Position.Top, Position.Bottom, Position.Left, Position.Right].map((position) => (
          <Handle key={`${position}-target`} className="node-handle" type="target" position={position} id={`${position}-target`} />
        ))}
        {[Position.Top, Position.Bottom, Position.Left, Position.Right].map((position) => (
          <Handle key={`${position}-source`} className="node-handle" type="source" position={position} id={`${position}-source`} />
        ))}

        <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-800 dark:border-slate-800 dark:text-slate-100">
          {Icon ? <Icon size={16} style={{ color }} /> : null}
          <span className="truncate">{data?.label || label}</span>
        </div>
        <div className="px-3 py-1.5 text-[11px] text-slate-500 dark:text-slate-400">{children}</div>
        <div className="absolute right-2 top-2 flex items-center gap-1">
          {hasError ? <span className="h-2.5 w-2.5 rounded-full bg-red-500" /> : null}
          {hasBreakpoint ? <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-700">BP</span> : null}
          {attachedCount ? <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-bold text-blue-700">MCP {attachedCount}</span> : null}
        </div>
        {hasError ? (
          <div className="pointer-events-none absolute left-3 top-[calc(100%+6px)] z-40 hidden max-w-[260px] whitespace-pre-wrap rounded-md border border-red-200 bg-white px-3 py-2 text-[11px] leading-4 text-red-700 shadow-xl group-hover:block dark:border-red-900 dark:bg-slate-950 dark:text-red-300">
            {hasError}
          </div>
        ) : null}
      </div>
      {menu ? (
        <ContextMenu
          {...menu}
          onClose={closeMenu}
          onEdit={() => {
            selectNode(id);
            closeMenu();
          }}
          hasBreakpoint={hasBreakpoint}
          onBreakpoint={() => {
            toggleBreakpointOnNode(id);
            closeMenu();
          }}
          onDuplicate={duplicate}
          onDelete={remove}
        />
      ) : null}
    </>
  );
}

export default memo(BaseNode);
