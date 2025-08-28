import json
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import random
import time

from fastmcp import FastMCP, Context


@dataclass
class MetricSample:
    timestamp: float
    value: float


@dataclass
class Metric:
    name: str
    labels: Dict[str, str]
    samples: List[MetricSample]
    help: str
    type: str  # counter, gauge, histogram, summary


@dataclass
class Alert:
    name: str
    state: str  # firing, pending, inactive
    labels: Dict[str, str]
    annotations: Dict[str, str]
    active_at: str
    value: float


class MockPrometheusData:
    """Mock data generator for Prometheus metrics that matches K8s cluster"""
    
    def __init__(self):
        self.cluster_name = "test-cluster"
        # Match the K8s cluster structure
        self.nodes = ["node-1", "node-2", "node-3"]
        self.namespaces = ["default", "kube-system", "monitoring", "ingress-nginx"]
        self.pods = {
            "nginx-deployment-7d4f8c9b8d-abc12": {"namespace": "default", "node": "node-2", "app": "nginx"},
            "nginx-deployment-7d4f8c9b8d-def34": {"namespace": "default", "node": "node-3", "app": "nginx"},
            "nginx-deployment-7d4f8c9b8d-ghi56": {"namespace": "default", "node": "node-2", "app": "nginx"},
            "api-service-6b8f9c7a5d-jkl78": {"namespace": "default", "node": "node-3", "app": "api"},
            "api-service-6b8f9c7a5d-mno90": {"namespace": "default", "node": "node-2", "app": "api"},
            "frontend-5a7b8c9d4e-pqr12": {"namespace": "default", "node": "node-1", "app": "frontend"},
            "coredns-78fcd69978-stu34": {"namespace": "kube-system", "node": "node-1", "app": "coredns"},
            "coredns-78fcd69978-vwx56": {"namespace": "kube-system", "node": "node-2", "app": "coredns"},
            "prometheus-server-789abc-yza78": {"namespace": "monitoring", "node": "node-3", "app": "prometheus"},
        }
        self.services = ["nginx-service", "api-service", "frontend-service", "kube-dns", "prometheus-server"]
        self._generate_alerts()
    
    def _generate_alerts(self):
        """Generate sample alerts"""
        self.alerts = [
            Alert(
                name="HighMemoryUsage",
                state="firing",
                labels={"instance": "node-2", "severity": "warning"},
                annotations={"description": "Memory usage is above 80%", "summary": "High memory usage on node-2"},
                active_at="2023-12-05T10:30:00Z",
                value=85.4
            ),
            Alert(
                name="PodRestartLoop",
                state="pending",
                labels={"pod": "nginx-deployment-7d4f8c9b8d-ghi56", "namespace": "default", "severity": "critical"},
                annotations={"description": "Pod has restarted 1 times in 5 minutes", "summary": "Pod restart detected"},
                active_at="2023-12-05T11:15:00Z",
                value=1
            ),
            Alert(
                name="DiskSpaceWarning",
                state="inactive",
                labels={"instance": "node-1", "severity": "warning"},
                annotations={"description": "Disk space usage is above 70%", "summary": "Low disk space"},
                active_at="",
                value=0
            )
        ]
    
    def generate_metric_samples(self, duration_minutes: int = 60, interval_seconds: int = 15) -> List[MetricSample]:
        """Generate time series samples for the specified duration"""
        samples = []
        end_time = time.time()
        start_time = end_time - (duration_minutes * 60)
        
        current_time = start_time
        while current_time <= end_time:
            # Add some realistic variance
            base_value = random.uniform(0.1, 0.9)
            samples.append(MetricSample(current_time, base_value))
            current_time += interval_seconds
        
        return samples


# Initialize FastMCP server and mock data
mcp = FastMCP("Prometheus Monitoring Server", version="1.0.0" , port="3001")
prom_data = MockPrometheusData()


# Resources - read-only data access
@mcp.resource("prometheus://status")
async def get_prometheus_status():
    """Get Prometheus server status and configuration"""
    return {
        "status": "ready",
        "version": "2.40.0",
        "uptime": "10d 5h 32m",
        "retention": "15d",
        "scrape_interval": "15s",
        "evaluation_interval": "15s",
        "storage_path": "/prometheus/data",
        "config_file": "/etc/prometheus/prometheus.yml",
        "active_targets": 25,
        "dropped_targets": 0,
        "active_alerts": len([a for a in prom_data.alerts if a.state == "firing"]),
        "total_series": 12847,
        "head_samples": 2834,
        "wal_size": "245MB"
    }


@mcp.resource("prometheus://targets")
async def get_targets():
    """Get all scrape targets and their status"""
    targets = []
    
    # Node exporter targets
    for node in prom_data.nodes:
        targets.append({
            "job": "node-exporter",
            "instance": f"{node}:9100",
            "health": "up",
            "last_scrape": "2023-12-05T11:30:00Z",
            "scrape_duration": "0.045s",
            "labels": {"node": node, "role": "node"}
        })
    
    # Kubernetes API server
    targets.append({
        "job": "kubernetes-apiservers",
        "instance": "k8s-api.example.com:6443",
        "health": "up",
        "last_scrape": "2023-12-05T11:30:00Z",
        "scrape_duration": "0.028s",
        "labels": {"component": "apiserver"}
    })
    
    # Pod targets
    for pod_name, pod_info in prom_data.pods.items():
        if pod_info["app"] in ["nginx", "api", "frontend"]:  # Only app pods have metrics
            targets.append({
                "job": f"{pod_info['app']}-metrics",
                "instance": f"{pod_name}:8080",
                "health": "up" if random.random() > 0.1 else "down",
                "last_scrape": "2023-12-05T11:30:00Z",
                "scrape_duration": f"0.{random.randint(20, 80)}s",
                "labels": {
                    "pod": pod_name,
                    "namespace": pod_info["namespace"],
                    "app": pod_info["app"],
                    "node": pod_info["node"]
                }
            })
    
    return {"targets": targets}


@mcp.resource("prometheus://alerts")
async def get_alerts():
    """Get all active alerts"""
    return {"alerts": [asdict(alert) for alert in prom_data.alerts]}


@mcp.resource("prometheus://rules")
async def get_alerting_rules():
    """Get configured alerting rules"""
    rules = [
        {
            "name": "kubernetes.rules",
            "rules": [
                {
                    "alert": "HighMemoryUsage",
                    "expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 80",
                    "for": "5m",
                    "labels": {"severity": "warning"},
                    "annotations": {
                        "description": "Memory usage is above 80% on {{ $labels.instance }}",
                        "summary": "High memory usage detected"
                    }
                },
                {
                    "alert": "PodRestartLoop", 
                    "expr": "rate(kube_pod_container_status_restarts_total[5m]) * 60 * 5 > 0",
                    "for": "0m",
                    "labels": {"severity": "critical"},
                    "annotations": {
                        "description": "Pod {{ $labels.pod }} has restarted {{ $value }} times in 5 minutes",
                        "summary": "Pod restart loop detected"
                    }
                },
                {
                    "alert": "DiskSpaceWarning",
                    "expr": "(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100 > 70",
                    "for": "10m", 
                    "labels": {"severity": "warning"},
                    "annotations": {
                        "description": "Disk space usage is above 70% on {{ $labels.instance }}",
                        "summary": "Low disk space"
                    }
                }
            ]
        }
    ]
    return {"rule_groups": rules}


# Tools - interactive query functions
@mcp.tool
async def query_prometheus(query: str, time_param: Optional[str] = None, ctx: Context = None) -> Dict[str, Any]:
    """
    Execute a PromQL query against Prometheus
    
    Args:
        query: PromQL query string
        time_param: Time parameter (RFC3339 timestamp or relative like '5m')
    """
    if ctx:
        await ctx.info(f"Executing PromQL query: {query}")
    
    # Simulate query execution with realistic responses based on query patterns
    result_type = "vector"
    results = []
    
    # Parse common query patterns and generate appropriate responses
    if "node_memory" in query.lower():
        # Memory metrics
        for node in prom_data.nodes:
            memory_used = random.uniform(4.0, 12.0)  # GB
            memory_total = 16.0
            percentage = (memory_used / memory_total) * 100
            
            results.append({
                "metric": {
                    "__name__": "node_memory_usage_percent",
                    "instance": f"{node}:9100",
                    "node": node
                },
                "value": [time.time(), str(round(percentage, 2))]
            })
    
    elif "node_cpu" in query.lower():
        # CPU metrics
        for node in prom_data.nodes:
            cpu_usage = random.uniform(15.0, 85.0)
            results.append({
                "metric": {
                    "__name__": "node_cpu_usage_percent", 
                    "instance": f"{node}:9100",
                    "node": node
                },
                "value": [time.time(), str(round(cpu_usage, 2))]
            })
    
    elif "kube_pod" in query.lower():
        # Pod metrics
        for pod_name, pod_info in prom_data.pods.items():
            if "status" in query.lower():
                status = 1 if random.random() > 0.05 else 0  # 95% pods running
                results.append({
                    "metric": {
                        "__name__": "kube_pod_status_ready",
                        "pod": pod_name,
                        "namespace": pod_info["namespace"],
                        "node": pod_info["node"]
                    },
                    "value": [time.time(), str(status)]
                })
            elif "restart" in query.lower():
                restarts = random.choice([0, 0, 0, 1])  # Mostly 0, sometimes 1
                results.append({
                    "metric": {
                        "__name__": "kube_pod_container_status_restarts_total",
                        "pod": pod_name,
                        "namespace": pod_info["namespace"],
                        "container": "main"
                    },
                    "value": [time.time(), str(restarts)]
                })
    
    elif "http_requests" in query.lower():
        # Application metrics
        for pod_name, pod_info in prom_data.pods.items():
            if pod_info["app"] in ["nginx", "api", "frontend"]:
                requests_rate = random.uniform(10.0, 100.0)
                results.append({
                    "metric": {
                        "__name__": "http_requests_total",
                        "pod": pod_name,
                        "app": pod_info["app"],
                        "status": "200"
                    },
                    "value": [time.time(), str(round(requests_rate, 2))]
                })
    
    else:
        # Generic response for unknown queries
        results.append({
            "metric": {"__name__": "unknown_metric"},
            "value": [time.time(), str(random.uniform(0, 100))]
        })
    
    if ctx:
        await ctx.info(f"Query returned {len(results)} results")
    
    return {
        "status": "success",
        "data": {
            "resultType": result_type,
            "result": results
        },
        "query": query,
        "timestamp": time.time()
    }


@mcp.tool
async def query_range(query: str, start: str, end: str, step: str = "15s", ctx: Context = None) -> Dict[str, Any]:
    """
    Execute a PromQL range query
    
    Args:
        query: PromQL query string
        start: Start time (RFC3339 or relative)
        end: End time (RFC3339 or relative) 
        step: Query resolution step
    """
    if ctx:
        await ctx.info(f"Executing range query: {query} from {start} to {end}")
    
    # Parse time parameters
    try:
        if start.endswith('m'):
            start_minutes = int(start[:-1])
            start_time = time.time() - (start_minutes * 60)
        else:
            start_time = time.time() - 3600  # Default 1 hour
        
        end_time = time.time()
        step_seconds = int(step[:-1]) if step.endswith('s') else 15
        
    except:
        start_time = time.time() - 3600
        end_time = time.time()
        step_seconds = 15
    
    # Generate time series data
    results = []
    
    if "node_memory" in query.lower():
        for node in prom_data.nodes:
            values = []
            current_time = start_time
            base_memory = random.uniform(40, 80)  # Base memory percentage
            
            while current_time <= end_time:
                # Add some variance around the base value
                memory_usage = base_memory + random.uniform(-5, 5)
                memory_usage = max(20, min(95, memory_usage))  # Clamp between 20-95%
                values.append([current_time, str(round(memory_usage, 2))])
                current_time += step_seconds
            
            results.append({
                "metric": {
                    "__name__": "node_memory_usage_percent",
                    "instance": f"{node}:9100",
                    "node": node
                },
                "values": values
            })
    
    elif "http_requests" in query.lower():
        for pod_name, pod_info in prom_data.pods.items():
            if pod_info["app"] in ["nginx", "api", "frontend"]:
                values = []
                current_time = start_time
                base_rate = random.uniform(20, 80)
                
                while current_time <= end_time:
                    rate = base_rate + random.uniform(-10, 10)
                    rate = max(0, rate)
                    values.append([current_time, str(round(rate, 2))])
                    current_time += step_seconds
                
                results.append({
                    "metric": {
                        "__name__": "http_requests_per_second",
                        "pod": pod_name,
                        "app": pod_info["app"]
                    },
                    "values": values
                })
    
    if ctx:
        await ctx.info(f"Range query returned {len(results)} time series")
    
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": results
        },
        "query": query,
        "start": start_time,
        "end": end_time,
        "step": step_seconds
    }


@mcp.tool
async def get_metric_metadata(metric: Optional[str] = None, ctx: Context = None) -> Dict[str, Any]:
    """
    Get metadata for metrics
    
    Args:
        metric: Specific metric name (optional, returns all if not specified)
    """
    if ctx:
        await ctx.info(f"Getting metadata for metric: {metric or 'all metrics'}")
    
    # Common Kubernetes and node metrics metadata
    metadata = {
        "node_memory_MemTotal_bytes": {
            "type": "gauge",
            "help": "Memory information field MemTotal_bytes",
            "unit": "bytes"
        },
        "node_memory_MemAvailable_bytes": {
            "type": "gauge", 
            "help": "Memory information field MemAvailable_bytes",
            "unit": "bytes"
        },
        "node_cpu_seconds_total": {
            "type": "counter",
            "help": "Seconds the CPUs spent in each mode",
            "unit": "seconds"
        },
        "kube_pod_status_ready": {
            "type": "gauge",
            "help": "Describes whether the pod is ready to serve requests",
            "unit": ""
        },
        "kube_pod_container_status_restarts_total": {
            "type": "counter",
            "help": "The number of container restarts per container",
            "unit": ""
        },
        "http_requests_total": {
            "type": "counter",
            "help": "Total number of HTTP requests",
            "unit": ""
        },
        "container_memory_usage_bytes": {
            "type": "gauge",
            "help": "Current memory usage in bytes",
            "unit": "bytes"
        },
        "container_cpu_usage_seconds_total": {
            "type": "counter",
            "help": "Cumulative cpu time consumed",
            "unit": "seconds"
        }
    }
    
    if metric:
        result = metadata.get(metric, {})
        if not result:
            result = {"error": f"Metric {metric} not found"}
    else:
        result = metadata
    
    return {"metadata": result}


@mcp.tool
async def get_node_metrics(node: str, ctx: Context = None) -> Dict[str, Any]:
    """
    Get comprehensive metrics for a specific node
    
    Args:
        node: Node name (node-1, node-2, node-3)
    """
    if ctx:
        await ctx.info(f"Fetching metrics for node {node}")
    
    if node not in prom_data.nodes:
        error_msg = f"Node {node} not found"
        if ctx:
            await ctx.error(error_msg)
        return {"error": error_msg}
    
    # Generate realistic node metrics
    cpu_cores = 4
    memory_total_gb = 16
    memory_used_gb = random.uniform(4, 12)
    cpu_usage_percent = random.uniform(15, 75)
    
    disk_total_gb = 100
    disk_used_gb = random.uniform(30, 60)
    
    network_rx_bytes = random.randint(1000000, 10000000)
    network_tx_bytes = random.randint(500000, 5000000)
    
    # Count pods on this node
    pods_on_node = [p for p, info in prom_data.pods.items() if info["node"] == node]
    
    return {
        "node": node,
        "timestamp": time.time(),
        "cpu": {
            "cores": cpu_cores,
            "usage_percent": round(cpu_usage_percent, 2),
            "usage_cores": round((cpu_usage_percent / 100) * cpu_cores, 2)
        },
        "memory": {
            "total_gb": memory_total_gb,
            "used_gb": round(memory_used_gb, 2),
            "available_gb": round(memory_total_gb - memory_used_gb, 2),
            "usage_percent": round((memory_used_gb / memory_total_gb) * 100, 2)
        },
        "disk": {
            "total_gb": disk_total_gb,
            "used_gb": round(disk_used_gb, 2),
            "available_gb": round(disk_total_gb - disk_used_gb, 2),
            "usage_percent": round((disk_used_gb / disk_total_gb) * 100, 2)
        },
        "network": {
            "rx_bytes": network_rx_bytes,
            "tx_bytes": network_tx_bytes
        },
        "pods": {
            "count": len(pods_on_node),
            "names": pods_on_node
        }
    }


@mcp.tool
async def get_pod_metrics(pod_name: str, namespace: str = "default", ctx: Context = None) -> Dict[str, Any]:
    """
    Get metrics for a specific pod
    
    Args:
        pod_name: Name of the pod
        namespace: Namespace of the pod
    """
    if ctx:
        await ctx.info(f"Fetching metrics for pod {pod_name} in namespace {namespace}")
    
    # Find the pod
    pod_info = prom_data.pods.get(pod_name)
    if not pod_info or pod_info["namespace"] != namespace:
        error_msg = f"Pod {pod_name} not found in namespace {namespace}"
        if ctx:
            await ctx.error(error_msg)
        return {"error": error_msg}
    
    # Generate pod-specific metrics
    cpu_usage = random.uniform(0.1, 2.0)  # CPU cores
    memory_usage_mb = random.uniform(50, 400)
    
    # Request metrics for app pods
    requests_per_sec = 0
    if pod_info["app"] in ["nginx", "api", "frontend"]:
        requests_per_sec = random.uniform(5, 50)
    
    return {
        "pod": pod_name,
        "namespace": namespace,
        "app": pod_info["app"],
        "node": pod_info["node"],
        "timestamp": time.time(),
        "resources": {
            "cpu_usage_cores": round(cpu_usage, 3),
            "memory_usage_mb": round(memory_usage_mb, 2),
            "memory_usage_bytes": int(memory_usage_mb * 1024 * 1024)
        },
        "application": {
            "http_requests_per_second": round(requests_per_sec, 2),
            "response_time_ms": round(random.uniform(10, 200), 2)
        },
        "container": {
            "restarts": random.choice([0, 0, 0, 1]),  # Mostly 0
            "status": "running"
        }
    }


# Prompts - reusable templates for analysis
@mcp.prompt
def analyze_cluster_performance() -> str:
    """Generate a prompt for comprehensive cluster performance analysis"""
    return """
Please perform a comprehensive Prometheus-based cluster performance analysis:

1. Query overall cluster resource usage (CPU, memory) across all nodes
2. Identify any performance bottlenecks or resource constraints
3. Check for any firing alerts and their root causes
4. Analyze application metrics and response times
5. Review pod resource consumption patterns
6. Provide recommendations for:
   - Resource optimization
   - Alert tuning
   - Performance improvements
   - Scaling decisions

Use the available Prometheus tools to gather metrics and provide actionable insights.
"""


@mcp.prompt
def investigate_alert(alert_name: str) -> str:
    """Generate a prompt for investigating a specific alert"""
    return f"""
Please investigate the alert '{alert_name}' using Prometheus data:

1. Get the current alert status and details
2. Query relevant metrics that triggered the alert
3. Check historical data to understand the trend
4. Identify the root cause of the issue
5. Provide troubleshooting steps and recommendations

Focus on:
- When the alert started firing
- Which resources/pods are affected
- Historical patterns and trends
- Immediate mitigation steps
- Long-term prevention strategies
"""


@mcp.prompt
def capacity_planning_analysis() -> str:
    """Generate a prompt for cluster capacity planning"""
    return """
Please perform a capacity planning analysis using Prometheus metrics:

1. Analyze current resource utilization trends across all nodes
2. Identify peak usage patterns and growth trends
3. Calculate resource headroom and projected capacity needs
4. Evaluate per-application resource consumption
5. Provide capacity planning recommendations:
   - When additional nodes may be needed
   - Optimal resource allocation strategies
   - Cost optimization opportunities
   - Scaling thresholds

Use range queries to analyze historical trends and project future needs.
"""


if __name__ == "__main__":
    mcp.run(transport="streamable-http")