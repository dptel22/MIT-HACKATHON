# KubeResilience Chaos Engine

This document details the newly built Chaos Engine layer added to the KubeResilience backend, based strictly on the provided `chaosengine.txt` specification.

## 1. Overview
The Chaos Engine allows your KubeResilience React Dashboard to actively inject faults (like CPU spikes, Memory leaks, or Network Packet Loss) directly into the Google Online Boutique microservices. 

It functions as the "trigger" making the AI detection loop react live during your hackathon demo.

## 2. Implemented Architecture
We created a brand new Python package within your backend system:
```text
chaos/
├── __init__.py                 ← Makes it a Python package
├── chaos_engine.py             ← Controller script bridging FastAPI and kubectl
└── manifests/
    ├── pod_kill.yaml           ← Native PodChaos
    ├── cpu_stress.yaml         ← StressChaos (90% CPU)
    ├── memory_leak.yaml        ← StressChaos (256MB RAM)
    ├── network_latency.yaml    ← NetworkChaos (300ms delay)
    └── packet_loss.yaml        ← NetworkChaos (45% drop)
```

## 3. Backend Integration (FastAPI additions)
We injected two newly available endpoints into `main.py` specifically for your frontend dashboard to interact with:

### `POST /api/chaos/inject`
* **Query Parameters:** `service` (e.g. `cartservice`), `scenario` (e.g. `cpu_stress`)
* **Purpose:** Uses `chaos_engine.py` to compile the YAML template dynamically and apply it via `kubectl`. 
* **Demo-Friendly Mock:** Because the real Prometheus connection is currently mocked, this endpoint automatically spikes the target service's anomaly flags (`confidence = 99.0`, `votes = [1,1,1,1,1]`) so your dashboard instantly renders the anomaly exactly as it would if the AI triggered.

### `POST /api/chaos/cleanup`
* **Purpose:** Erases all active `podchaos`, `stresschaos`, and `networkchaos` experiments via `kubectl` to reset your cluster manually before doing another demo.

## 4. Safety Guardrails Installed
Following the `chaosengine.txt` commands, the following rules have been hard-coded into `chaos_engine.py`:
1. **Critical Service Blocking:** Any API attempt to inject chaos into `frontend` or `checkoutservice` is strictly blocked by `inject_chaos_safe()` to prevent permanent demo breakage.
2. **Chaos Mesh Fallback:** If you have not installed the Chaos Mesh helm chart yet, the backend will still execute `pod_kill` commands by falling back to vanilla `kubectl delete pod` dynamically. Any other stressor (like `cpu_stress`) will return a clean API gracefully telling the dashboard it isn't installed.

## 5. Next Steps for You
Hand the checklist from `chaosengine.txt` to your teammate so they can install the correct `helm install` configuration for Chaos Mesh onto the cluster. From there, your dashboard has everything it needs to trigger total chaos!
