from pydantic import BaseModel, Field
from langgraph.graph import MessagesState
from langgraph.prebuilt import InjectedState
from typing import List, Optional , Literal, Annotated


class PlanSection(BaseModel):
    number : int = Field(description="Número de la sección en el informe puede ser 1 , 2 , 3 , etc.")
    title : str = Field(description="Título de la sección del informe")
    objective : str = Field(description="Objetivo de la sección del informe")
    description : str = Field(description="Descripción detallada de la sección del informe")

class PlanInput(BaseModel):
    plan : List[PlanSection] = Field(description="Lista de secciones del informe ordenadas por su número")

class HumanFeedbackInputTool(BaseModel):
    message_human : str = Field(description="Mensaje al usuario sobre el plan")
    plan : PlanInput = Field(description="Plan actual generado")

class HumanFeedback(BaseModel):
    feedback : Optional[str] = Field(default=None)
    answer : Optional[Literal["Comenzar el reporte" , "Cancelar Reporte" , "Actualiza el Plan"]]

class PlannerState(MessagesState):
    tools_context : str
    plan : Optional[PlanInput]