import argparse
import asyncio
import time
from locust import HttpUser, task, between, events

# To run: locust -f scripts/load_test.py --headless -u 10 -r 2 --host http://localhost:8000

class IngestUser(HttpUser):
    wait_time = between(1, 5)
    
    def on_start(self):
        # Setup authentication if needed (e.g. login and get token)
        # self.client.headers.update({"Authorization": "Bearer ..."})
        pass

    @task(1)
    def ingest_pdf(self):
        # We need a sample file. Assuming 'test.pdf' exists.
        # In real scenario, we might generate random files or pick from a pool.
        
        if not os.path.exists("test.pdf"):
            with open("test.pdf", "wb") as f:
                f.write(b"%PDF-1.4 mock pdf content")
                
        with open("test.pdf", "rb") as f:
            files = {'file': ('test.pdf', f, 'application/pdf')}
            # Use legacy endpoint for simplicity as it wraps new pipeline
            self.client.post("/api/documents/upload", files=files, params={"index": "true", "kb_name": "load_test"})

    @task(3)
    def chat_query(self):
        payload = {
            "query": "test query",
            "kb_name": "load_test",
            "strategy_config": {"top_k": 1}
        }
        # Using chat run endpoint (non-streaming for load test simplicity, or stream and consume)
        # Locust handles streaming response latency if we read content.
        with self.client.post("/api/chat/run", json=payload, stream=True, catch_response=True) as resp:
            if resp.status_code == 200:
                # Consume stream
                for line in resp.iter_lines():
                    pass
                resp.success()
            else:
                resp.failure(f"Status {resp.status_code}")

import os
if __name__ == "__main__":
    # Quick single run check
    pass

