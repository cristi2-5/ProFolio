import asyncio
from app.database import async_session_factory
from app.models.user import User
from app.models.resume import ParsedResume
from sqlalchemy import select

async def main():
    async with async_session_factory() as db:
        # Get test user
        stmt = select(User).where(User.email == 'test@example.com')
        user = (await db.execute(stmt)).scalar_one_or_none()
        
        if not user:
            print("Test user not found.")
            return

        # Seed realistic parsed resume data matching their preferences
        parsed_data = {
            "skills": ["JavaScript", "React", "CSS", "HTML", "TypeScript", "Frontend Development", "UI/UX", "TailwindCSS"],
            "experience": [
                {
                    "title": "Frontend Developer",
                    "company": "Tech Corp",
                    "description": "Built responsive React web applications using JavaScript and CSS."
                }
            ]
        }
        
        resume = ParsedResume(
            user_id=user.id,
            original_filename="test_resume.pdf",
            storage_path="/dev/null",
            parsed_data=parsed_data,
            is_active=True
        )
        db.add(resume)
        await db.commit()
        print("Successfully injected realistic test ParsedResume for test user!")

asyncio.run(main())
