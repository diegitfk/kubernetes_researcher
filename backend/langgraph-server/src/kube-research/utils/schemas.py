from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict , List , Literal , Optional, Any, Deque
from langgraph.graph import MessagesState
from subgraphs.planner_research.planner_schemas import PlanSection, PlanArgTool


class ObservabilityNote(BaseModel):  
    # Core fields  
    severity: Literal["info", "warning", "critical"] = Field(..., description="Nivel de severidad del hallazgo")  
    description: str = Field(..., description="Descripción detallada del hallazgo")   
      
    # Kubernetes context  
    namespace: Optional[str] = Field(default=None, description="Namespace de Kubernetes")  
    resource_type: Optional[Literal["pod", "deployment", "service", "node", "pvc", "configmap", "secret"]] = Field(default=None)  
    resource_name: Optional[str] = Field(default=None, description="Nombre del recurso afectado")  
      
    # Metrics  
    metric: Optional[str] = Field(default=None, description="Nombre de la métrica")  
    metric_value: Optional[float] = Field(default=None, description="Valor actual")  
    metric_threshold: Optional[float] = Field(default=None, description="Umbral configurado")  
    metric_unit: Optional[str] = Field(default=None, description="Unidad de medida")  
      
    # Classification  
    category: Optional[Literal["performance", "security", "availability", "cost", "compliance"]] = Field(default=None)  
    impact_level: Optional[Literal["low", "medium", "high"]] = Field(default=None)  
    urgency: Optional[Literal["low", "medium", "high", "immediate"]] = Field(default=None)  
      
    # Recommendations and resolution  
    recommendations: Optional[List[str]] = Field(default=None, description="Recomendaciones de mitigación")  
    root_cause: Optional[str] = Field(default=None, description="Causa raíz identificada")  
    status: Optional[Literal["new", "acknowledged", "in_progress", "resolved"]] = Field(default="new")  
      
    # Additional context  
    tags: Optional[List[str]] = Field(default=None, description="Etiquetas adicionales")  
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confianza del hallazgo")

class ObservabilityNoteInjectedAgent(ObservabilityNote):
    agent_name: str = Field(..., description="Nombre del agente de observabilidad que genera el hallazgo")
    timestamp: datetime = Field(default_factory=datetime.now, description="Fecha y hora del hallazgo")

class TaskResearch(BaseModel):
    id : str
    plan_section : PlanSection
    status : Literal["Pending" , "Done" , "Pass"]
    observability_notes : List[ObservabilityNoteInjectedAgent]

class KubeResearcherState(MessagesState):
    plan : Optional[PlanArgTool] #Plan generado por el agente planificador de kubernetes
    queue_tasks : Optional[Deque[TaskResearch]] #Tareas que se enviaran al SWARM
    queue_result_tasks : Optional[Deque[TaskResearch]] #Tareas que ya fueron abordadas por el SWARM
    tools_ctx : str #Contexto de las herramientas

