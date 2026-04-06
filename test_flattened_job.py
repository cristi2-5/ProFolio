import asyncio
import httpx
import json

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        print("Logging in...")
        res = await client.post("/api/auth/login", json={"email": "test@example.com", "password": "TestPass123!"})
        token = res.json()["access_token"]
        
        print("Fetching jobs list...")
        jobs_res = await client.get("/api/jobs/", headers={"Authorization": f"Bearer {token}"})
        jobs = jobs_res.json()["jobs"]
        
        if not jobs:
            print("No jobs found to test.")
            return
            
        job_id = jobs[0]["id"]
        print(f"Testing GET /api/jobs/{job_id} for flattened fields...")
        detail_res = await client.get(f"/api/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
        data = detail_res.json()
        
        # Check if job_title is at the top level
        if "job_title" in data and data["job_title"]:
            print(f"SUCCESS: Flattened job_title found: {data['job_title']}")
        else:
            print("FAILURE: Flattened job_title NOT found at top level.")
            print("Keys found:", data.keys())

        # Check for company_name
        if "company_name" in data and data["company_name"]:
            print(f"SUCCESS: Flattened company_name found: {data['company_name']}")

asyncio.run(main())
