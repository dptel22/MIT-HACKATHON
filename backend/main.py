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
from config import DEMO_MODE, KUBE_NAMESPACE
from chaos.chaos_engine import inject_chaos_safe, cleanup_all
from service_catalog import (
    get_non_critical_services,
    get_supported_chaos_scenarios,
    get_supported_services,
)

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="KubeResilience", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVICES = get_supported_services()
CHAOS_SERVICES = get_non_critical_services()
CHAOS_SCENARIOS = get_supported_chaos_scenarios()
AUTO_CHAOS_INTERVAL_SECONDS = 10 if DEMO_MODE else 30
FORCED_ANOMALY_GRACE_SECONDS = 45

# Independent States!
state = {
    "warmup_done": True, # True by default as baselines are pre-loaded by detector
    "manual_mode": False,
    "auto_chaos": False,
    "cooldowns": {},
    "services": {
        svc: {
            "votes": [],
            "confidence": 0.0,
            "is_anomaly": False,
            "circuit_broken": False,
            "recovery_in_progress": False,
            "cooldown": 0,
            "forced_anomaly_until": 0.0,
            "features": {"p95_latency_ms": 0.0, "error_rate_pct": 0.0, "cpu_cores": 0.0, "memory_mb": 0.0}
        } for svc in SERVICES
    }
}


def _service_has_active_incident(service_name: str) -> bool:
    svc_state = state["services"][service_name]
    return bool(
        svc_state.get("is_anomaly")
        or svc_state.get("recovery_in_progress")
    )


def _service_ready_for_auto_chaos(service_name: str) -> bool:
    svc_state = state["services"][service_name]
    cooldown_active, _ = decision.is_cooldown_active(service_name)
    return not bool(
        _service_has_active_incident(service_name)
        or svc_state.get("circuit_broken")
        or cooldown_active
    )

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def start_auto_chaos_loop():
    import random
    async def loop():
        while True:
            await asyncio.sleep(AUTO_CHAOS_INTERVAL_SECONDS)
            if state["auto_chaos"] and not state["manual_mode"]:
                async def inject_task(svc_target):
                    scenario = random.choice(CHAOS_SCENARIOS)
                    svc_state = state["services"][svc_target]
                    if _service_ready_for_auto_chaos(svc_target):
                        print(f"[AUTO-CHAOS] Assailing {svc_target} with {scenario}")
                        result = await asyncio.to_thread(inject_chaos_safe, svc_target, scenario)
                        if result["success"]:
                            state["services"][svc_target]["is_anomaly"] = True
                            state["services"][svc_target]["confidence"] = 99.0
                            state["services"][svc_target]["votes"] = [1, 1, 1, 1, 1]
                            state["services"][svc_target]["forced_anomaly_until"] = time.time() + FORCED_ANOMALY_GRACE_SECONDS
                            prometheus_client.set_demo_chaos(svc_target, scenario)

                available_targets = [
                    service_name
                    for service_name in CHAOS_SERVICES
                    if _service_ready_for_auto_chaos(service_name)
                ]
                if not available_targets:
                    continue

                if DEMO_MODE:
                    # Keep the live demo readable by running one incident at a time,
                    # but don't let a healed service's cooldown stall the whole showcase.
                    if any(_service_has_active_incident(service_name) for service_name in CHAOS_SERVICES):
                        continue
                    await inject_task(random.choice(available_targets))
                    continue

                num_targets = random.randint(1, min(3, len(available_targets)))
                targets = random.sample(available_targets, num_targets)
                tasks = [inject_task(t) for t in targets]
                await asyncio.gather(*tasks)
    asyncio.create_task(loop())

@app.get("/api/health")
def read_health():
    return {"status": "ok"}

@app.get("/api/services")
def list_services():
    """Returns the exact list of tracked services for the frontend."""
    return {"services": SERVICES}


@app.get("/api/config")
def get_runtime_config():
    return {
        "services": SERVICES,
        "chaos_services": CHAOS_SERVICES,
        "chaos_scenarios": CHAOS_SCENARIOS,
        "demo_mode": DEMO_MODE,
        "namespace": KUBE_NAMESPACE,
        "auto_chaos": state["auto_chaos"],
    }


@app.post("/api/warmup/start")
def start_warmup():
    state["warmup_done"] = True
    return {"message": "Warm-up skipped (using pre-trained baseline stats)"}

@app.get("/api/warmup/status")
def warmup_status():
    return {"done": state["warmup_done"]}

@app.post("/api/detect/run")
def run_detect():
    """
    Called by the dashboard loop. Overrides global polling and individually returns metrics.
    """
    if not state["warmup_done"]:
        return {"error": "Wait until warmup is completed"}
    if state["manual_mode"]:
        return {"error": "System frozen in manual mode"}
        
    for svc in SERVICES:
        svc_state = state["services"][svc]
        features = prometheus_client.fetch_metrics(svc)

        force_anomaly = time.time() < float(svc_state.get("forced_anomaly_until") or 0.0)
        if force_anomaly:
            svc_state["votes"] = [1, 1, 1, 1, 1]
            svc_state["confidence"] = 99.0
            svc_state["is_anomaly"] = True
            svc_state["features"] = features
        else:
            det_result = detector.run_detection(features, svc_state["votes"])
            
            # vote buffer is modified in place, but we can assign confidence and anomaly state
            svc_state["confidence"] = det_result["confidence"]
            svc_state["is_anomaly"] = det_result["triggered"]
            svc_state["features"] = features
        
        cooldown_active, cooldown_rem = decision.is_cooldown_active(svc)
        svc_state["cooldown"] = cooldown_rem
        
        if (
            not cooldown_active
            and not svc_state.get("recovery_in_progress")
            and svc_state.get("circuit_broken")
        ):
            svc_state["circuit_broken"] = False
            print(f"[CIRCUIT BREAKER] Reset on {svc}. Cooldown expired.")
    
    return state["services"]

@app.post("/api/recover")
def recover_service(service_name: str, db: Session = Depends(get_db)):
    if state["manual_mode"]:
        raise HTTPException(status_code=400, detail="Automation frozen in manual mode")
        
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail="Service not tracked")
        
    svc_state = state["services"][service_name]
    if svc_state.get("recovery_in_progress"):
        svc_state["circuit_broken"] = True
        return {"status": "skipped", "reason": "recovery_in_progress"}
    
    # Delegate to external Decision Engine
    res = decision.make_decision(
        service=service_name,
        confidence=svc_state["confidence"],
        triggered=svc_state["is_anomaly"],
        metrics=svc_state["features"],
        vote_buffer=svc_state["votes"]
    )
    
    if res.action != "RECOVER":
        if "cooldown" in res.reason.lower() and svc_state["confidence"] >= 80:
            svc_state["circuit_broken"] = True
            print(f"[CIRCUIT BREAKER] Activated on {service_name} to intercept traffic and prevent loss during Cooldown!")
        return {"status": "skipped", "reason": res.reason}

    svc_state["recovery_in_progress"] = True
    svc_state["circuit_broken"] = True

    status = None
    try:
        pod_deleted, timestamp = recovery.restart_pod(service_name)
        
        incident_votes = list(svc_state["votes"])
        incident_confidence = svc_state["confidence"]
        
        prometheus_client.clear_demo_chaos(service_name)
        svc_state["forced_anomaly_until"] = 0.0
        
        baseline = detector.get_baseline(service_name)
        
        status = verifier.verify_recovery(service_name, pod_deleted, baseline)
        
        # Route both success and failure through the shared cooldown hook so
        # a bad recovery attempt only freezes the affected service, not the
        # entire automation loop.
        try:
            decision.on_recovery_complete(
                service=service_name,
                verification_result={
                    "status": status,
                    "detail": f"Post-recovery verification returned {status}",
                },
                severity_label=res.severity_label,
            )
        except Exception as e:
            print(f"Warning: Failed to log adaptive cooldown record: {e}")
        
        new_incident = models.Incident(
            service=service_name,
            confidence=incident_confidence,
            votes=incident_votes,
            action=f"restarted 1 pod ({pod_deleted})",
            pod_name=pod_deleted,
            status=status,
            timestamp=timestamp
        )
        
        db.add(new_incident)
        db.commit()
        db.refresh(new_incident)

        if status == "HEALED":
            svc_state["votes"].clear()
            svc_state["confidence"] = 0.0
            svc_state["is_anomaly"] = False
        
        return new_incident
    finally:
        svc_state["recovery_in_progress"] = False
        cooldown_active, cooldown_remaining = decision.is_cooldown_active(service_name)
        svc_state["cooldown"] = cooldown_remaining
        if not cooldown_active and not svc_state.get("is_anomaly"):
            svc_state["circuit_broken"] = False

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
    if service not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service} not tracked")
    
    result = inject_chaos_safe(service, scenario)
    if not result["success"]:
        detail = result.get("error") or result.get("message") or "Chaos injection failed"
        raise HTTPException(status_code=400, detail=detail)
        
    if service in state["services"]:
        state["services"][service]["is_anomaly"] = True
        state["services"][service]["confidence"] = 99.0
        state["services"][service]["votes"] = [1, 1, 1, 1, 1]
        state["services"][service]["forced_anomaly_until"] = time.time() + FORCED_ANOMALY_GRACE_SECONDS
        prometheus_client.set_demo_chaos(service, scenario)
    
    return result

@app.post("/api/chaos/cleanup")
def chaos_cleanup():
    cleanup_all()
    prometheus_client.clear_demo_chaos()
    state["manual_mode"] = False
    state["auto_chaos"] = False
    for svc_state in state["services"].values():
        svc_state["votes"].clear()
        svc_state["confidence"] = 0.0
        svc_state["is_anomaly"] = False
        svc_state["circuit_broken"] = False
        svc_state["recovery_in_progress"] = False
        svc_state["cooldown"] = 0
        svc_state["forced_anomaly_until"] = 0.0
    return {"message": "All chaos experiments cleaned up"}

@app.post("/api/chaos/auto/start")
def start_auto_chaos():
    state["auto_chaos"] = True
    return {"message": "Auto Chaos Enabled"}

@app.post("/api/chaos/auto/stop")
def stop_auto_chaos():
    state["auto_chaos"] = False
    return {"message": "Auto Chaos Disabled"}
