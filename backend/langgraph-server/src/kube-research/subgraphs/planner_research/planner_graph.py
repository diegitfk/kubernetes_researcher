from typing import Literal, Optional, Annotated
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import tool, BaseTool
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage, filter_messages, ToolMessage
from langchain_core.tools.render import render_text_description_and_args
from langgraph.types import interrupt
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition, InjectedState
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel
from subgraphs.planner_research.planner_config import PlannerAgentConfig
from subgraphs.planner_research.planner_schemas import HumanFeedbackInputTool , HumanFeedback, PlanArgTool , PlannerState , PlannerStateOutput , PlannerFormatOutput
from pathlib import Path
import attrs
import tomllib

PROMPT_PATH = Path(__file__).parent.parent / "prompts.toml"

with open(PROMPT_PATH, "rb") as f:
    data = tomllib.load(f)

PLANNER_SYSTEM_PROMPT = data["planner_prompts"]["system_prompt"]
PLANNER_FORMAT_PROMPT = data["planner_prompts"]["format_prompt"]


PROMPT_TEMPLATE_PLANNER_RESEARCH = ChatPromptTemplate.from_messages([
    ('system' , PLANNER_SYSTEM_PROMPT),
    ('placeholder' , "{messages}")
])
PROMPT_TEMPLATE_PLANNER_FORMAT = ChatPromptTemplate.from_messages([
    ("system" , PLANNER_FORMAT_PROMPT)
])

@attrs.define(init=True)
class PlannerResearchGraph:
    reasoning_llm : BaseChatModel
    one_shot_llm : BaseChatModel
    __llm_config : PlannerAgentConfig = attrs.field(init=False)    
    __tools : list[BaseTool] = attrs.field(init=False)

    def __attrs_post_init__(self):
        self.__tools = [self.__human_feedback_or_confirm]
        self.__llm_config = PlannerAgentConfig(
                reasoning_llm=self.reasoning_llm,
                one_shot_llm=self.one_shot_llm,
                tools=self.__tools,
                response_format=PlannerFormatOutput
            )
    
    def __call__(self) -> CompiledStateGraph:
        tool_node = ToolNode(tools=self.__tools)
        planner_graph = (
            StateGraph(
                name="Research Planner",
                state_schema=PlannerState,
                output_schema=PlannerStateOutput
                )
            .add_node("planner_agent" , self.planner_section_agent)
            .add_node("tools" , tool_node)
            .add_node("response_format" , self.response_format_node)
            .set_entry_point("planner_agent")
            .add_conditional_edges("planner_agent" , tools_condition , {"tools" : "tools" , "__end__" : "response_format"})
            .add_edge("tools" , "planner_agent")
        )
        return planner_graph.compile()

    
    #nodes
    def planner_section_agent(self , state : PlannerState , config) -> PlannerState:
        messages = state.get("messages", [])
        # Si no hay mensajes, crear un mensaje inicial para que el agente comience
        if not messages:
            messages = [
                HumanMessage(content="Por favor, diseña un plan de investigación para analizar el estado y métricas de mi clúster de Kubernetes.")
            ]
        pipe_planner = self.__llm_config.build_pipe("tools" , PROMPT_TEMPLATE_PLANNER_RESEARCH)
        response = pipe_planner.invoke(
            {
                "messages" : messages,
                "tools_context" : state["tools_ctx"],
            },
            config
        )

        return {
            "messages" : state["messages"] + [response],
            "plan" : PlanArgTool(**response.tool_calls[0]["args"]["plan"]) if response.tool_calls else state["plan"]
        }

    def response_format_node(self , state : PlannerState , config) -> PlannerStateOutput:
        tool_calls = filter_messages(messages=state["messages"] , include_types=ToolMessage)
        pipe_sto = self.__llm_config.build_pipe("response_format" , PROMPT_TEMPLATE_PLANNER_FORMAT)
        response = pipe_sto.invoke({
            "human_response" : tool_calls[-1].content,
            "current_plan" : state["plan"].model_dump()
        } , config)
        return {
            "action" : response,
            "plan" : state["plan"],
            "messages" : state["messages"]
        }

    #Internal Tools
    @staticmethod
    @tool(args_schema=HumanFeedbackInputTool)
    def __human_feedback_or_confirm(message_human : str , plan : PlanArgTool):
        """
            HERRAMIENTA CRÍTICA Y OBLIGATORIA para solicitar feedback humano sobre el plan de investigación propuesto.
            
            Esta herramienta DEBE ser utilizada:
            - Inmediatamente después de generar cualquier versión del plan (inicial o actualizada)
            - Antes de proceder con cualquier otra acción
            - Para obtener confirmación explícita del usuario antes de finalizar
            
            IMPORTANTE: El planificador DEBE detenerse y esperar la respuesta del usuario después de usar esta herramienta.
            No debe continuar con ninguna acción hasta recibir el feedback.
            
            Args:
                message_human (str): Mensaje claro y directo al usuario que debe:
                    - Presentar el plan de forma comprensible
                    - Explicar brevemente las secciones propuestas
                    - Solicitar explícitamente aprobación o cambios
                    - Usar un tono profesional pero accesible
                    
                plan (PlanArgTool): Plan estructurado con lista ordenada de secciones que contiene:
                    - Secciones numeradas secuencialmente (1, 2, 3, etc.)
                    - Títulos descriptivos y específicos
                    - Objetivos claros que mencionen las herramientas específicas a utilizar
                    - Descripción detallada de las secciones
            
            Returns:
                str: Respuesta formateada del usuario que incluye:
                    - La respuesta del usuario (aprobación/rechazo/modificaciones)
                    - Cualquier feedback específico o sugerencias de cambios
            
            Ejemplo de uso correcto:
                message_human="He diseñado un plan de 4 secciones para analizar las métricas de tu clúster de Kubernetes. 
                            ¿Estás de acuerdo con este enfoque o necesitas alguna modificación?"
                plan=PlanArgTool(plan=[...secciones estructuradas...])
        """
        feedback = interrupt({
            "message" : message_human,
            "plan" : plan
        })

        feedback_parsed = HumanFeedback(feedback=feedback["feedback"] , answer=feedback["answer"])
        return f"""
        HUMAN FEEDBACK:
        El humano respondio lo siguiente : {feedback_parsed.answer}
        El humano retroalimento lo siguiente: {feedback_parsed.feedback if feedback_parsed.feedback else "No retroalimento nada"}
        """



