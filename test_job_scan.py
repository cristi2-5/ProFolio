#!/usr/bin/env python3
"""
Test script for job scanning functionality.
"""

import asyncio
import httpx

async def test_job_scanning():
    """Test the complete job scanning flow."""
    base_url = "http://localhost:8000"

    async with httpx.AsyncClient() as client:
        print("=== Testing Job Scanning Functionality ===")

        # 1. Register a test user
        print("\n1. Registering test user...")
        register_data = {
            "email": "testuser@test.com",
            "password": "Test123456",
            "full_name": "Test User",
            "seniority_level": "senior"
        }

        try:
            response = await client.post(f"{base_url}/api/auth/register", json=register_data)
            if response.status_code == 201:
                print("✅ User registered successfully")
            elif response.status_code == 409:
                print("ℹ️ User already exists, proceeding...")
            else:
                print(f"❌ Registration failed: {response.status_code} - {response.text}")
                return
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return

        # 2. Login to get token
        print("\n2. Logging in...")
        login_data = {
            "email": "testuser@test.com",
            "password": "Test123456"
        }

        try:
            response = await client.post(f"{base_url}/api/auth/login", json=login_data)
            if response.status_code != 200:
                print(f"❌ Login failed: {response.status_code} - {response.text}")
                return

            token_data = response.json()
            token = token_data["access_token"]
            print("✅ Login successful")

            # Set authorization header for subsequent requests
            client.headers["Authorization"] = f"Bearer {token}"

        except Exception as e:
            print(f"❌ Login error: {e}")
            return

        # 3. Set job preferences
        print("\n3. Setting job preferences...")
        preferences_data = {
            "desired_title": "Software Engineer",
            "location_type": "remote",
            "keywords": ["Python", "FastAPI", "React"]
        }

        try:
            response = await client.post(f"{base_url}/api/jobs/preferences", json=preferences_data)
            if response.status_code in [200, 201]:
                print("✅ Job preferences set successfully")
            else:
                print(f"❌ Failed to set preferences: {response.status_code} - {response.text}")
                return
        except Exception as e:
            print(f"❌ Preferences error: {e}")
            return

        # 4. Trigger job scan
        print("\n4. Triggering job scan...")
        try:
            response = await client.post(f"{base_url}/api/jobs/scan")
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            print(f"Response content: {response.text}")

            if response.status_code == 200:
                result = response.json()
                print("✅ Job scan triggered successfully!")
                print(f"Jobs found: {result.get('jobs_found', 0)}")
                print(f"Message: {result.get('message', 'No message')}")
                if result.get('jobs'):
                    print("Sample jobs:")
                    for job in result['jobs'][:3]:
                        print(f"  - {job.get('job_title')} at {job.get('company_name')}")
            else:
                print(f"❌ Job scan failed: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"❌ Job scan error: {e}")

        # 5. List jobs to see if any were found
        print("\n5. Checking job listings...")
        try:
            response = await client.get(f"{base_url}/api/jobs/")
            if response.status_code == 200:
                jobs = response.json()
                print(f"✅ Found {len(jobs)} jobs in database")
                for job in jobs[:3]:
                    print(f"  - {job.get('job', {}).get('job_title')} at {job.get('job', {}).get('company_name')}")
            else:
                print(f"❌ Failed to list jobs: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Job listing error: {e}")

if __name__ == "__main__":
    asyncio.run(test_job_scanning())