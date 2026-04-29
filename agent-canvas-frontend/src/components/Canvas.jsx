import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactFlow, { Background, Controls, MiniMap, addEdge, applyEdgeChanges, applyNodeChanges, useReactFlow } from 'reactflow';
import toast from 'react-hot-toast';
import { useGraphStore } from '../store/graphStore';
import { nodeDefinitions } from './nodes/nodeFactory.jsx';
import StartNode from './nodes/StartNode';
import EndNode from './nodes/EndNode';
import LLMNode from './nodes/LLMNode';
import MCPToolNode from './nodes/MCPToolNode';
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
  start: StartNode, end: EndNode, llm: LLMNode, mcpTool: MCPToolNode, code: CodeNode, router: RouterNode, condition: ConditionNode, breakpoint: BreakpointNode,
  sessionLoad: SessionLoadNode, sessionSave: SessionSaveNode, stateSet: StateSetNode, stateGet: StateGetNode, dbConnection: DBConnectionNode, dbQuery: DBQueryNode,
  artifactStore: ArtifactStoreNode, artifactLoad: ArtifactLoadNode, httpRequest: HTTPRequestNode, inputTransform: InputTransformNode, outputFormat: OutputFormatNode, nlp: NLPNode,
};

const NODE_DEFAULT_WIDTH = 180;
const NODE_DEFAULT_HEIGHT = 64;
const EDGE_INSERT_DISTANCE = 32;

const nodeSize = (node) => ({
  width: node.width || node.measured?.width || NODE_DEFAULT_WIDTH,
  height: node.height || node.measured?.height || NODE_DEFAULT_HEIGHT,
});

const nodeCenter = (node) => {
  const { width, height } = nodeSize(node);
  return { x: node.position.x + width / 2, y: node.position.y + height / 2 };
};

const distanceToSegment = (point, start, end) => {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy;
  if (!lengthSquared) return Math.hypot(point.x - start.x, point.y - start.y);
  const t = Math.max(0, Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared));
  const projection = { x: start.x + t * dx, y: start.y + t * dy };
  return Math.hypot(point.x - projection.x, point.y - projection.y);
};

const handleForDirection = (from, to, type) => {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const side = Math.abs(dx) > Math.abs(dy)
    ? (dx < 0 ? 'left' : 'right')
    : (dy < 0 ? 'top' : 'bottom');
  return `${side}-${type}`;
};

const nodeType = (node) => node?.type?.toLowerCase();

export default function Canvas() {
  const wrapper = useRef(null);
  const { screenToFlowPosition } = useReactFlow();
  const [edgeMenu, setEdgeMenu] = useState(null);
  const [connectTargetId, setConnectTargetId] = useState(null);
  const [dropEdgeId, setDropEdgeId] = useState(null);
  const { graphId, nodes, edges, setNodes, setEdges, selectNode, pushHistory, saveGraph, edgeBreakpoints, toggleBreakpointOnEdge, undo, setPanelMode } = useGraphStore();
  const selectedNodeRef = useRef(null);
  const selectedEdgeRef = useRef(null);
  const connectionStartRef = useRef(null);

  useEffect(() => { selectedNodeRef.current = nodes.find((n) => n.selected); }, [nodes]);
  useEffect(() => { selectedEdgeRef.current = edges.find((e) => e.selected); }, [edges]);
  useEffect(() => {
    const timer = setTimeout(() => {
      if (nodes.length && graphId !== 'local-graph') saveGraph({ validate: false }).catch(() => {});
    }, 500);
    return () => clearTimeout(timer);
  }, [graphId, nodes, edges, saveGraph]);

  const styledNodes = useMemo(() => nodes.map((node) => ({
    ...node,
    data: { ...node.data, connectionTarget: node.id === connectTargetId },
  })), [nodes, connectTargetId]);
  const styledEdges = useMemo(() => edges.map((edge) => {
    if (edge.id === dropEdgeId) {
      return { ...edge, animated: true, style: { ...(edge.style || {}), stroke: '#2563eb', strokeWidth: 3 } };
    }
    if (edgeBreakpoints[edge.id]) return { ...edge, animated: true, style: { stroke: '#ef4444', strokeDasharray: '6 4' } };
    return edge;
  }), [edges, edgeBreakpoints, dropEdgeId]);
  const onNodesChange = useCallback((changes) => setNodes(applyNodeChanges(changes, nodes)), [nodes, setNodes]);
  const onEdgesChange = useCallback((changes) => setEdges(applyEdgeChanges(changes, edges)), [edges, setEdges]);
  const canConnectNodes = useCallback((sourceId, targetId) => {
    if (!sourceId || !targetId || sourceId === targetId) return false;
    const currentNodes = useGraphStore.getState().nodes;
    const source = currentNodes.find((node) => node.id === sourceId);
    const target = currentNodes.find((node) => node.id === targetId);
    return nodeType(source) !== 'end' && nodeType(target) !== 'start';
  }, []);
  const isValidConnection = useCallback((connection) => canConnectNodes(connection.source, connection.target), [canConnectNodes]);
  const addConnection = useCallback((connection) => {
    if (!canConnectNodes(connection.source, connection.target)) return;
    const currentEdges = useGraphStore.getState().edges;
    const exists = currentEdges.some((edge) =>
      edge.source === connection.source &&
      edge.target === connection.target &&
      edge.sourceHandle === connection.sourceHandle &&
      edge.targetHandle === connection.targetHandle
    );
    if (exists) return;
    pushHistory();
    setEdges(addEdge(connection, currentEdges));
  }, [canConnectNodes, setEdges, pushHistory]);
  const onConnect = useCallback((connection) => {
    connectionStartRef.current = null;
    addConnection(connection);
  }, [addConnection]);

  const eventPoint = (event) => {
    const source = event.changedTouches?.[0] || event;
    return { x: source.clientX, y: source.clientY };
  };

  const nearestTargetHandle = (node, point) => {
    const flowPoint = screenToFlowPosition(point);
    const { width, height } = nodeSize(node);
    const centerX = node.position.x + width / 2;
    const centerY = node.position.y + height / 2;
    const dx = flowPoint.x - centerX;
    const dy = flowPoint.y - centerY;
    if (Math.abs(dx) > Math.abs(dy)) return dx < 0 ? 'left-target' : 'right-target';
    return dy < 0 ? 'top-target' : 'bottom-target';
  };

  const nodeAtPoint = (point) => {
    const element = document.elementFromPoint(point.x, point.y)?.closest?.('.react-flow__node');
    const nodeId = element?.getAttribute('data-id');
    if (nodeId) return useGraphStore.getState().nodes.find((node) => node.id === nodeId);
    const flowPoint = screenToFlowPosition(point);
    return useGraphStore.getState().nodes.find((node) => {
      const width = node.width || node.measured?.width || 180;
      const height = node.height || node.measured?.height || 64;
      return (
        flowPoint.x >= node.position.x &&
        flowPoint.x <= node.position.x + width &&
        flowPoint.y >= node.position.y &&
        flowPoint.y <= node.position.y + height
      );
    });
  };

  const closestEdgeAt = useCallback((flowPoint, ignoredNodeId = null) => {
    let closest = null;
    const currentNodes = useGraphStore.getState().nodes;
    const currentEdges = useGraphStore.getState().edges;
    currentEdges.forEach((edge) => {
      if (ignoredNodeId && (edge.source === ignoredNodeId || edge.target === ignoredNodeId)) return;
      const source = currentNodes.find((node) => node.id === edge.source);
      const target = currentNodes.find((node) => node.id === edge.target);
      if (!source || !target) return;
      if (nodeType(source) === 'end' || nodeType(target) === 'start') return;
      const distance = distanceToSegment(flowPoint, nodeCenter(source), nodeCenter(target));
      if (!closest || distance < closest.distance) closest = { edge, source, target, distance };
    });
    return closest?.distance <= EDGE_INSERT_DISTANCE ? closest : null;
  }, []);

  const onConnectStart = useCallback((_, params) => {
    if (params?.nodeId && params?.handleType === 'source') {
      connectionStartRef.current = params;
    }
  }, []);

  const onConnectEnd = useCallback((event) => {
    const start = connectionStartRef.current;
    connectionStartRef.current = null;
    setConnectTargetId(null);
    if (!start?.nodeId) return;
    const point = eventPoint(event);
    const targetNode = nodeAtPoint(point);
    if (!targetNode || !canConnectNodes(start.nodeId, targetNode.id)) return;
    addConnection({
      source: start.nodeId,
      sourceHandle: start.handleId || 'right-source',
      target: targetNode.id,
      targetHandle: nearestTargetHandle(targetNode, point),
    });
  }, [addConnection, canConnectNodes, screenToFlowPosition]);

  const onMouseMove = useCallback((event) => {
    const start = connectionStartRef.current;
    if (!start?.nodeId) {
      if (connectTargetId) setConnectTargetId(null);
      return;
    }
    const targetNode = nodeAtPoint({ x: event.clientX, y: event.clientY });
    const nextTargetId = targetNode && canConnectNodes(start.nodeId, targetNode.id) ? targetNode.id : null;
    if (nextTargetId !== connectTargetId) setConnectTargetId(nextTargetId);
  }, [canConnectNodes, connectTargetId, screenToFlowPosition]);

  const onMouseLeave = useCallback(() => {
    if (connectTargetId) setConnectTargetId(null);
  }, [connectTargetId]);

  const addNodeAtDrop = useCallback((type, position) => {
    const definition = nodeDefinitions[type];
    if (!definition) return;

    const currentNodes = useGraphStore.getState().nodes;
    const currentEdges = useGraphStore.getState().edges;
    const canInsertOnEdge = type !== 'start' && type !== 'end';
    const insertTarget = canInsertOnEdge ? closestEdgeAt(position) : null;
    const id = `${type}-${crypto.randomUUID()}`;
    const newNode = { id, type, position, data: { label: definition.label, attachedTools: [] } };

    pushHistory();
    if (!insertTarget) {
      setNodes([...currentNodes, newNode]);
      return;
    }

    const newCenter = {
      x: position.x + NODE_DEFAULT_WIDTH / 2,
      y: position.y + NODE_DEFAULT_HEIGHT / 2,
    };
    const sourceCenter = nodeCenter(insertTarget.source);
    const targetCenter = nodeCenter(insertTarget.target);
    const nextEdges = currentEdges.filter((edge) => edge.id !== insertTarget.edge.id);

    setNodes([...currentNodes, newNode]);
    setEdges(addEdge({
      source: insertTarget.edge.source,
      sourceHandle: insertTarget.edge.sourceHandle || handleForDirection(sourceCenter, newCenter, 'source'),
      target: id,
      targetHandle: handleForDirection(newCenter, sourceCenter, 'target'),
    }, addEdge({
      source: id,
      sourceHandle: handleForDirection(newCenter, targetCenter, 'source'),
      target: insertTarget.edge.target,
      targetHandle: insertTarget.edge.targetHandle || handleForDirection(targetCenter, newCenter, 'target'),
    }, nextEdges)));
  }, [closestEdgeAt, pushHistory, setEdges, setNodes]);

  const insertExistingNodeOnEdge = useCallback((node) => {
    const currentNodes = useGraphStore.getState().nodes;
    const currentEdges = useGraphStore.getState().edges;
    const storedNode = currentNodes.find((item) => item.id === node.id);
    const draggedNode = storedNode ? { ...storedNode, ...node, data: storedNode.data } : node;
    if (nodeType(draggedNode) === 'start' || nodeType(draggedNode) === 'end') return false;
    const insertTarget = closestEdgeAt(nodeCenter(draggedNode), draggedNode.id);
    if (!insertTarget) return false;

    const draggedCenter = nodeCenter(draggedNode);
    const sourceCenter = nodeCenter(insertTarget.source);
    const targetCenter = nodeCenter(insertTarget.target);
    const nextEdges = currentEdges.filter((edge) => edge.id !== insertTarget.edge.id);

    pushHistory();
    setEdges(addEdge({
      source: insertTarget.edge.source,
      sourceHandle: insertTarget.edge.sourceHandle || handleForDirection(sourceCenter, draggedCenter, 'source'),
      target: draggedNode.id,
      targetHandle: handleForDirection(draggedCenter, sourceCenter, 'target'),
    }, addEdge({
      source: draggedNode.id,
      sourceHandle: handleForDirection(draggedCenter, targetCenter, 'source'),
      target: insertTarget.edge.target,
      targetHandle: insertTarget.edge.targetHandle || handleForDirection(targetCenter, draggedCenter, 'target'),
    }, nextEdges)));
    return true;
  }, [closestEdgeAt, pushHistory, setEdges]);

  const onNodeDrag = useCallback((_, node) => {
    if (nodeType(node) === 'start' || nodeType(node) === 'end') {
      setDropEdgeId(null);
      return;
    }
    const nextEdgeId = closestEdgeAt(nodeCenter(node), node.id)?.edge.id || null;
    setDropEdgeId((current) => current === nextEdgeId ? current : nextEdgeId);
  }, [closestEdgeAt]);

  const onNodeDragStop = useCallback((_, node) => {
    insertExistingNodeOnEdge(node);
    setDropEdgeId(null);
  }, [insertExistingNodeOnEdge]);

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    const isNodeDrag = Array.from(event.dataTransfer.types || []).includes('application/reactflow');
    if (!isNodeDrag) return;
    const type = event.dataTransfer.getData('application/reactflow');
    if (type === 'start' || type === 'end') {
      setDropEdgeId(null);
      return;
    }
    const flowPoint = screenToFlowPosition({ x: event.clientX, y: event.clientY });
    const nextEdgeId = closestEdgeAt(flowPoint)?.edge.id || null;
    setDropEdgeId((current) => current === nextEdgeId ? current : nextEdgeId);
  }, [closestEdgeAt, screenToFlowPosition]);

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
      if (event.key === 'Delete' || event.key === 'Backspace') {
        const selectedNode = selectedNodeRef.current;
        const selectedEdge = selectedEdgeRef.current;
        if (selectedNode) {
          const id = selectedNode.id;
          event.preventDefault();
          pushHistory();
          setNodes(nodes.filter((n) => n.id !== id));
          setEdges(edges.filter((e) => e.source !== id && e.target !== id));
          return;
        }
        if (selectedEdge) {
          event.preventDefault();
          pushHistory();
          setEdges(edges.filter((e) => e.id !== selectedEdge.id));
        }
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
        nodes={styledNodes}
        edges={styledEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        isValidConnection={isValidConnection}
        onConnectStart={onConnectStart}
        onConnectEnd={onConnectEnd}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        onNodeClick={(_, node) => selectNode(node.id)}
        onEdgeClick={(_, edge) => { selectNode(null); setEdges(edges.map((item) => ({ ...item, selected: item.id === edge.id }))); }}
        onPaneClick={() => { selectNode(null); setEdges(edges.map((item) => ({ ...item, selected: false }))); }}
        onDragOver={onDragOver}
        onDragLeave={() => setDropEdgeId(null)}
        onDrop={(event) => {
          event.preventDefault();
          const type = event.dataTransfer.getData('application/reactflow');
          setDropEdgeId(null);
          if (type) addNodeAtDrop(type, screenToFlowPosition({ x: event.clientX, y: event.clientY }));
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
