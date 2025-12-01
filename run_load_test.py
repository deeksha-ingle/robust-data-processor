import os
import requests
import time
import json
from concurrent.futures import ThreadPoolExecutor

DATA_DIR = "load_test_data"
API_URL = "http://localhost:8080/ingest"

def send_file(filename):
    filepath = os.path.join(DATA_DIR, filename)
    
    try:
        if filename.endswith(".json"):
            with open(filepath, "r") as f:
                data = json.load(f)
            
            start = time.time()
            response = requests.post(API_URL, json=data)
            duration = time.time() - start
            return response.status_code, duration, "json"
            
        elif filename.endswith(".txt"):
            # Extract tenant_id from filename (format: tenant_id__filename)
            parts = filename.split("__")
            if len(parts) < 2:
                return 0, 0, "error"
            tenant_id = parts[0]
            
            with open(filepath, "r") as f:
                content = f.read()
                
            headers = {
                "Content-Type": "text/plain",
                "X-Tenant-ID": tenant_id
            }
            
            start = time.time()
            response = requests.post(API_URL, data=content, headers=headers)
            duration = time.time() - start
            return response.status_code, duration, "text"
            
    except Exception as e:
        print(f"Error sending {filename}: {e}")
        return 0, 0, "error"
    
    return 0, 0, "skip"

def run_load_test():
    if not os.path.exists(DATA_DIR):
        print(f"Data directory {DATA_DIR} not found. Run generate_load_data.py first.")
        return

    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json") or f.endswith(".txt")]
    total_files = len(files)
    print(f"Found {total_files} files. Starting ingestion...")
    
    start_time = time.time()
    
    # Use ThreadPoolExecutor to simulate concurrent users/high RPM
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(send_file, files))
        
    end_time = time.time()
    total_duration = end_time - start_time
    
    success_count = len([r for r in results if r[0] == 202])
    fail_count = len([r for r in results if r[0] != 202])
    avg_latency = sum([r[1] for r in results]) / len(results) if results else 0
    
    print("\n=== Load Test Results ===")
    print(f"Total Files Processed: {total_files}")
    print(f"Total Time: {total_duration:.2f} seconds")
    print(f"Throughput: {total_files / (total_duration / 60):.2f} RPM")
    print(f"Success (202 Accepted): {success_count}")
    print(f"Failures: {fail_count}")
    print(f"Average API Latency: {avg_latency:.4f} seconds")
    
    if success_count == total_files:
        print("\nSUCCESS: System handled the load perfectly.")
    else:
        print("\nWARNING: Some requests failed.")

if __name__ == "__main__":
    run_load_test()
