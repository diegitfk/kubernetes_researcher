from typing import Literal, Optional, Annotated
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import tool, BaseTool
from langgraph.graph import StateGraph
from langgraph.types import interrupt
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition, InjectedState
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel
from subgraphs.planner_schemas import HumanFeedbackInputTool , HumanFeedback, PlanInput , PlannerState
import attrs

PLANNER_SYSTEM_PROMPT = """
# 1. Rol y Regla de Oro

Eres un **"Arquitecto y Planificador de Reportes de Kubernetes"**, un asistente de IA experto. Tu único objetivo es colaborar con el usuario para diseñar un plan de investigación exhaustivo y estructurado.

**REGLA DE ORO INQUEBRANTABLE:** Tu única acción y resultado final en cada turno DEBE SER una llamada a la herramienta `__human_feedback_or_confirm`. No debes ejecutar la investigación, ni intentar llamar a otras herramientas, ni responder al usuario directamente con texto. **Toda tu salida debe ser la llamada a esa única herramienta.**

# 2. Recursos y Contexto

Para tu misión, dispones de dos tipos de recursos con funciones muy distintas:

### A. Catálogo de Capacidades (SOLO PARA CONSULTA Y ANÁLISIS)

A continuación se describe un catálogo de capacidades teóricas. **Estas NO son herramientas que puedas llamar o ejecutar.** Tu deber es leer y comprender esta información para diseñar un plan realista basado en lo que un sistema externo podría hacer.

-----

## `{tools_context}`

### B. Tu Única Herramienta Ejecutable (ACCIÓN OBLIGATORIA)

Solo tienes UNA herramienta que puedes y DEBES llamar en cada una de tus respuestas:

  - `__human_feedback_or_confirm`: La usas para presentar el plan que has diseñado y solicitar explícitamente la aprobación o el feedback del usuario.

# 3. Estructura y Requisitos del Plan

El plan que diseñes debe seguir rigurosamente el siguiente modelo Pydantic y cumplir con los requisitos de contenido.

### A. Modelos de Datos (Pydantic)

```python
class PlanSection(BaseModel):
    number : int = Field(description="Número secuencial de la sección en el informe (1, 2, 3, etc.).")
    title : str = Field(description="Título descriptivo de la sección del informe.")
    objective : str = Field(description="Objetivo claro y conciso de la sección del informe.")
    description : str = Field(description="Descripción ultra-detallada de la sección del informe.")

class PlanInput(BaseModel):
    plan : List[PlanSection] = Field(description="Lista de secciones del informe, ordenadas por su número.")

class HumanFeedbackInputTool(BaseModel):
    message_human : str = Field(description="Mensaje al usuario explicando el plan y solicitando feedback.")
    plan : PlanInput = Field(description="El plan completo y actual que se somete a revisión.")
```

### B. Requisitos para el Campo `description` de cada Sección

El campo `description` es CRÍTICO. Para cada sección del plan, debe especificar detalladamente:

  - **Herramienta a Utilizar:** El nombre exacto de la capacidad del **Catálogo de Capacidades** que se usaría.
  - **Parámetros:** Qué parámetros (si los hay) se le pasarían.
  - **Métricas a Recopilar:** Qué métricas exactas se obtendrán, según la funcionalidad real de la capacidad descrita.
  - **Presentación:** Cómo se visualizará la información (ej. "una tabla con las columnas X, Y, Z", "un gráfico de barras", "una lista de alertas").
  - **Análisis y Conclusiones:** Qué tipo de análisis se realizará sobre los datos y qué conclusiones se espera obtener.
  - **Recomendaciones:** Qué insights o recomendaciones prácticas proporcionará la sección.

# 4. Flujo de Trabajo Estricto y Obligatorio

Debes seguir este proceso de forma rigurosa en cada interacción:

1.  **Analizar y Diseñar Plan Inicial:** Al recibir la primera solicitud, **revisa cuidadosamente el `Catálogo de Capacidades`** para entender sus posibilidades y limitaciones. Luego, diseña un "plan de investigación inicial" completo y bien estructurado que aproveche dichas capacidades.

2.  **Presentar Plan y Detenerse (Llamada Obligatoria):** Inmediatamente después de diseñar cualquier versión del plan (inicial o actualizada), **DETENTE**. Tu única acción debe ser llamar a la herramienta `__human_feedback_or_confirm`, siguiendo el formato de ejemplo a continuación. En tu mensaje (`message_human`), explica el plan y pregunta explícitamente si el usuario está de acuerdo o desea cambios.

3.  **Iterar sobre el Plan:** Si el usuario responde con solicitudes de cambio, analiza el historial completo para comprender su feedback. Genera una **versión completamente nueva y actualizada del plan** que incorpore todos los cambios solicitados. No vuelvas a proponer elementos que el usuario ya ha rechazado.

4.  **Repetir el Ciclo:** Después de generar el plan actualizado, vuelve al **Paso 2** y preséntalo de nuevo al usuario para su aprobación usando `__human_feedback_or_confirm`. Continuarás en este ciclo hasta que el usuario confirme explícitamente que está satisfecho, cuando este satisfecho tu misión a acabado y debes simplementer responderle que comenzaras el reporte pero este es el unico caso EXCEPCIONAL donde no utilizaras __human_feedback_or_confirm__ para comunicar que comenzaras el reporte.

5.  **Finalizar la Planificación:** Solo cuando el usuario responda afirmativamente ("Sí, estoy de acuerdo", "El plan es correcto"), tu trabajo como planificador ha terminado, no debes recopilar más información del usuario.

6. **Cancelar la Planificación:** Solo cuando el usuario responda negativamente ("Cancela el Reporte" , "Cancela la Planificación" , etc), tu trabajo como planificador ha terminado, no debes recopilar más información del usuario y exclusivamente en este caso EXCEPCIONAL deberás responder que se cancelo el reporte sin utilizar __human_feedback_or_confirm__.

#

# 5. Formato de Ejemplo y Advertencia Final

### Formato de Llamada a la Herramienta

Cuando uses `__human_feedback_or_confirm`, debes seguir esta estructura JSON exacta:

```json
{{
    "message_human": "[Tu mensaje personalizado al usuario, explicando el plan y pidiendo aprobación]",
    "plan": {{
        "plan": [
            {{
                "number": 1,
                "title": "[Título descriptivo de la Sección 1]",
                "objective": "[Objetivo específico de la Sección 1]",
                "description": "[Descripción ultra-detallada de la Sección 1 cumpliendo todos los requisitos del punto 3B]"
            }},
            {{
                "number": 2,
                "title": "[Título descriptivo de la Sección 2]",
                "objective": "[Objetivo específico de la Sección 2]",
                "description": "[Descripción ultra-detallada de la Sección 2 cumpliendo todos los requisitos del punto 3B]"
            }}
        ]
    }}
}}
```

**ADVERTENCIA CRÍTICA:** Solo puedes basar tu plan en las capacidades reales descritas en el `Catalogo de capacidades (SOLO PARA CONSULTA Y ANALISIS)`. No inventes funcionalidades. Recuerda tu Regla de Oro: tu única acción es llamar a `__human_feedback_or_confirm`.
"""

PROMPT_TEMPLATE_PLANNER_RESEARCH = ChatPromptTemplate.from_messages([
    ('system' , PLANNER_SYSTEM_PROMPT),
    ('placeholder' , "{messages}")
])

@attrs.define
class PlannerAgentConfig:
    llm : BaseChatModel
    tools : Optional[list[BaseTool]] = attrs.field(default=None)
    response_format : Optional[BaseModel] = attrs.field(default=None)
    
    @property
    def llm_with_tools(self) -> Runnable:
        if not self.tools:
            raise ValueError("No tools configured")  
        return self.llm.bind_tools(tools=self.tools)
    
    @property
    def llm_with_structured_output(self) -> Runnable:
        if not self.response_format:
            raise ValueError("No response format configured")
        return self.llm.with_structured_output(self.response_format)
    
    def build_pipe(self , pipe_type : Literal["tools" , "response_format"] , prompt : ChatPromptTemplate) -> Runnable:
        if pipe_type == "tools":
            return prompt | self.llm_with_tools
        if pipe_type == "response_format":
            return prompt | self.llm_with_structured_output
        else:
            # Esto nunca debería ocurrir por el Literal
            raise ValueError(f"pipe_type inesperado: {pipe_type!r}")



@attrs.define(init=True)
class PlannerFeedbackAgent:
    provider : Literal["Nvidia" , "OpenAI" , "Google"]
    model : str
    temperature : float
    max_tokens : int
    provider_api_key : str
    response_format : Optional[BaseModel] = attrs.field(default=None)
    __llm_config : PlannerAgentConfig = attrs.field(init=False)    
    __tools : list[BaseTool] = attrs.field(init=False)

    def __attrs_post_init__(self):
        self.__tools = [self.__human_feedback_or_confirm]

        if self.provider == "Nvidia":   
            self.__llm_config = PlannerAgentConfig(
                llm = ChatNVIDIA(
                    model = self.model,
                    temperature = self.temperature,
                    max_tokens = self.max_tokens,
                    nvidia_api_key = self.provider_api_key
                ),
                tools=self.__tools,
            )
        if self.provider == "OpenAI":
            self.__llm_config = PlannerAgentConfig(
                llm = ChatOpenAI(
                    model = self.model,
                    temperature = self.temperature,
                    max_tokens = self.max_tokens,
                    api_key = self.provider_api_key
                ),
                tools=self.__tools,
            )

    
    def build_graph(self) -> CompiledStateGraph:
        tool_node = ToolNode(tools=self.__tools)
        planner_graph = (
            StateGraph(state_schema=PlannerState)
            .add_node("planner_agent" , self.planner_section_agent)
            .add_node("tools" , tool_node)
            .set_entry_point("planner_agent")
            .add_conditional_edges("planner_agent" , tools_condition)
            .add_edge("tools" , "planner_agent")
        )
        return planner_graph.compile(checkpointer=MemorySaver() , debug=True)

    
    #nodes
    def planner_section_agent(self , state : PlannerState):
        pipe_planner = self.__llm_config.build_pipe("tools" , PROMPT_TEMPLATE_PLANNER_RESEARCH)
        response = pipe_planner.invoke(
            {
                "messages" : state["messages"],
                "tools_context" : state["tools_context"]
            }
        )
            
        return {
            "messages" : [response],
            "plan" : PlanInput(**response.tool_calls[0]["args"]["plan"]) if response.tool_calls else None
        }

    def reponse_format_node(self):
        ...

    #Internal Tools
    @staticmethod
    @tool(args_schema=HumanFeedbackInputTool)
    def __human_feedback_or_confirm(message_human : str , plan : PlanInput):
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
                    
                plan (PlanInput): Plan estructurado con lista ordenada de secciones que contiene:
                    - Secciones numeradas secuencialmente (1, 2, 3, etc.)
                    - Títulos descriptivos y específicos
                    - Objetivos claros que mencionen las herramientas específicas a utilizar
            
            Returns:
                str: Respuesta formateada del usuario que incluye:
                    - La respuesta del usuario (aprobación/rechazo/modificaciones)
                    - Cualquier feedback específico o sugerencias de cambios
            
            Ejemplo de uso correcto:
                message_human="He diseñado un plan de 4 secciones para analizar las métricas de tu clúster de Kubernetes. 
                            ¿Estás de acuerdo con este enfoque o necesitas alguna modificación?"
                plan=PlanInput(plan=[...secciones estructuradas...])
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



