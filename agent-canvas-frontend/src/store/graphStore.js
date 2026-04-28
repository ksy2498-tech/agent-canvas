import { create } from 'zustand';
import * as client from '../api/client';

const snapshot = (nodes, edges) => ({
  nodes: JSON.parse(JSON.stringify(nodes)),
  edges: JSON.parse(JSON.stringify(edges)),
});

const toBackendGraph = ({ graphName, nodes, edges, breakpoints }) => ({
  name: graphName,
  description: null,
  nodes: nodes.map((node) => {
    const { label, validationError, ...config } = node.data || {};
    return {
      id: node.id || null,
      node_type: node.type,
      label: label || node.type,
      position_x: node.position?.x || 0,
      position_y: node.position?.y || 0,
      config: {
        ...config,
        breakpoint: breakpoints[node.id] || null,
      },
    };
  }),
  edges: edges.map((edge) => ({
    id: edge.id || null,
    source_node_id: edge.source,
    target_node_id: edge.target,
    source_handle: edge.sourceHandle || '',
    target_handle: edge.targetHandle || '',
    condition_label: edge.label || edge.data?.conditionLabel || null,
  })),
});

const fromBackendGraph = (graph) => ({
  graphId: graph.id || graph.graph_id || 'local-graph',
  graphName: graph.name || 'Untitled Agent',
  nodes: (graph.nodes || []).map((node) => {
    const { breakpoint, ...config } = node.config || {};
    return {
      id: node.id,
      type: node.node_type,
      position: { x: node.position_x || 0, y: node.position_y || 0 },
      data: { ...config, label: node.label, attachedTools: config.attachedTools || [] },
    };
  }),
  edges: (graph.edges || []).map((edge) => ({
    id: edge.id || `${edge.source_node_id}-${edge.target_node_id}`,
    source: edge.source_node_id,
    target: edge.target_node_id,
    sourceHandle: edge.source_handle || null,
    targetHandle: edge.target_handle || null,
    label: edge.condition_label || undefined,
  })),
  breakpoints: Object.fromEntries(
    (graph.nodes || [])
      .filter((node) => node.config?.breakpoint)
      .map((node) => [node.id, node.config.breakpoint]),
  ),
});

const getInitialDarkMode = () => {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem('darkMode') === 'true';
};

const applyDarkMode = (darkMode) => {
  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('dark', darkMode);
  }
};

const initialDark = getInitialDarkMode();
applyDarkMode(initialDark);

export const useGraphStore = create((set, get) => ({
  graphId: 'local-graph',
  graphName: 'Untitled Agent',
  nodes: [],
  edges: [],
  selectedNodeId: null,
  panelMode: null,
  history: [],
  breakpoints: {},
  edgeBreakpoints: {},
  darkMode: initialDark,
  runStatus: 'idle',
  pausedState: null,
  pausedAt: null,
  runningNodeId: null,
  trace: [],
  validationErrors: [],

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),
  setGraphName: (graphName) => set({ graphName }),
  selectNode: (selectedNodeId) => set({ selectedNodeId, panelMode: selectedNodeId ? 'config' : get().panelMode }),
  setPanelMode: (panelMode) => set({ panelMode }),
  setRunningNodeId: (runningNodeId) => set({ runningNodeId }),
  setTrace: (trace) => set({ trace }),

  pushHistory: () =>
    set((state) => ({ history: [...state.history, snapshot(state.nodes, state.edges)].slice(-20) })),
  undo: () =>
    set((state) => {
      const previous = state.history[state.history.length - 1];
      if (!previous) return state;
      return { nodes: previous.nodes, edges: previous.edges, history: state.history.slice(0, -1) };
    }),

  updateNodeData: (nodeId, patch) =>
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === nodeId ? { ...node, data: { ...node.data, ...patch } } : node,
      ),
    })),

  toggleBreakpointOnNode: (nodeId, config = { mode: 'inspect', editableKeys: [] }) =>
    set((state) => {
      const breakpoints = { ...state.breakpoints };
      if (breakpoints[nodeId]) delete breakpoints[nodeId];
      else breakpoints[nodeId] = config;
      return { breakpoints };
    }),
  setBreakpointConfig: (nodeId, config) =>
    set((state) => ({ breakpoints: { ...state.breakpoints, [nodeId]: config } })),
  toggleBreakpointOnEdge: (edgeId) =>
    set((state) => {
      const edgeBreakpoints = { ...state.edgeBreakpoints };
      if (edgeBreakpoints[edgeId]) delete edgeBreakpoints[edgeId];
      else edgeBreakpoints[edgeId] = true;
      return { edgeBreakpoints };
    }),

  validateGraph: () => {
    const { nodes, edges } = get();
    const violations = [];
    const nodeErrors = {};
    const addNodeError = (nodeId, message) => {
      nodeErrors[nodeId] = [...(nodeErrors[nodeId] || []), message];
      violations.push(message);
    };

    const startNodes = nodes.filter((n) => n.type === 'start');
    if (startNodes.length !== 1) {
      const message = 'Graph must contain exactly 1 Start node.';
      violations.push(message);
      startNodes.forEach((node) => {
        nodeErrors[node.id] = [...(nodeErrors[node.id] || []), message];
      });
    }
    if (!nodes.some((n) => n.type === 'end')) violations.push('Graph must contain at least 1 End node.');
    nodes.forEach((node) => {
      const connected = edges.some((edge) => edge.source === node.id || edge.target === node.id);
      if (!connected && nodes.length > 1) addNodeError(node.id, `${node.data?.label || node.type} is isolated.`);
      if (node.type === 'llm' && (!node.data?.apiKey || !node.data?.model)) {
        addNodeError(node.id, `${node.data?.label || 'LLM'} needs API key and model.`);
      }
      if (node.type === 'dbQuery') {
        const aliases = nodes.filter((n) => n.type === 'dbConnection').map((n) => n.data?.alias).filter(Boolean);
        if (!aliases.includes(node.data?.connectionAlias)) addNodeError(node.id, 'DB Query must reference a valid DB connection alias.');
      }
    });

    set((state) => ({
      validationErrors: violations,
      nodes: state.nodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          validationError: nodeErrors[node.id]?.join('\n') || '',
        },
      })),
    }));

    return violations.length === 0;
  },

  saveGraph: async ({ validate = true } = {}) => {
    if (validate && !get().validateGraph()) throw new Error('Validation failed');
    let { graphId } = get();
    const { graphName, nodes, edges, breakpoints, edgeBreakpoints } = get();
    const cleanNodes = nodes.map((node) => ({
      ...node,
      data: { ...node.data, validationError: '' },
    }));

    if (graphId === 'local-graph') {
      const created = await client.createGraph(graphName);
      graphId = created.id || created.graphId;
      if (!graphId) throw new Error('Create graph response did not include an id');
      set({ graphId });
    }

    await client.saveGraph(graphId, toBackendGraph({ graphName, nodes: cleanNodes, edges, breakpoints }));
    return graphId;
  },
  loadGraph: async (id) => {
    const graph = await client.getGraph(id);
    set({ ...fromBackendGraph(graph), edgeBreakpoints: graph.edgeBreakpoints || {} });
  },
  toggleDarkMode: () =>
    set((state) => {
      const darkMode = !state.darkMode;
      window.localStorage.setItem('darkMode', String(darkMode));
      applyDarkMode(darkMode);
      return { darkMode };
    }),
  setRunStatus: (runStatus) => set({ runStatus }),
  setPausedState: (pausedState, pausedAt) => set({ pausedState, pausedAt, runStatus: 'paused' }),
  resumeExecution: async (editedState) => {
    const result = await client.resumeExecution(get().graphId, editedState);
    set({ runStatus: 'running', pausedState: null, pausedAt: null });
    return result;
  },
}));
