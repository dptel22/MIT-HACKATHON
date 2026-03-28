import time

def evaluate_decision(confidence: float, votes: list, service_name: str, cooldowns: dict) -> tuple:
    """
    Evaluates the safety gates before authorizing a recovery action.
    """
    if sum(votes) < 4:
        return False, "Not enough anomalous votes (need 4/5)"
        
    if confidence < 80.0:
        return False, f"Confidence {confidence}% is below 80% threshold"
        
    # Updated Criticality Gate based on chosen 5 services
    if service_name in ["paymentservice", "productcatalogservice"]:
        return False, f"Service {service_name} is critical; halting auto-remediation"
        
    last_action_time = cooldowns.get(service_name, 0.0)
    time_since_last_action = time.time() - last_action_time
    if time_since_last_action < 120.0:
        return False, f"Service {service_name} in cooldown for another {int(120 - time_since_last_action)}s"
        
    return True, "All gates passed; initiating recovery"
