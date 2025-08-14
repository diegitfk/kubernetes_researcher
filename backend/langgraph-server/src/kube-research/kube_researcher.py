from langchain_openai.chat_models import ChatOpenAI
from langgraph.graph import StateGraph , MessagesState
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from subgraphs.planner_research.planner_schemas import PlanArgTool
from subgraphs.planner_research.planner_schemas import PlannerStateOutput
from utils.build import build_planner_research_graph
from utils.schemas import TaskResearch, KubeResearcherState
from collections import deque
from typing import Literal, Optional, List, Deque, Dict
import attrs
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

@attrs.define
class KubeResearcherGraph:
    """
            Construye y compila el grafo principal `KubeResearcherGraph`.

            Este grafo integra el subgrafo del planificador y define el flujo de control
            principal. Comienza con la planificación, luego, si se aprueba, transforma
            el plan en una cola de tareas y finaliza. Si se cancela, el proceso termina
            inmediatamente.

            ## Diagrama del Grafo KubeResearcher

            ```text
                ┌─────────────────┐
                │   ENTRY POINT   │
                │(kube_researcher)│
                └────────┬────────┘
                        │
                        ▼
            ┌───────────────────────────────┐
            │      kube_researcher_planner  │
            │      (Sub-Graph)              │
            └───────────────┬───────────────┘
                            │
                            │ Edge Condicional:
                            │ aproved_or_cancelled_plan()
                            │
                    ┌───────┴───────┐
                    │               │
            "plan_as_queue"         "__end__"
            (Si se aprueba)      (Si se cancela)
                    │               │
                    ▼               ▼
            ┌───────────────┐   ┌───────────┐
            │ plan_as_queue │   │    END    │
            │ (Node)        │   │(El grafo │
            └───────────────┘   │ termina)  │
                    │           └───────────┘
                    │
                    ▼
            ┌───────────────┐
            │ FINISH POINT  │
            └───────────────┘
            ```
        """
    reasoning_llm : BaseChatModel
    one_shot_llm : BaseChatModel
    mcp_connection_args : Dict

    #Node
    def plan_as_queue(self , state : KubeResearcherState) -> KubeResearcherState:
        """
        Transforma el plan generado en una Cola de objetos TaskResearch
        con la finalidad de establecer que cada sección del informe es una tarea de investigación
        que se pasara en un futuro a un swarm colectivo de agentes, agregando cada hallazgo de estos a 
        la tarea en la key observability_notes
        ```text
        ┌─────────────────────────────────────────────────────────────────┐
        │                    TRANSFORMACIÓN ITERATIVA                     │
        └─────────────────────────────────────────────────────────────────┘

        PlanSection[0] ──┐
                        │    ┌─────────────────────────────────────────┐
        PlanSection[1] ──┼──▶│          FOR EACH SECTION               │
                        │    │                                         │
        PlanSection[2] ──┼──▶│  1. Crear TaskResearch                  │
                        │    │     ├── id = "taskps_" + section.number │
        PlanSection[3] ──┼──▶│     ├── plan_section = section          │
                        │    │     ├── status = "Pending"              │
                        │    │     └── observability_notes = []        │
        ...              │   │                                         │
                        │    │  2. Agregar a task_queue                │
        PlanSection[N] ──┘   └-────────────────────────────────────────┘
                                            │
                                            ▼
                                    ┌─────────────────┐
                                    │   task_queue    │
                                    │   (Deque)       │
                                    │  ┌───────────┐  │
                                    │  │TaskResearch│ │
                                    │  │   #1       │ │
                                    │  └───────────┘  │
                                    │  ┌───────────┐  │
                                    │  │TaskResearch│ │
                                    │  │   #2       │ │
                                    │  └───────────┘  │
                                    │      ...        │
                                    │  ┌───────────┐  │
                                    │  │TaskResearch│ │
                                    │  │   #N       │ │
                                    │  └───────────┘  │
                                    └─────────────────┘
        ```
        Estructura TaskResearch Generada
        ```text
            TaskResearch
            ├── id: str                    ← "taskps_{section.number}"
            ├── plan_section: PlanSection  ← Referencia completa a la sección
            ├── status: Literal           ← "Pending" (estado inicial)
            └── observability_notes: List ← [] (lista vacía para futuros hallazgos)
        ```
        Flujo de Cola de Tareas
        ```text
        ANTES                                    DESPUÉS
        ┌──────────────────┐                     ┌──────────────────┐
         KubeResearcherState                     KubeResearcherState
        ├──────────────────┤                     ├──────────────────┤
        │ plan: PlanArgTool│ ──── TRANSFORM ───▶ │ queue_tasks:     │
        │   └─ plan: [     │                     │   ┌────────────┐ │
        │       Section1,  │                     │   │TaskResearch│ │
        │       Section2,  │                     │   │ (Section1) │ │
        │       Section3   │                     │   ├────────────┤ │
        │     ]            │                     │   │TaskResearch│ │
        │                  │                     │   │ (Section2) │ │
        │ queue_tasks: ∅  │                     │   ├────────────┤ │
        │ queue_result: ∅ │                     │   │TaskResearch│ │
        └──────────────────┘                     │   │ (Section3) │ │
                                                 │   └────────────┘ │
                                                 │                  │
                                                 │ queue_result:    │
                                                 │   ┌────────────┐ │
                                                 │   │   EMPTY    │ │
                                                 │   │   DEQUE    │ │
                                                 │   └────────────┘ │
                                                 └──────────────────┘
        ```
        Patrones de Identificación
        ```text
            ID Pattern: "taskps_" + section.number
                            │         │
                            │         └─ Número de sección del plan
                            └─ Prefijo identificador de tarea del plan sectionado

            Ejemplos:
            Section 1 → TaskResearch.id = "taskps_1"
            Section 5 → TaskResearch.id = "taskps_5" 
            Section 12 → TaskResearch.id = "taskps_12"
        ```
        Estado de Observabilidad
        ESTADO INICIAL DE OBSERVABILIDAD
        ```text
        ┌─────────────────────────────────────────┐
        │         TaskResearch                    │
        ├─────────────────────────────────────────┤
        │ observability_notes: []                 │
        │                                         │
        │ ┌─────────────────────────────────────┐ │
        │ │        PREPARADO PARA               │ │
        │ │      SWARM INJECTION                │ │
        │ │                                     │ │
        │ │ Agentes del swarm agregarán:        │ │
        │ │ ├─ ObservabilityNote #1             │ │
        │ │ ├─ ObservabilityNote #2             │ │
        │ │ └─ ObservabilityNote #N             │ │
        │ └─────────────────────────────────────┘ │
        └─────────────────────────────────────────┘
        ```
        Arquitectura del Swarm (Futuro)
        ```text
        ┌──────────────────────────────────────────────────────────────────┐
        │                        SWARM PROCESSING                          │
        └──────────────────────────────────────────────────────────────────┘

        queue_tasks          SWARM AGENTS                    queue_result_tasks
        ┌──────────┐    ┌─────────────────────────┐         ┌──────────────┐
        │TaskRes#1 │───▶│ Agent-kubernets         │────────▶│ TaskRes#1    │
        ├──────────┤    │ Agent-prometheus        │         │ + Notes      │
        │TaskRes#2 │───▶│ Agent-graphana          │────────▶├──────────────┤
        ├──────────┤    │ Agent-Performance       │         │ TaskRes#2    │
        │TaskRes#3 │───▶│ Agent-Security          │────────▶│ + Notes      │
        ├──────────┤    │ Agent-Network           │         ├──────────────┤
        │   ...    │    └─────────────────────────┘         │     ...      │
        └──────────┘                                        └──────────────┘
            │                                                      ▲
            │            ┌─────────────────────┐                   │
            └───────────▶│  MCP TOOLS CONTEXT  │───────────────────┘
                         │                     │
                         │ kubectl, APIs,      │
                         │ monitoring tools    │
                         └─────────────────────┘
        ```
        """
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
    #Conditional Edges
    def aproved_or_cancelled_plan(self , state : PlannerStateOutput) -> Literal["plan_as_queue" , "__end__"]:
        """
        ## Representación visual

        ```text
        ┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
        │             │     │                  │ YES │                 │
        │ approval_   │────▶│ approved_or_     │────▶│ plan_queue_     │
        │ node        │     │ cancelled_plan() │     │ node            │
        │             │     │                  │     │                 │
        └─────────────┘     └──────────────────┘     └─────────────────┘
                                    │
                                    │ NO
                                    ▼
                                ┌─────────┐
                                │   END   │
                                │ (Graph  │
                                │Termina- │
                                │tion)    │
                                └─────────┘
        ```
        """
        print(f"---STATE PLAN APROVED OR CANCELLED----->>>>>> \n{state}")
        if state.action.status == "APPROVED":
            return "plan_as_queue"
        elif state.action.status == "CANCELLED":
            return "__end__"

    def __call__(self) -> CompiledStateGraph:
        planner_graph = build_planner_research_graph(reasoning_llm=self.reasoning_llm , one_shot_llm=self.one_shot_llm)

        kube_researcher_graph = StateGraph(
            name="Kube Researcher",
            state_schema=KubeResearcherState
        )
        kube_researcher_graph.add_node("kube_researcher_planner" , planner_graph)
        kube_researcher_graph.add_node("plan_as_queue" , self.plan_as_queue)
        kube_researcher_graph.set_entry_point("kube_researcher_planner")
        kube_researcher_graph.add_conditional_edges("kube_researcher_planner" , self.aproved_or_cancelled_plan)
        kube_researcher_graph.set_finish_point("plan_as_queue")
        return kube_researcher_graph.compile(checkpointer=MemorySaver() , debug=True)
        

