import time
import os
import prometheus_client

from config import KUBE_NAMESPACE

try:
    from kubernetes import client, config
    HAS_K8S = True
except ImportError:
    HAS_K8S = False

def verify_recovery(pod_deleted: str, baseline_avg: float) -> str:
    """
    Confirms whether recovery actually worked post-restart.
    Waits 20s, checks readiness states, and compares p95 latency against 1.5x baseline limit.
    
    Args:
        pod_deleted: name of the deleted pod (used to derive service name)
        baseline_avg: the p95 baseline captured via stats
        
    Returns:
        status string: 'HEALED' or 'FAILED'
    """
    # PRD Requirement: Wait 20-30 seconds after deletion before checking
    print(f"[VERIFIER] Waiting 20 seconds to assess recovery for service related to {pod_deleted}...")
    time.sleep(20)
    
    try:
        # Extract base service name (e.g. 'cartservice' from 'cartservice-xyz-123')
        # We can also handle exact hits.
        parts = pod_deleted.split('-')
        service_name = parts[0] if len(parts) >= 2 else pod_deleted

        # Check Pod Readiness
        kubeconfig_path = os.path.join(os.path.dirname(__file__), "kubeconfig.yaml")
        if HAS_K8S and os.path.exists(kubeconfig_path):
            config.load_kube_config(config_file=kubeconfig_path)
            v1 = client.CoreV1Api()
            
            pods = v1.list_namespaced_pod(
                namespace=KUBE_NAMESPACE,
                label_selector=f"app={service_name}",
            )
            
            pod_ready = False
            for pod in pods.items:
                if pod.status.phase == "Running" and pod.status.conditions:
                    for condition in pod.status.conditions:
                        if condition.type == "Ready" and condition.status == "True":
                            pod_ready = True
                            break
                if pod_ready:
                    break
                    
            if not pod_ready:
                print(f"[VERIFIER] FAILED: No ready pods found for {service_name}.")
                return "FAILED"
        else:
            print(f"[VERIFIER] Mock: Assuming pod readiness passes because kubeconfig.yaml is absent.")
            
        print(f"[VERIFIER] Assessing latency compared to baseline {baseline_avg} ms")
        
        # Check Latency Recovery
        metrics = prometheus_client.fetch_metrics(service_name)
        lat = metrics.get('p95_latency_ms')
        
        if lat is None:
            print(f"[VERIFIER] FAILED: Missing latency metric for {service_name}.")
            return "FAILED"
            
        if lat >= baseline_avg * 1.5:
            print(f"[VERIFIER] FAILED: Latency {lat:.2f}ms is >= allowed threshold ({baseline_avg * 1.5:.2f}ms).")
            return "FAILED"
            
        print(f"[VERIFIER] HEALED: Latency {lat:.2f}ms is well within limits of {baseline_avg * 1.5:.2f}ms.")
        return "HEALED"
        
    except Exception as e:
        print(f"[VERIFIER] FAILED due to Exception: {e}")
        return "FAILED"
