from langchain_openai.chat_models import ChatOpenAI
from langgraph.graph import StateGraph , MessagesState
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from subgraphs.planner_research.planner_schemas import PlanArgTool
from subgraphs.planner_research.planner_schemas import PlannerStateOutput
from utils.build import build_planner_research_graph
from utils.schemas import TaskResearch
from collections import deque
from typing import Literal, Optional, List, Deque

def aproved_or_cancelled_plan(state : PlannerStateOutput) -> Literal["plan_as_queue" , "__end__"]:
    print(f"---STATE PLAN APROVED OR CANCELLED----->>>>>> \n{state}")
    if state.action.status == "APPROVED":
        return "plan_as_queue"
    elif state.action.status == "CANCELLED":
        return "__end__"

llm = ChatOpenAI(
    model="google/gemini-2.5-flash-lite",
    base_url="https://openrouter.ai/api/v1",
    reasoning_effort="medium",
    streaming=True,
    api_key="...",
)
class KubeResearcherState(MessagesState):
    plan : Optional[PlanArgTool] #Plan generado por el agente planificador de kubernetes
    queue_tasks : Optional[Deque[TaskResearch]] #Tareas que se enviaran al SWARM
    queue_result_tasks : Optional[Deque[TaskResearch]] #Tareas que ya fueron abordadas por el SWARM
    tools_ctx : str #Contexto de las herramientas

def plan_as_queue(state : KubeResearcherState) -> KubeResearcherState:
    task_queue = deque()
    plan = state["plan"]

    for section in plan.plan:
        task_queue.append(TaskResearch(
            id=f"taskps_{section.number}",
            plan_section=section,
            status="Pending",
            observability_notes=list()
        ))        

    return {
        "queue_tasks" : task_queue,
        "queue_results_tasks" : deque()
    }
planner_graph = build_planner_research_graph(llm=llm)

kube_researcher_graph = StateGraph(
    name="Kube Researcher",
    state_schema=KubeResearcherState
)
kube_researcher_graph.add_node("kube_researcher_planner" , planner_graph)
kube_researcher_graph.add_node("plan_as_queue" , plan_as_queue)
kube_researcher_graph.set_entry_point("kube_researcher_planner")
kube_researcher_graph.add_conditional_edges("kube_researcher_planner" , aproved_or_cancelled_plan)
kube_researcher_graph.set_finish_point("plan_as_queue")

kube_researcher = kube_researcher_graph.compile(checkpointer=MemorySaver() , debug=True)
