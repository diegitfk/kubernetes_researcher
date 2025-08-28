from typing import Any, Annotated, List , Dict, Optional, Self
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate , PromptTemplate
from langchain_community.tools import BaseTool
from langchain_mcp_adapters.sessions import Connection, StreamableHttpConnection
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph_supervisor import create_supervisor

from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.runtime import Runtime

from pydantic import BaseModel, Field, PrivateAttr
from textwrap import dedent
from pathlib import Path
import tomllib

from subgraphs.supervisor_obs.common_tools import create_register_observability_note_for_agent, create_handoff_research_tool
from subgraphs.supervisor_obs.research_workflow import ResearchAgent
from utils.schemas import TaskResearch
PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts.toml"
with open(PROMPT_PATH, "rb") as f:
    PROMPTS = tomllib.load(f)

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

class SupervisorState(AgentState):
    current_task : TaskResearch

class SupervisorBuilder(BaseModel):
    reasoning_llm : BaseChatModel
    one_shot_llm : BaseChatModel
    config_agents : Annotated[
        list[AgentConfig] , Field(
            description="""
            Una lista de los agentes de se configuraran dentro del SWARM de agentes de observabilidad
            este serializable se obtiene directamente de la base de datos al momento de construir el grafo
            """
    )]
    __mcp_connections : Optional[MultiServerMCPClient] = PrivateAttr(default=None)
    __sub_agents_ctx : Dict[str,str] = PrivateAttr(default_factory=dict)
    __sub_agents : Dict[str , CompiledStateGraph]= PrivateAttr(default_factory=dict)
    __is_built : bool = PrivateAttr(default=False)

    def __dynamic_prompt(self , state : SupervisorState , config : Dict[str , Any]) -> ChatPromptTemplate:
        """Callable interno de la clase, totalmente privado encargado de la construcción de un SystemPrompt para el agente supervisor"""
        
        prompt = PromptTemplate(
            template=PROMPTS["supervisor"]["base_research_supervisor"],
            input_variables=[
                "agents_ctx",
                "current_notes",
                "current_task",
            ]
        )
        task_dump = state["current_task"].model_dump(exclude={"observability_notes"})
        prompt_format = prompt.format(
            current_notes=state["current_task"].observability_notes,
            current_task=task_dump,
            agents_ctx=self.__sub_agents_ctx
        )
        return [{"role": "system", "content": prompt_format}] + state["messages"]

    def __build_mcp_connections(self) -> Self:
        connections = dict()
        for conf in self.config_agents:
            connections[conf.mcp_connection.id] = conf.mcp_connection.connection_args
        self.__mcp_connections = MultiServerMCPClient(connections=connections)
        return self


    async def __build_research_agents(self) -> Self:
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
        agents : Dict[str , CompiledStateGraph] = dict()
        for agent in self.config_agents:
            mcp_tools : list[BaseTool] = await self.__mcp_connections.get_tools(agent.mcp_connection.id)
            research_agent = ResearchAgent(
                agent_name=agent.name,
                agent_description=agent.description,
                model=self.reasoning_llm,
                tools=mcp_tools
            ).compile()
            agents[agent.name] = research_agent
            self.__sub_agents_ctx[agent.name] = agent.description

        self.__sub_agents = agents
        self.__is_built = True

        return self

    async def build(self) -> Self:
        self.__build_mcp_connections()
        await self.__build_research_agents()
        return self

    def compile(self) -> CompiledStateGraph:
        if not self.__is_built:
            raise ValueError("Builder not fully constructed. Call build() or build_research_agents() first")
        
        if not self.__sub_agents:
            raise ValueError("No sub-agents available for compilation")
        
        handoff_tools = []

        for agent_name in self.__sub_agents.keys():
            handoff_tools.append(create_handoff_research_tool(  
            agent_name=agent_name ,
            description=dedent(f"""\
                Herramienta para asignar una subtarea (A partir de la tarea actual que estas abordando)
                al agente especializado de investigación {agent_name}
            """)
            ))


        supervisor_agent = create_supervisor(
            model=self.one_shot_llm,
            agents=list(self.__sub_agents.values()),
            tools=handoff_tools,
            prompt=self.__dynamic_prompt,
            supervisor_name="research_supervisor"
        )
        return supervisor_agent.compile()
    
    @property
    def is_ready(self) -> bool:
        """Indica si el builder está listo para compilar."""
        return self.__is_built and bool(self.__sub_agents)

    def get_agent_names(self) -> list[str]:
        """Retorna los nombres de los agentes configurados."""
        return list(self.__sub_agents.keys()) if self.__sub_agents else []
            





    
    