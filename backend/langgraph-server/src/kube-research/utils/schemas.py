from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict , List , Literal , Optional, Any, Deque
from langgraph.graph import MessagesState
from subgraphs.planner_research.planner_schemas import PlanSection, PlanArgTool


class ObservabilityNote(BaseModel):
    severity: Literal["info", "warning", "critical"] = Field(..., description="Nivel de severidad del hallazgo")
    metric: Optional[str] = Field(default=None, description="Nombre de la métrica asociada al hallazgo")
    description: str = Field(..., description="Descripción detallada del hallazgo")
    recommendations: Optional[List[str]] = Field(default=None, description="Lista de recomendaciones para mitigar o resolver el hallazgo")

class ObservabilityNoteInjectedAgent(BaseModel):
    agent_name: str = Field(..., description="Nombre del agente de observabilidad que genera el hallazgo")
    timestamp: datetime = Field(default_factory=datetime.now, description="Fecha y hora del hallazgo")

class TaskResearch(BaseModel):
    id : str
    plan_section : PlanSection
    status : Literal["Pending" , "Done" , "Pass"]
    observability_notes : List[ObservabilityNote]

class KubeResearcherState(MessagesState):
    plan : Optional[PlanArgTool] #Plan generado por el agente planificador de kubernetes
    queue_tasks : Optional[Deque[TaskResearch]] #Tareas que se enviaran al SWARM
    queue_result_tasks : Optional[Deque[TaskResearch]] #Tareas que ya fueron abordadas por el SWARM
    tools_ctx : str #Contexto de las herramientas

