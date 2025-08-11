from fastmcp import FastMCP
from kubernetes import client , config
import asyncio

kube_mcp = FastMCP(name="Kubernetes Metrics")

@kube_mcp.tool
def list_pods(namespace : str):
    """
    Descripción: Lista todos los Pods del clúster (todos los namespaces) devolviendo metadatos, spec y status de cada Pod tal como los entrega la API de Kubernetes.
    Propósito: Obtener un snapshot completo del estado de workloads en el cluster — ideal para inventario, detección de reinicios, CrashLoopBackOff y otras anomalías de Pod.
    Return:
    ```json
                {
                "type": "object",
                "properties": {
                    "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                        "metadata": {
                            "type": "object",
                            "properties": {
                            "name": {"type":"string"},
                            "namespace": {"type":"string"},
                            "labels": {"type":"object", "additionalProperties":{"type":"string"}},
                            "creationTimestamp": {"type":"string", "format":"date-time"}
                            },
                            "required":["name","namespace"]
                        },
                        "spec": {"type":"object"},
                        "status": {
                            "type":"object",
                            "properties": {
                            "phase": {"type":"string"},
                            "podIP": {"type":"string"},
                            "container_statuses": {
                                "type":"array",
                                "items":{
                                "type":"object",
                                "properties": {
                                    "name": {"type":"string"},
                                    "restart_count": {"type":"integer"},
                                    "ready": {"type":"boolean"},
                                    "state": {"type":"object"}
                                },
                                "required":["name","restart_count"]
                                }
                            }
                            }
                        }
                        },
                        "required":["metadata","status"]
                    }
                    }
                },
                "required":["items"]
                }
    ```

    - items: array de Pods.
    - metadata.name, metadata.namespace: identificador del Pod.
    - metadata.labels: etiquetas útiles para filtrar (app, tier).
    - status.phase: estado alto (Running, Pending, Failed, Succeeded).
    - container_statuses: lista por contenedor con restart_count y state (contiene terminated o running con reason cuando está disponible). Un LLM debe extraer restart_count y last_termination_reason de aquí.

    """
    return None

if __name__ == "__main__":
    asyncio.run(kube_mcp.run_async(transport="streamable-http"))