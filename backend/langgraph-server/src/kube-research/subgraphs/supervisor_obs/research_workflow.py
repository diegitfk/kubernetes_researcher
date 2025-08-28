from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableSerializable
from langchain_core.messages import BaseMessage, AIMessage , ToolMessage, filter_messages
from langchain_core.tools.render import render_text_description_and_args
from langchain_core.prompts import ChatPromptTemplate

from typing import Optional, List, Literal, TypedDict, Annotated , Sequence

from langgraph.graph import StateGraph, add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt.chat_agent_executor import Prompt
from langgraph.prebuilt import ToolNode
from langgraph.typing import ContextT
from langgraph.runtime import Runtime
from langgraph._internal._runnable import RunnableCallable

from pydantic import BaseModel , Field , PrivateAttr
from textwrap import dedent
from pathlib import Path
import tomllib

from utils.schemas import TaskResearch, ObservabilityNoteInjectedAgent
from subgraphs.supervisor_obs.common_tools import create_register_observability_note_for_agent

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts.toml"

def factory_prompt_template() -> str:
    with open(PROMPT_PATH, "rb") as f:
        data = tomllib.load(f)

    return ChatPromptTemplate.from_messages([
        ("system" , data["supervisor"]["base_research_obs_agent"]),
        ("placeholder" , "{messages}")
        ])

class ResearchSchema(TypedDict):
    messages : Annotated[Sequence[BaseMessage], add_messages] #Lista de mensajes que puede visualizar el agente
    current_task : str # La tarea actual que el agente de investigación debe realizar
    current_notes : List[ObservabilityNoteInjectedAgent] #Notas de investigaciones que se han hecho en el proceso de investigación

class ResearchAgent(BaseModel):
    agent_name : str
    agent_description : str
    model : BaseChatModel
    tools : Optional[List[BaseTool]] = Field(default=[])
    __description_tools : Optional[str] = PrivateAttr(default=None)
    __prompt : ChatPromptTemplate = PrivateAttr(default_factory=factory_prompt_template)
    __llm_runnable : RunnableSerializable = PrivateAttr()

    def __build_runnable(self) -> RunnableSerializable:
        fixed_tools = [create_register_observability_note_for_agent(agent_name=f"{self.agent_name}")]
        return self.__prompt | self.model.bind_tools(tools=self.tools + fixed_tools)

    def model_post_init(self, context) -> None:
        self.__llm_runnable = self.__build_runnable()
        self.__description_tools = render_text_description_and_args(self.tools)

            

    def call_model(self , state : ResearchSchema , config) -> ResearchSchema:
        response = self.__llm_runnable.invoke(
            input={
                "agent_name" : f"{self.agent_name}" , 
                "agent_description" : f"{self.agent_description}",
                "specialized_tools" : f"{self.__description_tools}",
                "current_task" : f"{state["current_task"]}",
                "current_notes" : f"{state["current_notes"]}"
                },
            config=config
            )
        response.name = self.agent_name
        return {
            "messages" : [response]
        }

    async def acall_model(self , state : ResearchSchema , context : Runtime[ContextT]) -> ResearchSchema:
            response = await self.__llm_runnable.ainvoke(
                input={
                    "agent_name" : f"{self.agent_name}" , 
                    "agent_description" : f"{self.agent_description}",
                    "specialized_tools" : f"{self.__description_tools}",
                    "current_task" : f"{state["current_task"]}",
                    "current_notes" : f"{state["current_notes"]}"
                    }
                )
            response.name = self.agent_name
            return {
                "messages" : [response]
            }

    def should_continue(self, state : ResearchSchema) -> Literal["tools" , "__end__"]:
        last_message = state["messages"][-1]
        if isinstance(last_message , AIMessage) and last_message.tool_calls:
            return "tools"
        return "__end__"

    def push_note_hook(self , state : ResearchSchema) -> ResearchSchema:
        last_tool_messages : list[ToolMessage] = filter_messages(messages=state["messages"] , include_types=ToolMessage)
        if len(last_tool_messages) == 0:
            return state
        last_message = last_tool_messages[-1]
        if last_message.name == "register_observability_note" and isinstance(last_message.content , ObservabilityNoteInjectedAgent):
            return {
                "current_notes" : state["current_notes"] + [last_message.content]
            }
        return state

    
    def compile(self) -> CompiledStateGraph:
        tool_node = ToolNode(self.tools)
        research_workflow = StateGraph(state_schema=ResearchSchema)
        research_workflow.add_node("llm_call" , RunnableCallable(self.call_model , self.acall_model))
        research_workflow.add_node("tools" , tool_node)
        research_workflow.add_node("push_note_hook" , self.push_note_hook)
        research_workflow.set_entry_point("llm_call")
        research_workflow.add_edge("tools" , "push_note_hook")
        research_workflow.add_edge("push_note_hook" , "llm_call")
        research_workflow.add_conditional_edges("llm_call" , self.should_continue)
        return research_workflow.compile(debug=True)