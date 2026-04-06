import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        print("Logging in...")
        res = await client.post("/api/auth/login", json={"email": "test@example.com", "password": "TestPass123!"})
        if res.status_code != 200:
            print("Login failed:", res.text)
            return
        
        token = res.json()["access_token"]
        
        print("Fetching jobs...")
        jobs_res = await client.get("/api/jobs/", headers={"Authorization": f"Bearer {token}"})
        print(f"List response status: {jobs_res.status_code}")
        
        data = jobs_res.json()
        print(f"Total count returned: {data.get('total_count')}")
        jobs = data.get('jobs', [])
        print(f"Jobs returned in array: {len(jobs)}")
        
        if len(jobs) > 0:
            print(f"First job: {jobs[0]['job_title']} - status: {jobs[0]['status']}")

asyncio.run(main())
