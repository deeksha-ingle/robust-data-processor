import requests
import time
import threading
import random
import uuid
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor

def send_request(api_url, tenant_id):
    log_id = str(uuid.uuid4())
    text = f"Stress test message {log_id} with sensitive info 555-0199 " * random.randint(1, 5)
    
    try:
        if random.choice([True, False]):
            # JSON
            payload = {
                "tenant_id": tenant_id,
                "log_id": log_id,
                "text": text
            }
            start = time.time()
            resp = requests.post(f"{api_url}/ingest", json=payload)
            duration = time.time() - start
        else:
            # Text
            headers = {"X-Tenant-ID": tenant_id, "Content-Type": "text/plain"}
            start = time.time()
            resp = requests.post(f"{api_url}/ingest", data=text, headers=headers)
            duration = time.time() - start
            
        return resp.status_code, duration
    except Exception as e:
        return 0, 0

def run_stress_test(api_url, rpm, duration_sec):
    print(f"Starting stress test against {api_url}")
    print(f"Target: {rpm} RPM for {duration_sec} seconds")
    
    delay = 60.0 / rpm
    total_requests = int((rpm / 60.0) * duration_sec)
    
    results = []
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        start_time = time.time()
        
        for i in range(total_requests):
            tenant_id = f"tenant-{random.randint(1, 5)}"
            futures.append(executor.submit(send_request, api_url, tenant_id))
            
            # Simple pacing
            time_elapsed = time.time() - start_time
            expected_time = (i + 1) * delay
            if expected_time > time_elapsed:
                time.sleep(expected_time - time_elapsed)
                
        for f in futures:
            results.append(f.result())
            
    # Analyze
    success = len([r for r in results if r[0] == 202])
    failures = len([r for r in results if r[0] != 202])
    avg_time = sum([r[1] for r in results]) / len(results) if results else 0
    
    print("\n--- Results ---")
    print(f"Total Requests: {len(results)}")
    print(f"Success: {success}")
    print(f"Failures: {failures}")
    print(f"Avg Response Time: {avg_time:.4f}s")
    
    if failures > 0:
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test")
    parser.add_argument("url", help="API URL")
    parser.add_argument("--rpm", type=int, default=1000, help="Requests per minute")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    
    args = parser.parse_args()
    run_stress_test(args.url, args.rpm, args.duration)
