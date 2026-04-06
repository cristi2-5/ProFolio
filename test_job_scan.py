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
        print("Logged in, token len:", len(token))
        
        print("Triggering scan...")
        scan_res = await client.post("/api/jobs/scan", headers={"Authorization": f"Bearer {token}"})
        print(f"Scan response status: {scan_res.status_code}")
        print("Scan response body:", scan_res.text)

asyncio.run(main())
