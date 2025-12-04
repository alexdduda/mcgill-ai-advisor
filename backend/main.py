# backend/main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import anthropic
import os
from contextlib import asynccontextmanager
from typing import List
import re

# Import modules
from database import get_db, engine, Base
from repositories import CourseRepository, UserRepository, ChatRepository

# --- CONFIGURATION ---
SUBJECT_MAP = {
    "computer science": "COMP",
    "cs": "COMP",
    "comp": "COMP",
    "math": "MATH",
    "biology": "BIOL",
    "physics": "PHYS",
    "chemistry": "CHEM",
    "engineering": "ECSE", 
    "psychology": "PSYC",
    "management": "MGCR",
    "economics": "ECON",
    "arts": "ARTH",
    "sociology": "SOCI",
    "history": "HIST"
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        repo = CourseRepository(session)
        courses = await repo.get_all_courses()
        if not courses:
            print("🌱 Seeding database from CSV...")
            await repo.seed_from_csv("ClassAverageCrowdSourcing.csv")
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# --- Models ---
class ChatRequest(BaseModel):
    username: str = "guest"
    message: str

# REMOVED: CourseCard class
# REMOVED: recommendations list from response

class ChatResponse(BaseModel):
    response: str

# --- Endpoints ---

@app.get("/history/{username}")
async def get_history(username: str, db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    chat_repo = ChatRepository(db)
    user = await user_repo.get_or_create_user(username)
    history = await chat_repo.get_history(user.id, limit=20)
    return [{"role": msg.role, "content": msg.content} for msg in history]

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    try:
        user_repo = UserRepository(db)
        chat_repo = ChatRepository(db)
        course_repo = CourseRepository(db)
        
        # 1. Identity & Storage
        user = await user_repo.get_or_create_user(request.username)
        await chat_repo.add_message(user.id, "user", request.message)
        
        # 2. Retrieve Previous Context (Memory)
        profile = user.profile_data or {}
        last_search = profile.get("last_search", {})
        
        active_subject = last_search.get("subject")
        active_min_level = last_search.get("min_level", 0)
        active_max_level = last_search.get("max_level", 900)

        # 3. Analyze New Message for UPDATES
        msg_lower = request.message.lower()
        context_updated = False
        
        # Update Subject
        for keyword, prefix in SUBJECT_MAP.items():
            if keyword in msg_lower:
                active_subject = prefix
                context_updated = True
                break
        
        # Update Level
        if any(w in msg_lower for w in ["freshman", "100-level", "intro"]):
            active_min_level, active_max_level = 100, 199
            context_updated = True
        elif any(w in msg_lower for w in ["sophomore", "200-level"]):
            active_min_level, active_max_level = 200, 299
            context_updated = True
        elif any(w in msg_lower for w in ["junior", "300-level"]):
            active_min_level, active_max_level = 300, 399
            context_updated = True
        elif any(w in msg_lower for w in ["senior", "400-level", "500-level", "advanced", "grad"]):
            active_min_level, active_max_level = 400, 600
            context_updated = True

        # Save updates
        if context_updated:
            await user_repo.update_profile(request.username, {
                "last_search": {
                    "subject": active_subject,
                    "min_level": active_min_level,
                    "max_level": active_max_level
                }
            })

        # 4. Perform Query
        trigger_words = ["recommend", "suggest", "easy", "hard", "difficult", "worst", "best", "course", "class"]
        should_search = any(w in msg_lower for w in trigger_words)
        
        context_injection = ""
        
        if should_search and active_subject:
            all_courses = await course_repo.get_all_courses()
            
            # Filter Logic
            filtered = []
            for c in all_courses:
                # Subject Filter
                if not c.code.startswith(active_subject): continue
                
                # Level Filter
                try:
                    code_num = int(re.search(r'\d+', c.code).group())
                    if not (active_min_level <= code_num <= active_max_level): continue
                except:
                    continue
                
                # Data Validity Filter
                if c.class_average is None or c.class_average == 0: continue
                
                filtered.append(c)

            # Sort Logic
            if filtered:
                hard_keywords = ["hard", "difficult", "challenging", "complex", "worst", "lowest", "advanced"]
                is_hard_query = any(w in msg_lower for w in hard_keywords)
                
                # Hard/Advanced = Sort Ascending (Low GPA first)
                # Easy = Sort Descending (High GPA first)
                sorted_courses = sorted(filtered, key=lambda x: x.class_average, reverse=not is_hard_query)
                
                # Pick top 5 matches to give Claude variety
                top_matches = sorted_courses[:5]
                
                # Format as TEXT string for Claude
                rec_str = "; ".join([f"{c.code} (Avg GPA: {c.class_average})" for c in top_matches])
                
                context_injection = (
                    f"\n\n[SYSTEM DATA]: I used your active filters (Subject: {active_subject}, Level: {active_min_level}-{active_max_level}). "
                    f"Here are the matches sorted by {'DIFFICULTY' if is_hard_query else 'HIGHEST GRADES'}: {rec_str}. "
                    "These are REAL stats from McGill. Discuss these specific courses using your own knowledge of their titles and content."
                )
            else:
                context_injection = f"\n\n[SYSTEM NOTE]: I searched for {active_subject} courses (Level {active_min_level}-{active_max_level}) but found 0 matches in the database."

        # 5. Send to Claude
        recent_history = await chat_repo.get_history(user.id, limit=6)
        anthropic_messages = []
        for msg in recent_history:
            if msg.content != request.message: 
                anthropic_messages.append({"role": msg.role, "content": msg.content})
        
        final_user_content = request.message + context_injection
        anthropic_messages.append({"role": "user", "content": final_user_content})

        system_prompt = "You are a helpful McGill Academic Advisor. Use the [SYSTEM DATA] provided to answer accurately. You do not need to display cards, just chat naturally."
        
        models = ["claude-3-sonnet-20240229", "claude-3-opus-20240229"]
        bot_reply = "I'm having trouble thinking right now."
        
        for model in models:
            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=800,
                    system=system_prompt,
                    messages=anthropic_messages
                )
                bot_reply = response.content[0].text
                break
            except Exception:
                continue

        await chat_repo.add_message(user.id, "assistant", bot_reply)
        
        return {"response": bot_reply}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))