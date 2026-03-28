import subprocess
import os
import time

from config import DEMO_MODE
from service_catalog import get_supported_chaos_scenarios

MANIFEST_DIR = os.path.join(os.path.dirname(__file__), 'manifests')
SUPPORTED_SCENARIOS = frozenset(get_supported_chaos_scenarios())


def _result(service, scenario, *, success, message="", error=""):
    return {
        "success": success,
        "service": service,
        "scenario": scenario,
        "message": message,
        "error": error,
        "timestamp": time.time(),
    }

def check_chaos_mesh_available():
    """Checks if Chaos Mesh CRDs are installed on the cluster."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "crd", "podchaos.chaos-mesh.org"], 
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def fallback_pod_kill(service):
    """Backup pod kill method using plain kubectl if Chaos Mesh isn't available."""
    try:
        cmd = f"kubectl get pod -l app={service} -o jsonpath={{.items[0].metadata.name}}"
        pod_name = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()
        if pod_name:
            subprocess.run(f"kubectl delete pod {pod_name}", shell=True, check=True)
            return True, f"Fallback pod kill successful for {service}"
        return False, f"No running pod found for {service}"
    except Exception as e:
        return False, f"Fallback pod kill failed: {str(e)}"

def inject_chaos(service, scenario):
    """Internal function that reads YAML and applies it via kubectl."""
    yaml_file = os.path.join(MANIFEST_DIR, f"{scenario}.yaml")
    if not os.path.exists(yaml_file):
        return False, f"Scenario {scenario} not found"
        
    try:
        with open(yaml_file, 'r') as f:
            content = f.read()
            
        content = content.replace("SERVICE_PLACEHOLDER", service)
        
        process = subprocess.Popen(
            ['kubectl', 'apply', '-f', '-'], 
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = process.communicate(input=content)
        
        if process.returncode == 0:
            return True, f"Injected {scenario} into {service} successfully"
        else:
            return False, f"Failed to inject chaos system: {stderr}"
    except Exception as e:
        return False, f"CLI Error: {str(e)}"

def inject_chaos_safe(service, scenario):
    """THE MAIN FUNCTION: Runs safety checks before applying chaos."""
    if scenario not in SUPPORTED_SCENARIOS:
        return _result(
            service,
            scenario,
            success=False,
            error=f"Scenario {scenario} is not supported",
        )

    # 1. Criticality Check
    if service in ["frontend", "checkoutservice", "productcatalogservice", "paymentservice"]:
        # Allow demoing on some services, but strictly block the most critical ones:
        if service in ["frontend", "checkoutservice"]:
            return _result(
                service,
                scenario,
                success=False,
                error=f"Cannot inject chaos into foundational critical service: {service}",
            )

    if DEMO_MODE:
        return _result(
            service,
            scenario,
            success=True,
            message=f"Demo mode: simulated {scenario} for {service}",
        )
        
    # 2. Check capabilities
    is_available = check_chaos_mesh_available()
    
    if is_available:
        success, msg = inject_chaos(service, scenario)
    else:
        if scenario == "pod_kill":
            success, msg = fallback_pod_kill(service)
        else:
            return _result(
                service,
                scenario,
                success=False,
                error=(
                    f"Chaos Mesh not available. Cannot perform {scenario}, "
                    "please install helm chart."
                ),
            )
            
    return _result(
        service,
        scenario,
        success=success,
        message=msg,
        error="" if success else msg,
    )

def cleanup_all():
    """Wipes all active experiments after demo."""
    experiments = ["podchaos", "stresschaos", "networkchaos"]
    for exp in experiments:
        try:
            subprocess.run(f"kubectl delete {exp} --all --all-namespaces", shell=True, capture_output=True, timeout=5)
        except subprocess.TimeoutExpired:
            pass
