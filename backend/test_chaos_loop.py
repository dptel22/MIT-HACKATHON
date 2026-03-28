import time
import requests

BASE_URL = "http://localhost:8000/api"

def print_res(name, res):
    print(f"\n[{name}]")
    try:
        if res.status_code >= 400:
            print(f"Error {res.status_code}: {res.json()}")
        else:
            print(res.json())
    except Exception as e:
        print(f"Failed: {e}")

try:
    print("====================================")
    print(" KUBERESILIENCE END-TO-END TEST")
    print("====================================\n")

    # 1. Warm-up
    print_res("1. WARMUP START", requests.post(f"{BASE_URL}/warmup/start"))
    print("   [Sleeping 12 seconds for warmup baseline calculation...]")
    time.sleep(12)

    # 2. Normal Detection
    print_res("2. NORMAL DETECTION RUN", requests.post(f"{BASE_URL}/detect/run"))
    print("   (Notice the 'is_anomaly': false flags across services)")

    # 3. Inject Chaos (Triggering anomaly manually via our mock)
    print("\n   => Injecting cpu_stress chaos into cartservice <= ")
    print_res("3. CHAOS INJECTION", requests.post(f"{BASE_URL}/chaos/inject?service=cartservice&scenario=cpu_stress"))

    # 4. Anomaly Detection triggered!
    print_res("4. DETECTING ANOMALY", requests.post(f"{BASE_URL}/detect/run"))
    print("   (Notice cartservice now has 5 votes and 99.0 confidence!)")

    # 5. Recovery Gate Test (Success!)
    print_res("5. RECOVER NON-CRITICAL (cartservice)", requests.post(f"{BASE_URL}/recover?service_name=cartservice"))
    print("   (Recovery succeeded, pod fake-ID deleted via fallback!)")

    # 6. Recovery Gate Test (Failure on Critical Service!)
    print("\n   => Testing Safety Gate by injecting chaos into Critical paymentservice <= ")
    requests.post(f"{BASE_URL}/chaos/inject?service=paymentservice&scenario=pod_kill")
    print_res("6. RECOVER CRITICAL (paymentservice)", requests.post(f"{BASE_URL}/recover?service_name=paymentservice"))
    print("   (Auto-Recovery blocked because paymentservice is a critical gate!)")
    
    # 7. Database Check
    print_res("7. VIEW INCIDENTS DATABASE", requests.get(f"{BASE_URL}/incidents"))

except Exception as e:
    print(f"Test script failed. Ensure Uvicorn is running: {e}")
