import asyncio
import sys
from app.database import async_session_factory
from app.models.user import User
from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume
from sqlalchemy import select

async def main():
    async with async_session_factory() as db:
        # Get the first registered user
        stmt = select(User).limit(1)
        user = (await db.execute(stmt)).scalar_one_or_none()
        
        if not user:
            print("No users found in database.")
            return

        print(f"Injecting test data for user: {user.email} (ID: {user.id})")

        # 1. Ensure user has a parsed resume (basic one)
        stmt = select(ParsedResume).where(ParsedResume.user_id == user.id)
        resume = (await db.execute(stmt)).scalar_one_or_none()
        if not resume:
            resume = ParsedResume(
                user_id=user.id,
                original_filename="sample_cv.pdf",
                file_url="local://sample_cv.pdf",
                parsed_data={"skills": ["Python", "React", "Docker"]},
                is_active=True
            )
            db.add(resume)
            await db.flush()

        # 2. Inject a Mock Job
        # Check if dummy job exists
        stmt = select(ScrapedJob).where(ScrapedJob.external_url == "https://test.adzuna.example/job/1")
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            job = ScrapedJob(
                description_hash="dummy_hash_12345",
                job_title="Senior Full Stack Python Developer",
                company_name="GoogleTech Labs",
                location="Bucharest / Remote",
                external_url="https://test.adzuna.example/job/1",
                description="Cautam un developer python cu experienta pe FastAPI, React si Docker. Va lucra la un nou produs de integrare AI.",
                source_platform="adzuna"
            )
            db.add(job)
            await db.flush()

        # 3. Link Job to User
        stmt = select(UserJob).where(UserJob.user_id == user.id, UserJob.job_id == job.id)
        user_job = (await db.execute(stmt)).scalar_one_or_none()
        if not user_job:
            user_job = UserJob(
                user_id=user.id,
                job_id=job.id,
                status="new",
                match_score=85,
            )
            db.add(user_job)
            
        await db.commit()
        print("Successfully injected test Job for UI verification!")

if __name__ == "__main__":
    asyncio.run(main())
