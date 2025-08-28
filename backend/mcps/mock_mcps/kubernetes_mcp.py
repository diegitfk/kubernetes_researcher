import json
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import random
import uuid

from fastmcp import FastMCP, Context


@dataclass
class Pod:
    name: str
    namespace: str
    status: str
    ready: str
    restarts: int
    age: str
    node: str
    image: str


@dataclass
class Service:
    name: str
    namespace: str
    type: str
    cluster_ip: str
    external_ip: str
    port: str
    age: str


@dataclass
class Deployment:
    name: str
    namespace: str
    ready: str
    up_to_date: int
    available: int
    age: str
    replicas: int


@dataclass
class Node:
    name: str
    status: str
    roles: str
    age: str
    version: str
    internal_ip: str
    os_image: str


class MockKubernetesData:
    """Mock data generator for Kubernetes objects"""
    
    def __init__(self):
        self.cluster_name = "test-cluster"
        self.namespaces = ["default", "kube-system", "monitoring", "ingress-nginx"]
        self._generate_mock_data()
    
    def _generate_mock_data(self):
        """Generate mock Kubernetes objects for simulation"""
        # Mock nodes
        self.nodes = [
            Node("node-1", "Ready", "control-plane", "15d", "v1.28.2", "10.0.1.10", "Ubuntu 22.04.3 LTS"),
            Node("node-2", "Ready", "worker", "15d", "v1.28.2", "10.0.1.11", "Ubuntu 22.04.3 LTS"),
            Node("node-3", "Ready", "worker", "14d", "v1.28.2", "10.0.1.12", "Ubuntu 22.04.3 LTS"),
        ]
        
        # Mock deployments
        self.deployments = [
            Deployment("nginx-deployment", "default", "3/3", 3, 3, "5d", 3),
            Deployment("api-service", "default", "2/2", 2, 2, "3d", 2),
            Deployment("frontend", "default", "1/1", 1, 1, "2d", 1),
            Deployment("coredns", "kube-system", "2/2", 2, 2, "15d", 2),
            Deployment("prometheus", "monitoring", "1/1", 1, 1, "10d", 1),
        ]
        
        # Mock pods
        self.pods = [
            Pod("nginx-deployment-7d4f8c9b8d-abc12", "default", "Running", "1/1", 0, "5d", "node-2", "nginx:1.21"),
            Pod("nginx-deployment-7d4f8c9b8d-def34", "default", "Running", "1/1", 0, "5d", "node-3", "nginx:1.21"),
            Pod("nginx-deployment-7d4f8c9b8d-ghi56", "default", "Running", "1/1", 1, "4d", "node-2", "nginx:1.21"),
            Pod("api-service-6b8f9c7a5d-jkl78", "default", "Running", "1/1", 0, "3d", "node-3", "api:v1.2"),
            Pod("api-service-6b8f9c7a5d-mno90", "default", "Running", "1/1", 0, "3d", "node-2", "api:v1.2"),
            Pod("frontend-5a7b8c9d4e-pqr12", "default", "Running", "1/1", 0, "2d", "node-1", "frontend:latest"),
            Pod("coredns-78fcd69978-stu34", "kube-system", "Running", "1/1", 0, "15d", "node-1", "coredns:1.10.1"),
            Pod("coredns-78fcd69978-vwx56", "kube-system", "Running", "1/1", 0, "15d", "node-2", "coredns:1.10.1"),
            Pod("prometheus-server-789abc-yza78", "monitoring", "Running", "2/2", 0, "10d", "node-3", "prometheus:v2.40.0"),
        ]
        
        # Mock services
        self.services = [
            Service("nginx-service", "default", "ClusterIP", "10.96.1.100", "<none>", "80/TCP", "5d"),
            Service("api-service", "default", "ClusterIP", "10.96.1.101", "<none>", "8080/TCP", "3d"),
            Service("frontend-service", "default", "LoadBalancer", "10.96.1.102", "203.0.113.1", "80:32000/TCP", "2d"),
            Service("kube-dns", "kube-system", "ClusterIP", "10.96.0.10", "<none>", "53/UDP,53/TCP", "15d"),
            Service("prometheus-server", "monitoring", "ClusterIP", "10.96.2.50", "<none>", "9090/TCP", "10d"),
        ]


# Initialize FastMCP server and mock data
mcp = FastMCP("Kubernetes Cluster Manager", version="1.0.0" , host="localhost" ,port=3000)
k8s_data = MockKubernetesData()


# Resources - read-only data access
@mcp.resource("k8s://cluster/info")
async def get_cluster_info():
    """Get general information about the Kubernetes cluster"""
    return {
        "cluster_name": k8s_data.cluster_name,
        "version": "v1.28.2",
        "nodes": len(k8s_data.nodes),
        "total_pods": len(k8s_data.pods),
        "total_services": len(k8s_data.services),
        "total_deployments": len(k8s_data.deployments),
        "namespaces": k8s_data.namespaces,
        "cluster_status": "Healthy",
        "api_server": "https://k8s-api.example.com:6443",
        "dns_service": "10.96.0.10"
    }


@mcp.resource("k8s://namespaces")
async def get_namespaces():
    """Get all namespaces in the cluster"""
    return {"namespaces": k8s_data.namespaces}


@mcp.resource("k8s://nodes")
async def get_nodes():
    """Get all cluster nodes"""
    return {"nodes": [asdict(node) for node in k8s_data.nodes]}


@mcp.resource("k8s://pods/{namespace}")
async def get_pods_by_namespace(namespace: str):
    """Get pods filtered by namespace"""
    if namespace == "all":
        filtered_pods = k8s_data.pods
    else:
        filtered_pods = [p for p in k8s_data.pods if p.namespace == namespace]
    
    return {"namespace": namespace, "pods": [asdict(pod) for pod in filtered_pods]}


@mcp.resource("k8s://services/{namespace}")
async def get_services_by_namespace(namespace: str):
    """Get services filtered by namespace"""
    if namespace == "all":
        filtered_services = k8s_data.services
    else:
        filtered_services = [s for s in k8s_data.services if s.namespace == namespace]
    
    return {"namespace": namespace, "services": [asdict(service) for service in filtered_services]}


@mcp.resource("k8s://deployments/{namespace}")
async def get_deployments_by_namespace(namespace: str):
    """Get deployments filtered by namespace"""
    if namespace == "all":
        filtered_deployments = k8s_data.deployments
    else:
        filtered_deployments = [d for d in k8s_data.deployments if d.namespace == namespace]
    
    return {"namespace": namespace, "deployments": [asdict(deployment) for deployment in filtered_deployments]}


# Tools - interactive functions with side effects
@mcp.tool
async def get_pod_logs(pod_name: str, namespace: str = "default", tail: int = 100, ctx: Context = None) -> str:
    """
    Get logs from a specific pod
    
    Args:
        pod_name: Name of the pod
        namespace: Namespace of the pod (default: default)
        tail: Number of log lines to retrieve (default: 100)
    """
    if ctx:
        await ctx.info(f"Fetching logs for pod {pod_name} in namespace {namespace}")
    
    # Check if pod exists
    pod = next((p for p in k8s_data.pods if p.name == pod_name and p.namespace == namespace), None)
    if not pod:
        if ctx:
            await ctx.error(f"Pod {pod_name} not found in namespace {namespace}")
        return f"Error: Pod {pod_name} not found in namespace {namespace}"
    
    # Simulate log generation
    logs = []
    base_time = datetime.now() - timedelta(hours=1)
    
    for i in range(min(tail, 50)):  # Limit for simulation
        timestamp = (base_time + timedelta(seconds=i*10)).strftime("%Y-%m-%d %H:%M:%S")
        log_level = random.choice(["INFO", "DEBUG", "WARN", "ERROR"])
        messages = [
            "Starting application server",
            "Processing request from client",
            "Database connection established", 
            "Cache hit for key: user_123",
            "Request completed successfully",
            "Health check passed",
            "Memory usage: 245MB",
            "Processing background job"
        ]
        message = random.choice(messages)
        logs.append(f"{timestamp} {log_level} {message}")
    
    return "\n".join(logs[-tail:])


@mcp.tool
async def describe_pod(pod_name: str, namespace: str = "default", ctx: Context = None) -> Dict[str, Any]:
    """
    Get detailed information about a specific pod
    
    Args:
        pod_name: Name of the pod
        namespace: Namespace of the pod (default: default)
    """
    if ctx:
        await ctx.info(f"Describing pod {pod_name} in namespace {namespace}")
    
    # Find the pod
    pod = next((p for p in k8s_data.pods if p.name == pod_name and p.namespace == namespace), None)
    
    if not pod:
        error_msg = f"Pod {pod_name} not found in namespace {namespace}"
        if ctx:
            await ctx.error(error_msg)
        return {"error": error_msg}
    
    # Simulate detailed pod description
    return {
        "name": pod.name,
        "namespace": pod.namespace,
        "status": {
            "phase": pod.status,
            "conditions": [
                {"type": "Initialized", "status": "True"},
                {"type": "Ready", "status": "True"},
                {"type": "ContainersReady", "status": "True"},
                {"type": "PodScheduled", "status": "True"}
            ],
            "containerStatuses": [{
                "name": "main",
                "ready": True,
                "restartCount": pod.restarts,
                "image": pod.image,
                "state": {"running": {"startedAt": "2023-12-01T10:00:00Z"}}
            }]
        },
        "spec": {
            "nodeName": pod.node,
            "containers": [{
                "name": "main",
                "image": pod.image,
                "ports": [{"containerPort": 80, "protocol": "TCP"}],
                "resources": {
                    "requests": {"cpu": "100m", "memory": "128Mi"},
                    "limits": {"cpu": "500m", "memory": "512Mi"}
                }
            }]
        },
        "metadata": {
            "creationTimestamp": "2023-12-01T10:00:00Z",
            "labels": {"app": pod.name.split("-")[0], "version": "v1"},
            "uid": str(uuid.uuid4())
        }
    }


@mcp.tool
async def scale_deployment(deployment_name: str, replicas: int, namespace: str = "default", ctx: Context = None) -> Dict[str, Any]:
    """
    Scale a deployment to specified number of replicas
    
    Args:
        deployment_name: Name of the deployment
        replicas: Number of replicas to scale to
        namespace: Namespace of the deployment (default: default)
    """
    if ctx:
        await ctx.info(f"Scaling deployment {deployment_name} to {replicas} replicas in namespace {namespace}")
    
    # Find the deployment
    deployment = next((d for d in k8s_data.deployments 
                      if d.name == deployment_name and d.namespace == namespace), None)
    
    if not deployment:
        error_msg = f"Deployment {deployment_name} not found in namespace {namespace}"
        if ctx:
            await ctx.error(error_msg)
        return {"error": error_msg}
    
    # Simulate scaling
    old_replicas = deployment.replicas
    deployment.replicas = replicas
    deployment.ready = f"{replicas}/{replicas}"
    deployment.up_to_date = replicas
    deployment.available = replicas
    
    success_msg = f"Deployment {deployment_name} scaled from {old_replicas} to {replicas} replicas"
    if ctx:
        await ctx.info(success_msg)
    
    return {
        "success": True,
        "message": success_msg,
        "deployment": asdict(deployment)
    }


@mcp.tool
async def get_resource_usage(namespace: Optional[str] = None, ctx: Context = None) -> Dict[str, Any]:
    """
    Get cluster resource usage statistics
    
    Args:
        namespace: Namespace to filter resources (optional)
    """
    if ctx:
        ns_msg = f" for namespace {namespace}" if namespace else ""
        await ctx.info(f"Calculating resource usage{ns_msg}")
    
    # Simulate resource usage calculation with slight randomness
    base_cpu_used = 2.5
    base_memory_used = 6.2
    
    if namespace and namespace != "all":
        # Scale down for specific namespace
        pods_in_ns = len([p for p in k8s_data.pods if p.namespace == namespace])
        total_pods = len(k8s_data.pods)
        scale_factor = pods_in_ns / total_pods
        base_cpu_used *= scale_factor
        base_memory_used *= scale_factor
    
    return {
        "namespace": namespace or "cluster-wide",
        "cpu": {
            "used": f"{base_cpu_used:.1f}",
            "total": "8.0",
            "percentage": f"{(base_cpu_used/8.0)*100:.2f}%"
        },
        "memory": {
            "used": f"{base_memory_used:.1f}Gi",
            "total": "16Gi", 
            "percentage": f"{(base_memory_used/16.0)*100:.2f}%"
        },
        "storage": {
            "used": "45Gi",
            "total": "100Gi",
            "percentage": "45%"
        },
        "pods": {
            "used": len([p for p in k8s_data.pods if not namespace or namespace == "all" or p.namespace == namespace]),
            "total": "110"
        }
    }


@mcp.tool
async def restart_deployment(deployment_name: str, namespace: str = "default", ctx: Context = None) -> Dict[str, Any]:
    """
    Restart a deployment by triggering a rolling restart
    
    Args:
        deployment_name: Name of the deployment to restart
        namespace: Namespace of the deployment (default: default)
    """
    if ctx:
        await ctx.info(f"Restarting deployment {deployment_name} in namespace {namespace}")
    
    # Find the deployment
    deployment = next((d for d in k8s_data.deployments 
                      if d.name == deployment_name and d.namespace == namespace), None)
    
    if not deployment:
        error_msg = f"Deployment {deployment_name} not found in namespace {namespace}"
        if ctx:
            await ctx.error(error_msg)
        return {"error": error_msg}
    
    # Simulate restart process
    success_msg = f"Deployment {deployment_name} restart initiated. Rolling restart in progress..."
    
    if ctx:
        await ctx.info("Rolling restart initiated")
        await ctx.info("Terminating old pods...")
        await ctx.info("Starting new pods...")
        await ctx.info("Rolling restart completed successfully")
    
    return {
        "success": True,
        "message": success_msg,
        "deployment": deployment_name,
        "namespace": namespace,
        "restart_time": datetime.now().isoformat()
    }


# Prompts - reusable templates for LLM interactions
@mcp.prompt
def analyze_pod_status(pod_name: str, namespace: str = "default") -> str:
    """Generate a prompt for analyzing pod status and troubleshooting"""
    return f"""
Please analyze the status of pod '{pod_name}' in namespace '{namespace}' and provide:

1. Current status assessment
2. Any potential issues or concerns
3. Troubleshooting recommendations if needed
4. Performance optimization suggestions

Use the describe_pod tool to get detailed information, then provide your analysis.
"""


@mcp.prompt
def cluster_health_check() -> str:
    """Generate a comprehensive cluster health check prompt"""
    return """
Please perform a comprehensive Kubernetes cluster health check:

1. Check cluster info and overall status
2. Review all namespaces and their resources
3. Identify any pods with issues (restarts, failures, etc.)
4. Check resource usage across the cluster
5. Provide a summary with:
   - Overall cluster health status
   - Any issues found and their severity
   - Recommendations for improvements
   - Resource optimization suggestions

Use the available Kubernetes tools to gather this information.
"""


@mcp.prompt
def deployment_scaling_advice(deployment_name: str, namespace: str = "default") -> str:
    """Generate a prompt for deployment scaling recommendations"""
    return f"""
Please analyze the deployment '{deployment_name}' in namespace '{namespace}' and provide scaling recommendations:

1. Get current deployment status and resource usage
2. Analyze current performance and resource consumption
3. Provide scaling recommendations based on:
   - Current load patterns
   - Resource utilization
   - High availability requirements
4. Suggest optimal replica count with justification

Use the available tools to gather deployment info and resource usage data.
"""


# Health check endpoint
@mcp.tool
async def health_check(ctx: Context = None) -> Dict[str, Any]:
    """
    Perform a basic health check of the cluster
    """
    if ctx:
        await ctx.info("Performing cluster health check...")
    
    # Simulate health checks
    healthy_nodes = len([n for n in k8s_data.nodes if n.status == "Ready"])
    total_nodes = len(k8s_data.nodes)
    
    running_pods = len([p for p in k8s_data.pods if p.status == "Running"])
    total_pods = len(k8s_data.pods)
    
    health_status = "Healthy" if healthy_nodes == total_nodes and running_pods == total_pods else "Warning"
    
    if ctx:
        await ctx.info(f"Health check completed. Status: {health_status}")
    
    return {
        "overall_status": health_status,
        "timestamp": datetime.now().isoformat(),
        "nodes": {
            "healthy": healthy_nodes,
            "total": total_nodes,
            "status": "Healthy" if healthy_nodes == total_nodes else "Warning"
        },
        "pods": {
            "running": running_pods,
            "total": total_pods,
            "status": "Healthy" if running_pods == total_pods else "Warning"
        },
        "services": {
            "total": len(k8s_data.services),
            "status": "Healthy"
        },
        "deployments": {
            "total": len(k8s_data.deployments),
            "status": "Healthy"
        }
    }


if __name__ == "__main__":
    # Run the FastMCP server    
    # Run with default STDIO transport for local testing
    # Use mcp.run(transport="http", port=8000) for web deployment
    mcp.run(transport="streamable-http")