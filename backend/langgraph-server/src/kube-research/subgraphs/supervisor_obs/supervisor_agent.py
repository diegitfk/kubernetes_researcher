from typing import Any, Annotated, List , Dict, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import BaseTool
from langchain_mcp_adapters.sessions import Connection, StreamableHttpConnection
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph_supervisor import create_supervisor

from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.runtime import Runtime

from pydantic import BaseModel, Field, PrivateAttr
from textwrap import dedent

from subgraphs.supervisor_obs.common_tools import create_register_observability_note_for_agent, create_handoff_research_tool
from subgraphs.supervisor_obs.research_workflow import ResearchAgent
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

class SupervisorBuilder(BaseModel):
    model : BaseChatModel
    config_agents : Annotated[
        list[AgentConfig] , Field(
            description="""
            Una lista de los agentes de se configuraran dentro del SWARM de agentes de observabilidad
            este serializable se obtiene directamente de la base de datos al momento de construir el grafo
            """
    )]
    __sub_agents : Optional[Dict[str , CompiledStateGraph]] = PrivateAttr()

    def _build_mcp_connections(self) -> MultiServerMCPClient:
        connections = dict()
        for conf in self.config_agents:
            connections[conf.mcp_connection.id] = conf.mcp_connection.connection_args
        return MultiServerMCPClient(connections=connections)


    async def _build_research_agents(self) -> Dict[str , CompiledStateGraph]:
        """
        Herramienta encargada de generar a partir de las conexiones MCP actuales agentes
        especializados por MCP, esta función devuelve un diccionario con grafos de estados la 
        compilados:
        ```json
        {
            "kube_observer" : CompiledStateGraph,
            "prometheus_agent" : CompiledStateGraph,
            "graphana_agent" : CompiledStateGraph,
            ...
        }
        ```
        es necesaria esta estructura para que el supervisor sepa que grado de estado compilado corresponde
        a que agente, con la finalidad de no dificultar la creación de handoffs tools que el agente tendra
        para los subagentes espcializados.
        """
        multi_server_client = self._build_mcp_connections()
        agents : Dict[str , CompiledStateGraph] = dict()
        for agent in self.config_agents:
            mcp_tools : list[BaseTool] = await multi_server_client.get_tools(agent.mcp_connection.id)
            research_agent = ResearchAgent(
                agent_name=agent.name,
                agent_description=agent.description,
                model=self.model,
                tools=mcp_tools
            ).compile()
            agents[agent.name] = research_agent
        self.__sub_agents = agent
        return agents


    def build_supervisor(self) -> CompiledStateGraph:
        ...
            





    
    