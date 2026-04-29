import { create } from 'zustand';
import * as client from '../api/client';

const updateServer = (servers, id, patch) => servers.map((server) => (server.id === id ? { ...server, ...patch } : server));
const replaceServer = (servers, originalId, server) => {
  const next = withUiFields(server);
  const replaced = servers.map((item) => (item.id === originalId ? next : item));
  return replaced.some((item) => item.id === next.id) ? replaced : [...replaced, next];
};
const normalizeTools = (payload) => (Array.isArray(payload) ? payload : payload?.tools || []);
const normalizeServers = (payload) => {
  if (Array.isArray(payload)) {
    return {
      globalServers: payload.filter((server) => server.scope === 'global').map(withUiFields),
      graphServers: payload
        .filter((server) => server.scope !== 'global')
        .reduce((groups, server) => ({ ...groups, [server.scope]: [...(groups[server.scope] || []), withUiFields(server)] }), {}),
    };
  }
  return {
    globalServers: (payload?.globalServers || []).map(withUiFields),
    graphServers: Object.fromEntries(
      Object.entries(payload?.graphServers || {}).map(([scope, servers]) => [scope, servers.map(withUiFields)]),
    ),
  };
};

function withUiFields(server) {
  return {
    ...server,
    ...(server.config || {}),
    status: server.status || 'disconnected',
    tools: server.tools || [],
  };
}

const upsertServer = (state, server, scope = 'global') => {
  const next = withUiFields(server);
  if (scope === 'global') {
    const exists = state.globalServers.some((s) => s.id === next.id);
    return { globalServers: exists ? updateServer(state.globalServers, next.id, next) : [...state.globalServers, next] };
  }
  const current = state.graphServers[scope] || [];
  const exists = current.some((s) => s.id === next.id);
  return { graphServers: { ...state.graphServers, [scope]: exists ? updateServer(current, next.id, next) : [...current, next] } };
};

const replaceSavedServer = (state, originalId, server, scope = 'global') => {
  if (scope === 'global') {
    return { globalServers: replaceServer(state.globalServers, originalId, server) };
  }
  const current = state.graphServers[scope] || [];
  return { graphServers: { ...state.graphServers, [scope]: replaceServer(current, originalId, server) } };
};

const updateServerEverywhere = (state, id, patch) => ({
  globalServers: updateServer(state.globalServers, id, patch),
  graphServers: Object.fromEntries(
    Object.entries(state.graphServers).map(([graphId, servers]) => [graphId, updateServer(servers, id, patch)]),
  ),
});

const assertOk = (result, fallbackMessage) => {
  if (result?.status === 'error') {
    throw new Error(result.message || fallbackMessage);
  }
  return result;
};

export const useMCPStore = create((set, get) => ({
  globalServers: [],
  graphServers: {},

  loadServers: async () => {
    const data = await client.listMCPServers();
    set(normalizeServers(data));
  },
  saveServer: async (server, scope = 'global') => {
    const originalId = server.id;
    const saved = await client.saveMCPServer(server, scope);
    const next = { ...server, ...saved, status: 'disconnected', tools: server.tools || [] };
    set((state) => replaceSavedServer(state, originalId, next, scope));
    return withUiFields(next);
  },
  addServer: async (server, scope = 'global') => {
    const originalId = server.id;
    const saved = await client.saveMCPServer(server, scope);
    const next = { ...server, ...saved, status: 'disconnected', tools: server.tools || [] };
    set((state) => replaceSavedServer(state, originalId, next, scope));
    return withUiFields(next);
  },
  upsertLocalServer: (server, scope = 'global') =>
    set((state) => upsertServer(state, server, scope)),
  removeServer: async (id, scope = 'global') => {
    await client.deleteMCPServer(id);
    set((state) =>
      scope === 'global'
        ? { globalServers: state.globalServers.filter((server) => server.id !== id) }
        : { graphServers: { ...state.graphServers, [scope]: (state.graphServers[scope] || []).filter((server) => server.id !== id) } },
    );
  },
  testConnection: async (server, scope = 'global') => {
    try {
      const result = assertOk(await client.testMCPConnection(server, scope), 'Connection failed');
      set((state) => updateServerEverywhere(state, server.id, { status: 'connected' }));
      return result;
    } catch (error) {
      set((state) => updateServerEverywhere(state, server.id, { status: 'error' }));
      throw error;
    }
  },
  fetchTools: async (server, scope = 'global') => {
    try {
      const result = assertOk(await client.fetchMCPTools(server, scope), 'Could not fetch tools');
      const tools = normalizeTools(result);
      set((state) => updateServerEverywhere(state, server.id, { tools, status: 'connected' }));
      return tools;
    } catch (error) {
      set((state) => updateServerEverywhere(state, server.id, { status: 'error' }));
      throw error;
    }
  },
  getServersForGraph: (graphId) => [...get().globalServers, ...(get().graphServers[graphId] || [])],
}));
