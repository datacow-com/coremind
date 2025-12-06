import argparse
import asyncio
import aiohttp
import os
import time
import json
from typing import List

async def ingest_file(session, file_path: str, url: str, sem: asyncio.Semaphore, kb_name: str):
    async with sem:
        file_name = os.path.basename(file_path)
        # Check if file exists
        if not os.path.exists(file_path):
            print(f"Skipping {file_name}, not found.")
            return None
            
        try:
            with open(file_path, 'rb') as f:
                # Use FormData
                data = aiohttp.FormData()
                data.add_field('file', f, filename=file_name)
                # Params
                params = {"index": "true", "kb_name": kb_name}
                
                # Use auto endpoint which detects type and routes
                async with session.post(url, data=data, params=params) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        print(f"SUCCESS: {file_name} -> {res.get('document_id')}")
                        return res
                    else:
                        text = await resp.text()
                        print(f"FAILED: {file_name} -> {resp.status} {text}")
                        return None
        except Exception as e:
            print(f"ERROR: {file_name} -> {str(e)}")
            return None

async def batch_ingest(
    source_dir: str, 
    base_url: str, 
    concurrency: int, 
    kb_name: str
):
    url = f"{base_url.rstrip('/')}/api/documents/upload" # Or new /api/ingest/run if we want direct control
    # Legacy upload endpoint calls create_ingest_graph_for_kb which uses new pipeline if configured
    
    files = []
    for root, _, filenames in os.walk(source_dir):
        for name in filenames:
            if not name.startswith('.'): # Skip hidden
                files.append(os.path.join(root, name))
    
    print(f"Found {len(files)} files in {source_dir}")
    
    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session:
        tasks = [ingest_file(session, f, url, sem, kb_name) for f in files]
        
        start = time.time()
        results = await asyncio.gather(*tasks)
        end = time.time()
        
        success_count = len([r for r in results if r])
        print(f"\nBatch Completed in {end-start:.2f}s")
        print(f"Success: {success_count}/{len(files)}")

def main():
    parser = argparse.ArgumentParser(description="Batch Ingestion Script for OmniRAG")
    parser.add_argument("--dir", required=True, help="Directory containing files to ingest")
    parser.add_argument("--url", default="http://localhost:8000", help="Base API URL")
    parser.add_argument("--workers", type=int, default=5, help="Concurrency level")
    parser.add_argument("--kb", default="default", help="Knowledge Base Name")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.dir):
        print(f"Directory {args.dir} does not exist.")
        return

    asyncio.run(batch_ingest(args.dir, args.url, args.workers, args.kb))

if __name__ == "__main__":
    main()

