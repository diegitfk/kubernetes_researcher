[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/diegitfk/kubernetes_researcher)
# kubernetes_researcher
Este es un proyecto que busca la integración de diversos MCP, para obtener metricas de un cluster remoto de kubernetes, potenciando las metricas con interpretaciones de un LLM.
## Infraestructura del proyecto
<img width="1280" height="761" alt="image" src="https://github.com/user-attachments/assets/2adb2286-d27a-4d85-95c8-7cdebf85d706" />

# Langgraph Workflows
En el servidor `langgraph-server` de la infraestructura, se despliega el servidor de langgraph y se sirven los siguientes workflow en la API REST.

## Kube-Researcher
Es un flujo de trabajo codificado en langgraph que posee la capacidad de generar secciones de un reporte sobre un cluster de kubernetes a partir de la disponibilidad de herramientas de métricas.
este posee los siguientes flujos:
- `Planificador de secciones`: Es un subgrafo que implementa llamadas a un llm teniendo este la disponibilidad de una herramienta llamada `__human_feedback_or_confirm`, es que básicamente la herramienta que pausa el estado del grafo para recibir de parte del usuario un feedback sobre el plan generado para actualizarlo, confirmar el comienzo de la investigación del cluster de kubernetes o cancelar la investigación, este posee los siguientes nodos internos:
   - **planner**: Nodo que genera un plan estructurado de las secciones del informe que se generara.
   - **tools**: Un `ToolNode` con solamente una función `__human_feedback_or_confirm` que es la tool que utiliza el nodo **planner** para recibir el feedback del usuario hasta que aprueba o rechaza la generación del informe.
   - **response_format**: Un analisis de la respuesta final del usuario, para completar con una salida estructurada si el plan es aprobado o cancelado, entregando un mensaje de referencia a la decisión del usuario.
     ```json
     {
      "status": "APPROVED|CANCELLED",
      "message": "Explicación breve de la decisión tomada"
     }
     ```
Así los nodos mencionados se relacionan de la siguiente manera:

<img width="1043" height="625" alt="Captura desde 2025-08-02 21-17-13" src="https://github.com/user-attachments/assets/9afc2a6d-6105-4ac8-a6ce-6ae2e8c191d7" />


En que se diferencia este planificador de otros?: Planificador conoce todas las herramientas de métricas para el cluster que se encuentran a disposición, o sea **a medida que conectamos más MCP's de observabilidad, más herramientas tiene a disposición para investigar el estado del cluster**, con estas herramientas el planificador **propone** un plan a seguir con secciones del reporte estructuradas de la siguiente manera (numero , titulo , objetivo , descripción).  

Ejemplo de funcionamiento:
En este caso al planificador se le entregaron las siguiente herramientas **ficticias** 
- get_pods_metrics(), para obtener metricas de los pods del cluster.
- prometheus_cluster_metrics(), para obtener metricas del cluster via prometheus.
y su comportamiento es el siguiente:


https://github.com/user-attachments/assets/0adcb69e-a5da-4673-88e3-28cda4b1cbaa






