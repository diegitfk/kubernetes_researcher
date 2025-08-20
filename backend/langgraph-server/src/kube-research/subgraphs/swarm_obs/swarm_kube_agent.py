from langgraph.graph.state import CompiledStateGraph
from langgraph.graph import MessagesState, add_messages
from langchain_core.messages import AnyMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_community.tools import BaseTool
from typing import TypedDict, Annotated, Self, Dict , Any
import attrs

from langchain_core.tools import tool
from subgraphs.swarm_obs.swarm_base_agent import BaseSwarmAgent, BaseAgentConfig
from subgraphs.swarm_obs.swarm_common_tools import create_register_observability_note_for_agent
from utils.schemas import TaskResearch , ObservabilityNoteInjectedAgent

#testing_tools
@tool
def get_nodes():
    """
        Obtiene los nodos y estadisticas de los nodos de un cluster de kubernetes
    """
    ...
@tool
def get_pods_metrics(namespace : str):
    """
        Obtiene las metricas de los pods de un cluster de kubernetes
    """
    ...


class KubernetesObservabilityState(TypedDict):
    current_task : TaskResearch
    kube_messages : Annotated[list[AnyMessage] , add_messages]

@attrs.define
class KubernetesObservabilityAgent(BaseSwarmAgent):
    agent_name : str = attrs.field(default="Kubernetes Observability Agent")
    mcp_config : Dict[str , Any]
    reasoning_llm : BaseChatModel
    one_shot_llm : BaseChatModel
    __llm_config : BaseAgentConfig = attrs.field(init=False)
    __tools : list[BaseTool] = attrs.field(init=False)
    
    #nodes
    def llm_agent(self , state : KubernetesObservabilityState , config):
        self.__llm_config.build_pipe("tools")
    
    def post_hook_push_note(self , *args , **kwargs):
        pass

    async def init(self) -> Self:   
        self.__tools = [create_register_observability_note_for_agent(self.agent_name)] + await self.load_mcp_tools_from_config()
        self.__llm_config = BaseAgentConfig(
            reasoning_llm=self.reasoning_llm,
            one_shot_llm=self.one_shot_llm,
            tools=self.__tools
        )
        return self
    
    async def load_mcp_tools_from_config(self) -> list[BaseTool]:
        return [get_nodes , get_pods_metrics]

    async def __call__(self, *args, **kwargs) -> CompiledStateGraph:
        pass
    
