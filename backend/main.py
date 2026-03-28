from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import time
import asyncio

import database
import models
import prometheus_client
import detector
import decision
import recovery
import verifier
from chaos.chaos_engine import inject_chaos_safe, cleanup_all

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="KubeResilience", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The 5 explicit services chosen for the dashboard tracking
SERVICES = ["cartservice", "paymentservice", "recommendationservice", "shippingservice", "productcatalogservice"]

# Independent States!
state = {
    "warmup_done": False,
    "manual_mode": False,
    "cooldowns": {},
    "services": {
        svc: {
            "baseline_avg": 100.0,
            "votes": [],
            "confidence": 0.0,
            "is_anomaly": False,
            "features": {"p95_latency": 0.0, "error_rate": 0.0, "cpu": 0.0, "memory": 0.0}
        } for svc in SERVICES
    }
}

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/health")
def read_health():
    return {"status": "ok"}

@app.get("/api/services")
def list_services():
    """Returns the exact list of the 5 tracked services for the frontend."""
    return {"services": SERVICES}

async def perform_warmup():
    print("[WARMUP] Starting 10-second warm-up phase.")
    await asyncio.sleep(10) 
    
    for svc in SERVICES:
        baselines = []
        for _ in range(5):
            features = prometheus_client.fetch_metrics(svc)
            baselines.append(features.get("p95_latency", 0))
        
        state["services"][svc]["baseline_avg"] = sum(baselines) / len(baselines) if baselines else 100.0
        
    state["warmup_done"] = True
    print(f"[WARMUP] Completed.")

@app.post("/api/warmup/start")
def start_warmup(background_tasks: BackgroundTasks):
    if state["warmup_done"]:
        return {"message": "Warmup already completed"}
    background_tasks.add_task(perform_warmup)
    return {"message": "Warm-up started"}

@app.get("/api/warmup/status")
def warmup_status():
    return {"done": state["warmup_done"]}

@app.post("/api/detect/run")
def run_detect():
    """
    Called by the dashboard loop. Overrides global polling and individually returns metrics
    for all 5 services!
    """
    if not state["warmup_done"]:
        return {"error": "Wait until warmup is completed"}
    if state["manual_mode"]:
        return {"error": "System frozen in manual mode"}
        
    # Poll all 5 services!
    for svc in SERVICES:
        svc_state = state["services"][svc]
        features = prometheus_client.fetch_metrics(svc)
        
        confidence, new_votes, is_anomaly = detector.run_detector(features, svc_state["votes"])
        
        svc_state["votes"] = new_votes
        svc_state["confidence"] = confidence
        svc_state["is_anomaly"] = is_anomaly
        svc_state["features"] = features
    
    # Returns the mass dictionary of all 5 services to generate cards!
    return state["services"]

@app.post("/api/recover")
def recover_service(service_name: str, db: Session = Depends(get_db)):
    if state["manual_mode"]:
        raise HTTPException(status_code=400, detail="Automation frozen in manual mode")
        
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail="Service not tracked")
        
    svc_state = state["services"][service_name]
    
    should_act, reason = decision.evaluate_decision(
        svc_state["confidence"], 
        svc_state["votes"], 
        service_name, 
        state["cooldowns"]
    )
    
    if not should_act:
        return {"status": "skipped", "reason": reason}
        
    pod_deleted, timestamp = recovery.restart_pod(service_name)
    state["cooldowns"][service_name] = timestamp
    
    status = verifier.verify_recovery(pod_deleted, svc_state["baseline_avg"])
    
    if status == "FAILED":
        state["manual_mode"] = True
    
    new_incident = models.Incident(
        service=service_name,
        confidence=svc_state["confidence"],
        votes=svc_state["votes"],
        action=f"restarted 1 pod ({pod_deleted})",
        pod_name=pod_deleted,
        status=status,
        timestamp=timestamp
    )
    
    db.add(new_incident)
    db.commit()
    db.refresh(new_incident)
    
    return new_incident

@app.get("/api/incidents")
def get_incidents(db: Session = Depends(get_db)):
    return db.query(models.Incident).order_by(models.Incident.timestamp.desc()).all()

@app.get("/api/latest")
def get_latest_incident(db: Session = Depends(get_db)):
    incident = db.query(models.Incident).order_by(models.Incident.timestamp.desc()).first()
    if not incident:
        return {"message": "No incidents yet"}
    return incident

@app.post("/api/chaos/inject")
def trigger_chaos(service: str, scenario: str):
    if service not in SERVICES and service not in ["frontend", "checkoutservice"]:
        raise HTTPException(status_code=404, detail=f"Service {service} not tracked")
    
    result = inject_chaos_safe(service, scenario)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
        
    # Simulate an immediate spike in the backend state for the dashboard demo!
    if service in state["services"]:
        state["services"][service]["is_anomaly"] = True
        state["services"][service]["confidence"] = 99.0
        state["services"][service]["votes"] = [1, 1, 1, 1, 1]
    
    return result

@app.post("/api/chaos/cleanup")
def chaos_cleanup():
    cleanup_all()
    return {"message": "All chaos experiments cleaned up"}
