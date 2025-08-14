from typing import Optional , Literal
from langchain_core.runnables import Runnable
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import BaseTool
from pydantic import BaseModel
import attrs

@attrs.define
class PlannerAgentConfig:
    reasoning_llm : BaseChatModel
    one_shot_llm : BaseChatModel
    tools : Optional[list[BaseTool]] = attrs.field(default=None)
    response_format : Optional[BaseModel] = attrs.field(default=None)
    
    @property
    def llm_with_tools(self) -> Runnable:
        if not self.tools:
            raise ValueError("No tools configured")  
        return self.reasoning_llm.bind_tools(tools=self.tools)
    
    @property
    def llm_with_structured_output(self) -> Runnable:
        if not self.response_format:
            raise ValueError("No response format configured")
        return self.one_shot_llm.with_structured_output(self.response_format)
    
    def build_pipe(self , pipe_type : Literal["tools" , "response_format"] , prompt : ChatPromptTemplate) -> Runnable:
        if pipe_type == "tools":
            return prompt | self.llm_with_tools
        if pipe_type == "response_format":
            return prompt | self.llm_with_structured_output
        else:
            # Esto nunca debería ocurrir por el Literal
            raise ValueError(f"pipe_type inesperado: {pipe_type!r}")