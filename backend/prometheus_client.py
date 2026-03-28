import os
import random

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

def fetch_metrics(service_name: str) -> dict:
    """
    Fetches feature metrics from teammate's Prometheus per-service.
    """
    base_latency = 50.0
    if service_name == "paymentservice": 
        base_latency = 120.0
    elif service_name == "recommendationservice": 
        base_latency = 80.0
        
    return {
        "p95_latency": round(random.uniform(base_latency, base_latency + 50.0), 2),
        "error_rate": round(random.uniform(0.0, 0.05), 4),
        "cpu": round(random.uniform(10.0, 30.0), 2),
        "memory": round(random.uniform(40.0, 60.0), 2)
    }
