from typing import Any, Annotated, Callable, List
from langchain_core.runnables import Runnable
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import BaseTool
from langchain_core.messages import filter_messages, ToolMessage
from langchain_mcp_adapters.sessions import Connection, StreamableHttpConnection
from langchain_mcp_adapters.client import MultiServerMCPClient

from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.runtime import Runtime

from pydantic import BaseModel, Field, PrivateAttr

from subgraphs.supervisor_obs.supervisor_common_tools import create_register_observability_note_for_agent
from utils.schemas import TaskResearch


class MCPSConnection(BaseModel):
    id : str
    connection_args : StreamableHttpConnection


class AgentConfig(BaseModel):
    id : str
    name : str
    description : str
    objective : str
    mcp_connection : MCPSConnection

class ResearchState(AgentState):
    current_task : Any
    current_notes : List[Any]

class ObservabilitySupervisorBuilder(BaseModel):
    model : BaseChatModel
    config_agents : Annotated[
        list[AgentConfig] , Field(
            description="""
            Una lista de los agentes de se configuraran dentro del SWARM de agentes de observabilidad
            este serializable se obtiene directamente de la base de datos al momento de construir el grafo
            """
    )]

    def _build_mcp_connections(self) -> MultiServerMCPClient:
        connections = dict()
        for conf in self.config_agents:
            connections[conf.mcp_connection.id] = conf.mcp_connection.connection_args
        return MultiServerMCPClient(connections=connections)

    def _build_global_push_note(self) -> Callable:
        def research_push_note_hook(state : ResearchState) -> ResearchState:
            tool_calls : list[ToolMessage] = filter_messages(state["messages"] , include_types=ToolMessage)
            if not tool_calls:
                return state
            last_tool_call = tool_calls[-1]
            if last_tool_call.name != "register_observability_note":
                return state
            return {
                "current_notes" : state["current_notes"] + [last_tool_call.content]
            }
        return research_push_note_hook

    async def _build_research_agents(self) -> list[CompiledStateGraph]:
        """
        Herramienta encargada de generar a partir de las conexiones MCP actuales react agents
        especializados por MCP.
        """
        multi_server_client = self._build_mcp_connections()
        agents : list[CompiledStateGraph] = []
        for agent in self.config_agents:
            mcp_tools : list[BaseTool] = await multi_server_client.get_tools(agent.mcp_connection.id)
            research_tool : list[BaseTool] = [create_register_observability_note_for_agent(agent.name)]
            research_agent = create_react_agent(
                model=self.model,
                tools=mcp_tools + research_tool,
                name=agent.name
            )
        ...


    def build_supervisor(self) -> CompiledStateGraph:
        ...





    
    