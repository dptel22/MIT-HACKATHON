import time
import os
import uuid
import logging

from config import KUBE_NAMESPACE

try:
    from kubernetes import client, config
    HAS_K8S = True
except ImportError:
    HAS_K8S = False
    
logger = logging.getLogger(__name__)

def restart_pod(service_name: str) -> tuple:
    """
    Deletes exactly 1 pod matching the service_name in the configured namespace.
    Returns:
        pod_name: string that was deleted
        timestamp: float
    """
    kubeconfig_path = os.path.join(os.path.dirname(__file__), "kubeconfig.yaml")
    
    if HAS_K8S and os.path.exists(kubeconfig_path):
        try:
            config.load_kube_config(config_file=kubeconfig_path)
            v1 = client.CoreV1Api()
            
            pods = v1.list_namespaced_pod(
                namespace=KUBE_NAMESPACE,
                label_selector=f"app={service_name}",
            )
            if not pods.items:
                raise Exception(f"No pods found for service {service_name} with label app={service_name}")
                
            pod_to_delete = pods.items[0].metadata.name
            
            print(f"[RECOVERY] Deleting pod {pod_to_delete} in namespace {KUBE_NAMESPACE}.")
            v1.delete_namespaced_pod(name=pod_to_delete, namespace=KUBE_NAMESPACE)
            
            return pod_to_delete, time.time()
        except Exception as e:
            print(f"[RECOVERY] Kubernetes client error: {e}")
            raise e
    else:
        # Fallback to mock behavior if kubeconfig is missing or library is unavailable
        pod_id = str(uuid.uuid4())[:8]
        pod_name = f"{service_name}-{pod_id}"
        timestamp = time.time()
        
        print(
            f"[RECOVERY] Mock mode: Simulated delete request for pod {pod_name} "
            f"in namespace {KUBE_NAMESPACE} (kubeconfig not found)."
        )
        return pod_name, timestamp
