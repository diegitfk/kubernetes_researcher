from pydantic import BaseModel, Field
from langgraph.graph import MessagesState, add_messages
from langgraph.prebuilt import InjectedState
from langchain_core.messages import AnyMessage
from typing import List, Optional , Literal, Annotated, TypedDict, Any

class PlanSection(BaseModel):
    number : int = Field(description="Número de la sección en el informe puede ser 1 , 2 , 3 , etc.")
    title : str = Field(description="Título de la sección del informe")
    objective : str = Field(description="Objetivo de la sección del informe")
    description : str = Field(description="Descripción detallada de la sección del informe")

class PlanArgTool(BaseModel):
    plan : List[PlanSection] = Field(description="Lista de secciones del informe ordenadas por su número")

class HumanFeedbackInputTool(BaseModel):
    message_human : str = Field(description="Mensaje al usuario sobre el plan")
    plan : PlanArgTool = Field(description="Plan actual generado")

class HumanFeedback(BaseModel):
    feedback : Optional[str] = Field(default=None)
    answer : Optional[Literal["Comenzar el reporte" , "Cancelar Reporte" , "Actualiza el Plan"]]

class PlannerState(MessagesState):
    plan : Optional[PlanArgTool]
    action : Any

class PlannerFormatOutput(BaseModel):
    status: Literal["APPROVED", "CANCELLED"] = Field(description="Estado de la planificación: APPROVED si el usuario acepta el plan, CANCELLED en caso contrario.")
    message: str = Field(description="Explicación breve de la decisión tomada.")

class PlannerStateOutput(BaseModel):
    plan : Optional[PlanArgTool]
    action : PlannerFormatOutput