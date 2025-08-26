from langchain_core.tools import tool, BaseTool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langchain_core.messages import ToolMessage
from typing import Deque, Literal, Optional, List, Annotated
from datetime import date
from utils.schemas import ObservabilityNote , ObservabilityNoteInjectedAgent , TaskResearch

def create_register_observability_note_for_agent(agent_name : str):
    """
    Este resulta ser un wrapper que devuelve la tool, con un contexto inyectado de las notas generadas por el agente con su nombre
    agregado con la finalidad de mantener una coherencia entre el responsable de generar la nota de observabilidad, evitando sesgos por 
    parte del modelo.
    """
    @tool
    def register_observability_note(
    # Core fields  
    severity: Literal["info", "warning", "critical"], 
    description: str,
      
    # Kubernetes context  
    namespace: Optional[str],
    resource_type: Optional[Literal["pod", "deployment", "service", "node", "pvc", "configmap", "secret"]], 
    resource_name: Optional[str],
      
    # Metrics  
    metric: Optional[str],
    metric_value: Optional[float],
    metric_threshold: Optional[float],  
    metric_unit: Optional[str],
      
    # Classification  
    category: Optional[Literal["performance", "security", "availability", "cost", "compliance"]],
    impact_level: Optional[Literal["low", "medium", "high"]],
    urgency: Optional[Literal["low", "medium", "high", "immediate"]],
      
    # Recommendations and resolution  
    recommendations: Optional[List[str]], 
    root_cause: Optional[str],
    status: Optional[Literal["new", "acknowledged", "in_progress", "resolved"]],
      
    # Additional context  
    tags: Optional[List[str]],
    confidence_score: Optional[float]
    ) -> ObservabilityNoteInjectedAgent:
        """
        Herramienta utilizada para registrar una nota de observabilidad sobre la tarea.  
        Esta nota permite documentar hallazgos, métricas y contexto relacionado con la
        observabilidad de un recurso, incidente o condición particular detectada por ti
        en el trayecto que tratas de contribuir a la tarea de observabilidad solicitada.

        Args:
            severity (Literal["info", "warning", "critical"]): Nivel de severidad del hallazgo.
            description (str): Descripción detallada del hallazgo.
            namespace (Optional[str]): Namespace de Kubernetes donde se detectó el hallazgo.
            resource_type (Optional[Literal["pod", "deployment", "service", "node", "pvc", "configmap", "secret"]]): Tipo de recurso afectado.
            resource_name (Optional[str]): Nombre del recurso afectado.
            metric (Optional[str]): Nombre de la métrica asociada al hallazgo.
            metric_value (Optional[float]): Valor actual de la métrica.
            metric_threshold (Optional[float]): Umbral definido para la métrica.
            metric_unit (Optional[str]): Unidad de medida de la métrica (por ejemplo: %, ms, MB).
            category (Optional[Literal["performance", "security", "availability", "cost", "compliance"]]): Categoría principal del hallazgo.
            impact_level (Optional[Literal["low", "medium", "high"]]): Nivel de impacto estimado.
            urgency (Optional[Literal["low", "medium", "high", "immediate"]]): Nivel de urgencia para atender el hallazgo.
            recommendations (Optional[List[str]]): Lista de acciones o pasos sugeridos para mitigar o resolver el hallazgo.
            root_cause (Optional[str]): Descripción de la causa raíz identificada.
            status (Optional[Literal["new", "acknowledged", "in_progress", "resolved"]]): Estado actual del hallazgo.
            tags (Optional[List[str]]): Lista de etiquetas para clasificar o filtrar el hallazgo.
            confidence_score (Optional[float]): Nivel de confianza (0 a 1) en la precisión del hallazgo.

        Returns:
            ObservabilityNoteInjectedAgent: Objeto estandarizado que encapsula toda la información
            registrada sobre el hallazgo de observabilidad, incluyendo el nombre del agente que lo reporta.
        """
        new_obervability_note = ObservabilityNoteInjectedAgent(
            agent_name=agent_name,
            severity=severity,
            description=description,
            namespace=namespace,
            resource_type=resource_type,
            resource_name=resource_name,
            metric=metric,
            metric_value=metric_value,
            metric_threshold=metric_threshold,
            metric_unit=metric_unit,
            category=category,
            impact_level=impact_level,
            urgency=urgency,
            recommendations=recommendations,
            root_cause=root_cause,
            status=status,
            tags=tags,
            confidence_score=confidence_score
            )
        return new_obervability_note
    return register_observability_note

        