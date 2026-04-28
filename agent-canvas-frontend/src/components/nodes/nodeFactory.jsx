import {
  Brain,
  Braces,
  Code2,
  Database,
  FileArchive,
  FileDown,
  FileUp,
  Flag,
  GitBranch,
  Globe,
  ListFilter,
  MessageSquare,
  Play,
  Power,
  Route,
  Save,
  Server,
  Square,
  Text,
  Wand2,
} from 'lucide-react';
import BaseNode from './BaseNode';

export const nodeDefinitions = {
  start: { label: 'Start', category: 'start', icon: Play, summary: () => 'Entry point' },
  end: { label: 'End', category: 'end', icon: Flag, summary: () => 'Terminal node' },
  llm: { label: 'LLM Call', category: 'llm', icon: Brain, summary: (d) => d.model || 'No model configured' },
  code: { label: 'Code', category: 'code', icon: Code2, summary: (d) => (d.code || '').split('\n').find(Boolean) || 'Python code' },
  router: { label: 'Router', category: 'router', icon: Route, summary: (d) => d.routingMode || 'llm-based' },
  condition: { label: 'Condition', category: 'condition', icon: GitBranch, summary: (d) => d.expression || 'No condition' },
  breakpoint: { label: 'Breakpoint', category: 'breakpoint', icon: Square, summary: (d) => d.mode || 'pause and inspect' },
  sessionLoad: { label: 'Session Load', category: 'session', icon: FileDown, summary: (d) => `Output: ${d.outputKey || 'messages'}` },
  sessionSave: { label: 'Session Save', category: 'session', icon: Save, summary: (d) => d.mode || 'append' },
  stateSet: { label: 'State Set', category: 'state', icon: Braces, summary: (d) => `${d.values?.length || 0} keys` },
  stateGet: { label: 'State Get', category: 'state', icon: ListFilter, summary: (d) => d.key || 'No key' },
  dbConnection: { label: 'DB Connection', category: 'db', icon: Server, summary: (d) => d.alias || d.dbType || 'Connection' },
  dbQuery: { label: 'DB Query', category: 'db', icon: Database, summary: (d) => d.connectionAlias || 'No connection' },
  artifactStore: { label: 'Artifact Store', category: 'artifact', icon: FileUp, summary: (d) => d.backend || 'Local' },
  artifactLoad: { label: 'Artifact Load', category: 'artifact', icon: FileArchive, summary: (d) => d.outputKey || 'artifact' },
  httpRequest: { label: 'HTTP Request', category: 'io', icon: Globe, summary: (d) => `${d.method || 'GET'} ${d.url || ''}` },
  inputTransform: { label: 'Input Transform', category: 'io', icon: Wand2, summary: () => 'Transform input' },
  outputFormat: { label: 'Output Format', category: 'io', icon: Text, summary: (d) => d.formatType || 'plain' },
  nlp: { label: 'NLP Node', category: 'nlp', icon: MessageSquare, summary: (d) => d.engine || 'Kiwi' },
};

export const createNodeComponent = (type) => {
  const definition = nodeDefinitions[type];
  return function Node(props) {
    return (
      <BaseNode {...props} icon={definition.icon} label={definition.label} category={definition.category}>
        <div className="max-w-[220px] truncate">{definition.summary(props.data || {})}</div>
      </BaseNode>
    );
  };
};
