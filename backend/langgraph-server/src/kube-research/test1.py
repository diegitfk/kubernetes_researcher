from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from subgraphs.supervisor_obs.research_workflow import ResearchAgent
from subgraphs.supervisor_obs.supervisor_agent import SupervisorBuilder, AgentConfig, MCPSConnection
from subgraphs.planner_research.planner_schemas import PlanSection
from utils.schemas import TaskResearch
import uuid
import asyncio
import httpx

def my_httpx_factory():
    """Factory para crear clientes httpx configurados."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(30.0), 
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
    )

reasoning_llm = ChatOpenAI(
        model="google/gemini-2.5-pro",
        base_url="https://openrouter.ai/api/v1",
        reasoning_effort="medium",
        streaming=True,
        api_key="...",
    )
one_shot_llm = ChatOpenAI(
        model="google/gemini-2.0-flash",
        base_url="https://openrouter.ai/api/v1",
        reasoning_effort="medium",
        streaming=True,
        api_key="...",
    )

async def amain():
    k8_observer_config = AgentConfig(
        id=str(uuid.uuid4()),
        name="K8's Observer",
        description="""
        Un Agente de investigación encargado de conectarte al Cluster de kubernetes para obtener información del cluster 
        de kubernetes vía Kube-API, con esto puede lograr obtener una serie de información para contribuir a la investigación.
        """,
        objective="Obtener información importante sobre el cluster de kubernets para investigarlo", 
        mcp_connection=MCPSConnection(
                id=str(uuid.uuid4()),
                connection_args={
                    "url" : "http://localhost:3000/mcp",
                    "transport" : "streamable_http"
                }
        )
    )
    supervisor_builder = SupervisorBuilder(
        reasoning_llm=reasoning_llm,
        one_shot_llm=one_shot_llm, 
        config_agents=[k8_observer_config]
    )
    await supervisor_builder.build()
    supervisor_research = supervisor_builder.compile(name="research_supervisor")
    print(supervisor_research.get_graph().draw_ascii())




if __name__ == "__main__":
    asyncio.run(amain())
    