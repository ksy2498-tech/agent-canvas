import { X } from 'lucide-react';
import { useGraphStore } from '../../store/graphStore';
import { nodeDefinitions } from '../nodes/nodeFactory.jsx';
import StartNodePanel from './panels/StartNodePanel';
import EndNodePanel from './panels/EndNodePanel';
import LLMNodePanel from './panels/LLMNodePanel';
import MCPToolPanel from './panels/MCPToolPanel';
import CodeNodePanel from './panels/CodeNodePanel';
import RouterNodePanel from './panels/RouterNodePanel';
import ConditionNodePanel from './panels/ConditionNodePanel';
import BreakpointPanel from './panels/BreakpointPanel';
import SessionLoadPanel from './panels/SessionLoadPanel';
import SessionSavePanel from './panels/SessionSavePanel';
import StateSetPanel from './panels/StateSetPanel';
import StateGetPanel from './panels/StateGetPanel';
import RuntimeSetPanel from './panels/RuntimeSetPanel';
import RuntimeGetPanel from './panels/RuntimeGetPanel';
import DBConnectionPanel from './panels/DBConnectionPanel';
import DBQueryPanel from './panels/DBQueryPanel';
import ArtifactStorePanel from './panels/ArtifactStorePanel';
import ArtifactLoadPanel from './panels/ArtifactLoadPanel';
import HTTPRequestPanel from './panels/HTTPRequestPanel';
import InputTransformPanel from './panels/InputTransformPanel';
import OutputFormatPanel from './panels/OutputFormatPanel';
import NLPNodePanel from './panels/NLPNodePanel';
import BreakpointSettings from './shared/BreakpointSettings';

const panels = {
  start: StartNodePanel,
  end: EndNodePanel,
  llm: LLMNodePanel,
  mcpTool: MCPToolPanel,
  code: CodeNodePanel,
  router: RouterNodePanel,
  condition: ConditionNodePanel,
  breakpoint: BreakpointPanel,
  sessionLoad: SessionLoadPanel,
  sessionSave: SessionSavePanel,
  stateSet: StateSetPanel,
  stateGet: StateGetPanel,
  runtimeSet: RuntimeSetPanel,
  runtimeGet: RuntimeGetPanel,
  dbConnection: DBConnectionPanel,
  dbQuery: DBQueryPanel,
  artifactStore: ArtifactStorePanel,
  artifactLoad: ArtifactLoadPanel,
  httpRequest: HTTPRequestPanel,
  inputTransform: InputTransformPanel,
  outputFormat: OutputFormatPanel,
  nlp: NLPNodePanel,
};

export default function ConfigPanel() {
  const { nodes, selectedNodeId, setPanelMode, selectNode, updateNodeData } = useGraphStore();
  const node = nodes.find((item) => item.id === selectedNodeId);
  if (!node) return null;
  const Panel = panels[node.type] || StartNodePanel;
  const title = nodeDefinitions[node.type]?.label || node.type;
  return (
    <aside className="fixed right-0 top-0 z-30 h-full w-[360px] overflow-y-auto border-l border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900">
      <div className="sticky top-0 z-10 border-b border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-semibold">{title}</h2>
          <button className="icon-btn" onClick={() => { selectNode(null); setPanelMode(null); }}><X size={17} /></button>
        </div>
        <input className="field font-medium" value={node.data?.label || ''} onChange={(e) => updateNodeData(node.id, { label: e.target.value })} />
      </div>
      <div className="p-4">
        <Panel node={node} />
        {node.type !== 'breakpoint' ? <BreakpointSettings nodeId={node.id} /> : null}
      </div>
    </aside>
  );
}
