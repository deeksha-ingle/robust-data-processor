import os
import json
import random
import uuid

DATA_DIR = "load_test_data"

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def generate_data(count=1000):
    ensure_dir(DATA_DIR)
    print(f"Generating {count} files in {DATA_DIR}...")
    
    for i in range(count):
        tenant_id = random.choice(["acme", "beta", "gamma", "delta"])
        log_id = str(uuid.uuid4())
        # Random text length between 50 and 200 chars
        text_content = f"Log entry {i} for {tenant_id}. User 555-0199 performed action. " + "x" * random.randint(20, 150)
        
        if random.random() > 0.5:
            # JSON File
            filename = os.path.join(DATA_DIR, f"log_{i}.json")
            data = {
                "tenant_id": tenant_id,
                "log_id": log_id,
                "text": text_content
            }
            with open(filename, "w") as f:
                json.dump(data, f)
        else:
            # Text File
            filename = os.path.join(DATA_DIR, f"log_{i}.txt")
            # For text files, we need to know the tenant_id when sending, 
            # so we'll encode it in the filename for the sender script to pick up: tenant_id__filename
            filename = os.path.join(DATA_DIR, f"{tenant_id}__log_{i}.txt")
            with open(filename, "w") as f:
                f.write(text_content)
                
    print("Generation complete.")

if __name__ == "__main__":
    generate_data()
