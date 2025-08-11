from langgraph.graph import StateGraph
from langgraph.types import Command
from subgraphs.planner_research.planner_graph import PlannerResearchGraph
from kube_researcher import KubeResearcherGraph
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_core.tools.render import render_text_description_and_args
from langchain_openai import ChatOpenAI
from collections import deque
import os

#Tools Examples
@tool
def get_nodes():
    """
        Obtiene los nodos y estadisticas de los nodos de un cluster de kubernetes
    """
    ...
@tool
def get_pods_metrics(namespace : str):
    """
        Obtiene las metricas de los pods de un cluster de kubernetes
    """
    ...
@tool
def prometheus_cluster_metrics():
    """
        Obtiene las metricas del cluster de kubernetes via prometheus
    """

tools = [get_nodes , get_pods_metrics , prometheus_cluster_metrics]
kube_researcher_graph = KubeResearcherGraph(
    reasoning_llm=ChatOpenAI(
        model="google/gemini-2.5-flash-lite",
        base_url="https://openrouter.ai/api/v1",
        reasoning_effort="medium",
        streaming=True,
        api_key="...",
    ), 
    one_shot_llm=ChatOpenAI(
        model="google/gemini-2.0-flash-lite-001",
        base_url="https://openrouter.ai/api/v1",
        streaming=True,
        api_key="...",
    ),
    mcp_connection_args={}
)()
while True:
    interrupts = kube_researcher_graph.get_state({"configurable" : {"thread_id" : "planner_abcf56ji"}}).interrupts

    if interrupts:
        for interrupt in interrupts:
            print(f"Interrupt id : {interrupt.id}")
            if interrupt.value["message"]:
                print(f"Message AI : {interrupt.value['message']}")
            if interrupt.value["plan"]:
                print("Plan Generado")
                for section in interrupt.value["plan"].plan:
                    print(f"{section.number}._ {section.title} \n Objetivo: {section.objective}\n Descripcion: {section.description}")
        
        answer_option = {1 : "Comenzar el reporte" ,2 : "Cancelar Reporte" , 3 : "Actualiza el Plan" }
        print("---------OPCIONES--------------")
        answer = int(input("1._ Comenzar el reporte\n2._ Cancelar Reporte\n3._ Actualizar el plan\n Ingresa la opción:"))
        feedback = None
        if answer == 2 or answer == 1:
            for chunk in kube_researcher_graph.stream(
                input=Command(
                    resume={
                        "feedback" : feedback,
                        "answer" : answer_option[answer]
                    }
                ),
                stream_mode=["messages"],
                subgraphs=True,
                config={"configurable" : {"thread_id" : "planner_abcf56ji"}}
            ):
                print(chunk)
                #if chunk.content:
                    #print(chunk.content , end="" , flush=True)
            break
        if answer == 3:
            feedback = str(input("Feedback : "))
            for chunk in kube_researcher_graph.stream(
                input=Command(
                    resume={
                        "feedback" : feedback,
                        "answer" : answer_option[answer]
                    }
                ),
                subgraphs=True,
                stream_mode="messages",
                config={"configurable" : {"thread_id" : "planner_abcf56ji"}}
            ):
                print(chunk)
                
                #if chunk.content:
                    #print(chunk.content , end="" , flush=True)

    else: 
        for chunk in kube_researcher_graph.stream({
            "messages" : [HumanMessage(content="Requiero que generes un reporte breve sobre el estado de los pods y nodos de mi cluster de kubernetes")],
            "tools_ctx" : render_text_description_and_args(tools),
            "plan" : None
        } ,
        {"configurable" : {"thread_id" : "planner_abcf56ji"}},
        subgraphs=True,
        stream_mode="messages"
        ):
            print(chunk)
            #if chunk.content: 
                #print(chunk , end="" , flush=True)

