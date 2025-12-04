import asyncio
from database import AsyncSessionLocal
from repositories import CourseRepository

async def reseed():
    print("🔄 Starting Database Reseed...")
    async with AsyncSessionLocal() as session:
        repo = CourseRepository(session)
        # Ensure this matches your actual filename
        await repo.seed_from_csv("ClassAverageCrowdSourcing.csv")
    print("✨ Reseed Complete!")

if __name__ == "__main__":
    asyncio.run(reseed())