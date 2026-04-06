import asyncio
import httpx

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
        print(f"Testing GET /api/jobs/{job_id}...")
        detail_res = await client.get(f"/api/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
        print(f"Response status: {detail_res.status_code}")
        if detail_res.status_code == 200:
            print(f"Job found: {detail_res.json()['job']['job_title']} at {detail_res.json()['job']['company_name']}")

asyncio.run(main())
