from langchain_core.tools import tool, BaseTool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command, Send
from langgraph_supervisor.handoff import METADATA_KEY_HANDOFF_DESTINATION
from langchain_core.messages import AIMessage , ToolMessage
from langgraph_supervisor.handoff import (
    _normalize_agent_name,
    _remove_non_handoff_tool_calls,
    METADATA_KEY_HANDOFF_DESTINATION,
)
from typing import Deque, Literal, Optional, List, Annotated, cast
import uuid
from datetime import date
from utils.schemas import ObservabilityNote , ObservabilityNoteInjectedAgent , TaskResearch
from textwrap import dedent

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

        
def create_handoff_research_tool(
    agent_name: str,
    description: str,
    handle_handoff_message: bool = True,
):
    """
    Crea una herramienta que transfiere la conversación a un agente especializado y
    le pasa una subtarea de investigación (sub_task) en forma de mensaje adicional.

    Args:
        agent_name: nombre del agente destino.
        description: descripción de la herramienta.
        handle_handoff_message: si True, añade mensajes de handoff + la subtarea al historial;
                               si False, omite el último AIMessage (similar al comportamiento
                               de create_handoff_tool cuando no se desean repetir mensajes).
    Returns:
        Una función decorada con @tool que produce el Command necesario para hacer el handoff.
    """
    tool_name = f"transfer_to_{_normalize_agent_name(agent_name)}_research"

    @tool(tool_name, description=description)
    def handoff_research_tool(
        sub_task: Annotated[
            str,
            dedent(
                """\
                Una subtarea de investigación, detallada y
                con contexto estructurado en JSON para que el agente especializado
                pueda abordarla e investigar sobre ella
                """
            ),
        ],
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        # Mensaje de herramienta que indica éxito de la transferencia y metadata con destino.
        tool_message = ToolMessage(
            content=f"Transferencia exitosa al agente especializado {agent_name}",
            name=tool_name,
            tool_call_id=tool_call_id,
            response_metadata={METADATA_KEY_HANDOFF_DESTINATION: agent_name},
        )

        # Construimos un AIMessage que contiene la subtarea de investigación para que
        # el agente especializado la vea en su historial como instrucción/contexto.
        research_message = AIMessage(
            content=sub_task,
            name="supervisor",
            id=str(uuid.uuid4()),
        )

        # Último mensaje AI en el historial del state
        last_ai_message = cast(AIMessage, state["messages"][-1])

        # Manejo de handoffs paralelos (cuando el último AIMessage tiene múltiples tool_calls)
        last_tool_calls = getattr(last_ai_message, "tool_calls", []) or []
        if len(last_tool_calls) > 1:
            # Tomamos todos los mensajes excepto el último (ya que es el que contiene tool_calls)
            handoff_messages = state["messages"][:-1]
            if handle_handoff_message:
                # Añadimos el AIMessage filtrado (solo con el tool_call relevante), el ToolMessage
                # y la instrucción de investigación
                handoff_messages.extend(
                    (
                        _remove_non_handoff_tool_calls(last_ai_message, tool_call_id),
                        tool_message,
                        research_message,
                    )
                )

            # Devolvemos un Command que use Send para permitir combinación de múltiples handoffs
            return Command(
                graph=Command.PARENT,
                goto=[Send(agent_name, {**state, "messages": handoff_messages})],
            )

        # Caso de handoff único (no paralelo)
        else:
            if handle_handoff_message:
                # Añadimos el ToolMessage y la instrucción de investigación al final del historial
                handoff_messages = state["messages"] + [tool_message, research_message]
            else:
                # Si no queremos agregar handoff messages, eliminamos el último AIMessage
                # (similar al comportamiento de create_handoff_tool)
                handoff_messages = state["messages"][:-1]

            return Command(
                goto=agent_name,
                graph=Command.PARENT,
                update={**state, "messages": handoff_messages},
            )

    # Metadata para poder identificar el destino del handoff desde fuera si es necesario
    handoff_research_tool.metadata = {METADATA_KEY_HANDOFF_DESTINATION: agent_name}
    return handoff_research_tool