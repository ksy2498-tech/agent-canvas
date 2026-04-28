import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactFlow, { Background, Controls, MiniMap, addEdge, applyEdgeChanges, applyNodeChanges, useReactFlow } from 'reactflow';
import toast from 'react-hot-toast';
import { useGraphStore } from '../store/graphStore';
import { nodeDefinitions } from './nodes/nodeFactory.jsx';
import StartNode from './nodes/StartNode';
import EndNode from './nodes/EndNode';
import LLMNode from './nodes/LLMNode';
import CodeNode from './nodes/CodeNode';
import RouterNode from './nodes/RouterNode';
import ConditionNode from './nodes/ConditionNode';
import BreakpointNode from './nodes/BreakpointNode';
import SessionLoadNode from './nodes/SessionLoadNode';
import SessionSaveNode from './nodes/SessionSaveNode';
import StateSetNode from './nodes/StateSetNode';
import StateGetNode from './nodes/StateGetNode';
import DBConnectionNode from './nodes/DBConnectionNode';
import DBQueryNode from './nodes/DBQueryNode';
import ArtifactStoreNode from './nodes/ArtifactStoreNode';
import ArtifactLoadNode from './nodes/ArtifactLoadNode';
import HTTPRequestNode from './nodes/HTTPRequestNode';
import InputTransformNode from './nodes/InputTransformNode';
import OutputFormatNode from './nodes/OutputFormatNode';
import NLPNode from './nodes/NLPNode';

const nodeTypes = {
  start: StartNode, end: EndNode, llm: LLMNode, code: CodeNode, router: RouterNode, condition: ConditionNode, breakpoint: BreakpointNode,
  sessionLoad: SessionLoadNode, sessionSave: SessionSaveNode, stateSet: StateSetNode, stateGet: StateGetNode, dbConnection: DBConnectionNode, dbQuery: DBQueryNode,
  artifactStore: ArtifactStoreNode, artifactLoad: ArtifactLoadNode, httpRequest: HTTPRequestNode, inputTransform: InputTransformNode, outputFormat: OutputFormatNode, nlp: NLPNode,
};

export default function Canvas() {
  const wrapper = useRef(null);
  const { screenToFlowPosition } = useReactFlow();
  const [edgeMenu, setEdgeMenu] = useState(null);
  const { graphId, nodes, edges, setNodes, setEdges, selectNode, pushHistory, saveGraph, edgeBreakpoints, toggleBreakpointOnEdge, undo, setPanelMode } = useGraphStore();
  const selectedNodeRef = useRef(null);

  useEffect(() => { selectedNodeRef.current = nodes.find((n) => n.selected); }, [nodes]);
  useEffect(() => {
    const timer = setTimeout(() => {
      if (nodes.length && graphId !== 'local-graph') saveGraph({ validate: false }).catch(() => {});
    }, 500);
    return () => clearTimeout(timer);
  }, [graphId, nodes, edges, saveGraph]);

  const styledEdges = useMemo(() => edges.map((edge) => edgeBreakpoints[edge.id] ? { ...edge, animated: true, style: { stroke: '#ef4444', strokeDasharray: '6 4' } } : edge), [edges, edgeBreakpoints]);
  const onNodesChange = useCallback((changes) => setNodes(applyNodeChanges(changes, nodes)), [nodes, setNodes]);
  const onEdgesChange = useCallback((changes) => setEdges(applyEdgeChanges(changes, edges)), [edges, setEdges]);
  const onConnect = useCallback((connection) => { pushHistory(); setEdges(addEdge(connection, edges)); }, [edges, setEdges, pushHistory]);
  const addNode = (type, position) => {
    pushHistory();
    const definition = nodeDefinitions[type];
    const id = `${type}-${crypto.randomUUID()}`;
    setNodes([...nodes, { id, type, position, data: { label: definition.label, attachedTools: [] } }]);
  };

  useEffect(() => {
    const isTypingTarget = (target) => {
      if (!target) return false;
      const element = target instanceof Element ? target : null;
      if (!element) return false;
      const tagName = element.tagName?.toLowerCase();
      return (
        tagName === 'input' ||
        tagName === 'textarea' ||
        tagName === 'select' ||
        element.isContentEditable ||
        Boolean(element.closest('[contenteditable="true"], .monaco-editor, .field'))
      );
    };

    const handler = (event) => {
      const typing = isTypingTarget(event.target);
      if (typing && event.key !== 'Escape') return;
      if (event.key === 'Escape') setPanelMode(null);
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') { event.preventDefault(); saveGraph().then(() => toast.success('Graph saved')).catch(() => {}); }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); undo(); }
      if ((event.key === 'Delete' || event.key === 'Backspace') && selectedNodeRef.current) {
        const id = selectedNodeRef.current.id;
        pushHistory();
        setNodes(nodes.filter((n) => n.id !== id));
        setEdges(edges.filter((e) => e.source !== id && e.target !== id));
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'c') selectedNodeRef.current && localStorage.setItem('copiedNode', JSON.stringify(selectedNodeRef.current));
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'v') {
        const copied = localStorage.getItem('copiedNode');
        if (copied) {
          const node = JSON.parse(copied);
          setNodes([...nodes, { ...node, id: `${node.type}-${crypto.randomUUID()}`, position: { x: node.position.x + 20, y: node.position.y + 20 } }]);
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [nodes, edges, saveGraph, setNodes, setEdges, pushHistory, undo, setPanelMode]);

  return (
    <div className="h-full pl-[220px] pt-[56px]" ref={wrapper}>
      {!nodes.length ? <div className="pointer-events-none absolute left-[calc(220px+50%)] top-1/2 z-10 -translate-x-1/2 rounded-md bg-white/90 px-4 py-3 text-slate-500 shadow dark:bg-slate-900/90">Drag a node to get started</div> : null}
      <ReactFlow
        nodes={nodes}
        edges={styledEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, node) => selectNode(node.id)}
        onPaneClick={() => selectNode(null)}
        onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; }}
        onDrop={(event) => {
          event.preventDefault();
          const type = event.dataTransfer.getData('application/reactflow');
          if (type) addNode(type, screenToFlowPosition({ x: event.clientX, y: event.clientY }));
        }}
        onEdgeContextMenu={(event, edge) => { event.preventDefault(); setEdgeMenu({ x: event.clientX, y: event.clientY, edge }); }}
        defaultViewport={{ x: 240, y: 120, zoom: 0.85 }}
        minZoom={0.25}
        maxZoom={1.4}
      >
        <Background variant="dots" gap={20} size={1} />
        <Controls />
        <MiniMap />
      </ReactFlow>
      {edgeMenu ? <div className="fixed z-50 rounded-md border border-slate-200 bg-white p-1 text-xs shadow-xl dark:border-slate-700 dark:bg-slate-900" style={{ left: edgeMenu.x, top: edgeMenu.y }} onMouseLeave={() => setEdgeMenu(null)}><button className="px-2.5 py-1.5 hover:bg-slate-100 dark:hover:bg-slate-800" onClick={() => { toggleBreakpointOnEdge(edgeMenu.edge.id); setEdgeMenu(null); }}>{edgeBreakpoints[edgeMenu.edge.id] ? 'Remove Breakpoint' : 'Add Breakpoint'}</button></div> : null}
    </div>
  );
}
