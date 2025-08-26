from typing import Any, Annotated, Callable, List
from langchain_core.runnables import Runnable
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import BaseTool
from langchain_core.messages import filter_messages, ToolMessage
from langchain_mcp_adapters.sessions import Connection, StreamableHttpConnection
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph_supervisor import create_supervisor , create_handoff_tool

from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.runtime import Runtime

from pydantic import BaseModel, Field, PrivateAttr

from subgraphs.supervisor_obs.common_tools import create_register_observability_note_for_agent
from utils.schemas import TaskResearch


class MCPSConnection(BaseModel):
    id : str
    connection_args : StreamableHttpConnection


class AgentConfig(BaseModel):
    """
        Este es un objeto serializable que se obtendra en un futuro de la base de datos, dado que si se desea
        construir un agente por runtime debe ser serializable y stateful modificable externalizado al codigo
    """
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


    async def _build_research_agents(self) -> list[CompiledStateGraph]:
        """
        Herramienta encargada de generar a partir de las conexiones MCP actuales react agents
        especializados por MCP.
        """
        multi_server_client = self._build_mcp_connections()
        agents : list[CompiledStateGraph] = []
        for agent in self.config_agents:
            mcp_tools : list[BaseTool] = await multi_server_client.get_tools(agent.mcp_connection.id)
            research_agent = create_react_agent(
                model=self.model,
                tools=mcp_tools,
                name=agent.name
            )
        ...


    def build_supervisor(self) -> CompiledStateGraph:
        ...





    
    