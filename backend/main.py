from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from prompts import SYSTEM_PROMPT
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Construct absolute path to data/vectors
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
vectors_path = os.path.join(project_root, "data", "vectors")

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ.get("GEMINI_API_KEY")

embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2"
)

db = FAISS.load_local(
    vectors_path,
    embeddings,
    allow_dangerous_deserialization=True
)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0
)

class Query(BaseModel):
    message: str
    session_id: str = "default"

# --- Booking Logic ---
import json
from datetime import datetime

class BookingState:
    IDLE = "IDLE"
    ASK_NAME = "ASK_NAME"
    ASK_PHONE = "ASK_PHONE"
    ASK_EMAIL = "ASK_EMAIL"
    ASK_SERVICE = "ASK_SERVICE"
    ASK_DATE = "ASK_DATE"
    CONFIRM = "CONFIRM"

# In-memory session store: session_id -> {state: ..., data: {...}}
sessions = {}

APPOINTMENTS_FILE = os.path.join(project_root, "data", "appointments.json")

def save_appointment(data):
    appointments = []
    if os.path.exists(APPOINTMENTS_FILE):
        with open(APPOINTMENTS_FILE, "r") as f:
            try:
                appointments = json.load(f)
            except:
                pass
    
    data["created_at"] = datetime.now().isoformat()
    appointments.append(data)
    
    # Ensure directory exists just in case
    os.makedirs(os.path.dirname(APPOINTMENTS_FILE), exist_ok=True)
    
    with open(APPOINTMENTS_FILE, "w") as f:
        json.dump(appointments, f, indent=4)

def process_booking(session_id: str, message: str, state_data: dict):
    state = state_data.get("state", BookingState.IDLE)
    data = state_data.get("data", {})
    msg = message.strip().lower()
    
    if state == BookingState.IDLE:
        # Check for booking intent
        if "book" in msg and "appointment" in msg:
            sessions[session_id] = {"state": BookingState.ASK_NAME, "data": {}}
            return {"message": "Sure! I can help you with that. What is your name?"}
        return None  # Fallback to RAG

    if state == BookingState.ASK_NAME:
        sessions[session_id]["data"]["name"] = message
        sessions[session_id]["state"] = BookingState.ASK_PHONE
        return {"message": f"Thanks {message}. What is your phone number?"}

    if state == BookingState.ASK_PHONE:
        sessions[session_id]["data"]["phone"] = message
        sessions[session_id]["state"] = BookingState.ASK_EMAIL
        return {"message": "Got it. What is your email address?"}

    if state == BookingState.ASK_EMAIL:
        sessions[session_id]["data"]["email"] = message
        sessions[session_id]["state"] = BookingState.ASK_SERVICE
        return {"message": "Thanks. What service are you interested in?"}

    if state == BookingState.ASK_SERVICE:
        sessions[session_id]["data"]["service"] = message
        sessions[session_id]["state"] = BookingState.ASK_DATE
        return {
            "message": "And when would you like to come in? (Date and Time)",
            "ui_action": "date_picker"
        }

    if state == BookingState.ASK_DATE:
        sessions[session_id]["data"]["date"] = message
        sessions[session_id]["state"] = BookingState.CONFIRM
        name = sessions[session_id]["data"]["name"]
        phone = sessions[session_id]["data"]["phone"]
        email = sessions[session_id]["data"]["email"]
        service = sessions[session_id]["data"]["service"]
        return {"message": f"Please confirm details:\n- Name: {name}\n- Phone: {phone}\n- Email: {email}\n- Service: {service}\n- Date: {message}\n\nType 'yes' to confirm or 'cancel' to stop."}

    if state == BookingState.CONFIRM:
        if msg in ["yes", "y", "confirm", "ok"]:
            save_appointment(sessions[session_id]["data"])
            sessions[session_id] = {"state": BookingState.IDLE, "data": {}}
            return {"message": "Appointment saved! We look forward to seeing you."}
        elif msg in ["no", "cancel", "stop"]:
            sessions[session_id] = {"state": BookingState.IDLE, "data": {}}
            return {"message": "Booking cancelled."}
        else:
            return {"message": "Please type 'yes' to save the appointment or 'cancel' to stop."}

    return None

@app.post("/chat")
def chat(q: Query):
    session_id = q.session_id
    
    # Initialize session if not exists
    if session_id not in sessions:
        sessions[session_id] = {"state": BookingState.IDLE, "data": {}}
    
    # Try to process booking flow
    booking_response = process_booking(session_id, q.message, sessions[session_id])
    if booking_response:
        return {
            "reply": booking_response["message"],
            "ui_action": booking_response.get("ui_action")
        }

    # Fallback to RAG
    docs = db.similarity_search(q.message, k=4)
    context = "\n".join([d.page_content for d in docs])

    prompt = f"""
{SYSTEM_PROMPT}

Context:
{context}

Question: {q.message}
"""

    res = llm.invoke(prompt)
    return {"reply": res.content}
