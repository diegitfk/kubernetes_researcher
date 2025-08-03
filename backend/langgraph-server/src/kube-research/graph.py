from langgraph.graph import StateGraph
from langgraph.types import Command
from subgraphs.planner_research.planner_graph import PlannerResearchGraph
from langchain_core.messages import HumanMessage
import os

agent = PlannerResearchGraph(
    provider = "OpenAI",
    model = "gpt-4.1-mini",
    temperature = 0.3,
    max_tokens = 10000,
    provider_api_key="..."
)
planner = agent.build_graph()
while True:
    interrupts = planner.get_state({"configurable" : {"thread_id" : "planner_abcf56ji"}}).interrupts

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
            response = planner.invoke(
                input=Command(
                    resume={
                        "feedback" : feedback,
                        "answer" : answer_option[answer]
                    }
                ),
                config={"configurable" : {"thread_id" : "planner_abcf56ji"}}
            )
            print(response)
            break
        if answer == 3:
            feedback = str(input("Feedback : "))
            planner.invoke(
                input=Command(
                    resume={
                        "feedback" : feedback,
                        "answer" : answer_option[answer]
                    }
                ),
                config={"configurable" : {"thread_id" : "planner_abcf56ji"}}
            )
    else: 
        state = planner.invoke({
            "messages" : [],
            "tools_context" : "- get_pods_metrics() , para obtener las metricas de pods\n- prometheus_cluster_metrics(), para obtener metricas del cluster via prometheus",
            "plan" : None
        } ,
        {"configurable" : {"thread_id" : "planner_abcf56ji"}}
        )

