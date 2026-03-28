import time
import os
import prometheus_client

from config import DEMO_MODE, KUBE_CONFIG_PATH, KUBE_NAMESPACE

try:
    from kubernetes import client, config
    HAS_K8S = True
except ImportError:
    HAS_K8S = False

CHECK_INTERVAL_SECONDS = 3 if DEMO_MODE else 5
MAX_ATTEMPTS = 10 if DEMO_MODE else 12
MAX_WAIT_SECONDS = CHECK_INTERVAL_SECONDS * MAX_ATTEMPTS

def verify_recovery(service_name: str, pod_deleted: str, baseline: dict) -> str:
    """
    Confirms whether recovery actually worked post-restart.
    Adaptively waits up to MAX_WAIT_SECONDS, checking readiness and metrics.
    """
    print(f"[VERIFIER] Initiating adaptive health assessment for {service_name} (Max {MAX_WAIT_SECONDS}s)...")

    # Initialize Kubernetes client once if available
    v1 = None
    if HAS_K8S and os.path.exists(KUBE_CONFIG_PATH):
        config.load_kube_config(config_file=KUBE_CONFIG_PATH)
        v1 = client.CoreV1Api()
        
    for attempt in range(MAX_ATTEMPTS):
        time.sleep(CHECK_INTERVAL_SECONDS)
        print(f"[VERIFIER] Attempt {attempt+1}/{MAX_ATTEMPTS} for {service_name}...")
        
        try:
            # Check Pod Readiness
            pod_ready = False
            if v1:
                pods = v1.list_namespaced_pod(
                    namespace=KUBE_NAMESPACE,
                    label_selector=f"app={service_name}",
                )
                
                for pod in pods.items:
                    # Ignore terminating pods
                    if pod.metadata.deletion_timestamp is not None:
                        continue
                        
                    if pod.status.phase == "Running" and pod.status.conditions:
                        for condition in pod.status.conditions:
                            if condition.type == "Ready" and condition.status == "True":
                                pod_ready = True
                                break
                    if pod_ready:
                        break
                        
                if not pod_ready:
                    print(f"[VERIFIER] Not yet ready: No active ready pods found for {service_name}.")
                    continue # Try again next loop
            else:
                pod_ready = True # Mock mode passes implicitly
                
            # Check all core metrics against baselines
            metrics = prometheus_client.fetch_metrics(service_name)
            
            checks = [
                ("p95_latency_ms", "p95_latency_ms_mean", 1.5),
                ("error_rate_pct", "error_rate_pct_mean", 1.5),
                ("cpu_cores", "cpu_cores_mean", 1.5),
                ("memory_mb", "memory_mb_mean", 1.5)
            ]
            
            all_metrics_passed = True
            for metric_key, base_key, multiplier in checks:
                val = metrics.get(metric_key)
                if val is None:
                    print(f"[VERIFIER] Still missing metric {metric_key} for {service_name}.")
                    all_metrics_passed = False
                    break
                    
                base_val = baseline.get(base_key, 0.0)
                threshold = max(base_val * multiplier, base_val + 0.1) # Add tiny delta for zero baselines
                
                if val >= threshold:
                    print(f"[VERIFIER] Metric {metric_key}={val:.2f} still >= allowed threshold ({threshold:.2f}).")
                    all_metrics_passed = False
                    break
                    
            if not all_metrics_passed:
                continue # Try again next loop
                
            print(f"[VERIFIER] HEALED: All metrics and pods for {service_name} have fully stabilized!")
            return "HEALED"
            
        except Exception as e:
            print(f"[VERIFIER] Exception during check attempt: {e}")
            continue

    print(f"[VERIFIER] FAILED: Recovery timeout reached ({MAX_WAIT_SECONDS}s) for {service_name}. Unable to verify stability.")
    return "FAILED"
