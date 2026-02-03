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

def extract_booking_details(message: str, context: str = ""):
    """
    Uses LLM to extract booking details from the message, using context if available.
    Returns a dict with keys: name, phone, email, service, date.
    Values are None if not found.
    """
    schema = {
        "properties": {
            "name": {"type": "string"},
            "phone": {"type": "string"},
            "email": {"type": "string"},
            "service": {"type": "string"},
            "date": {"type": "string"}
        },
        "type": "object"
    }
    
    extraction_prompt = f"""
    Extract booking details from the user's message.
    Use the provided conversation context to resolve references like "this service" or "it".
    
    IMPORTANT:
    - If the user says "book appointment" or "schedule visit" WITHOUT naming a specific service, look at the context to see what service was discussed.
    - Do NOT extract generic terms like "appointment", "booking", "consultation", "service", "visit", "checkup" as the service name.
    - If no specific service is found in message or context, return 'service': null.
    
    Return a valid JSON object with the following fields: name, phone, email, service, date.
    If a field is not present in the message or context, set it to null.
    
    Context:
    {context}
    
    User message: "{message}"
    """
    
    try:
        # Simple invocation - better structured output handling could be done with tools/functions
        # but for this simple use case, we ask for JSON directly.
        res = llm.invoke(extraction_prompt + "\n\nReturn ONLY JSON.")
        content = res.content.strip()
        # Clean up code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
             content = content.split("```")[1].split("```")[0]
             
        data = json.loads(content)
        return data
    except Exception as e:
        print(f"Extraction error: {e}")
        return {}

def get_next_question(session_id):
    """
    Determines the next state and question based on missing data.
    """
    state_data = sessions[session_id]
    data = state_data["data"]
    state = state_data["state"]

    # Helpers for context
    name = data.get("name", "")
    service = data.get("service", "")

    # Iterate through states to find the first missing info
    # We enforce a linear order: Name -> Phone -> Email -> Service -> Date -> Confirm

    # If currently in ASK_NAME, but we already have name, move to ASK_PHONE
    if state == BookingState.ASK_NAME:
        if data.get("name"):
            sessions[session_id]["state"] = BookingState.ASK_PHONE
            state = BookingState.ASK_PHONE
        else:
            if service:
                return {"message": f"I can definitely help you book a {service}. First, what is your name?"}
            return {"message": "Sure! I can help you with that. What is your name?"}

    if state == BookingState.ASK_PHONE:
        if data.get("phone"):
            sessions[session_id]["state"] = BookingState.ASK_EMAIL
            state = BookingState.ASK_EMAIL
        else:
            return {"message": f"Thanks {name}. What is your phone number?"}

    if state == BookingState.ASK_EMAIL:
        if data.get("email"):
            sessions[session_id]["state"] = BookingState.ASK_SERVICE
            state = BookingState.ASK_SERVICE
        else:
            return {"message": "Got it. What is your email address?"}

    if state == BookingState.ASK_SERVICE:
        if data.get("service"):
            sessions[session_id]["state"] = BookingState.ASK_DATE
            state = BookingState.ASK_DATE
        else:
            return {"message": f"Thanks {name}. What service are you interested in?"}

    if state == BookingState.ASK_DATE:
        if data.get("date"):
            sessions[session_id]["state"] = BookingState.CONFIRM
            state = BookingState.CONFIRM
        else:
             msg = "And when would you like to come in? (Date and Time)"
             if service:
                 msg = f"When would you like to schedule your {service}? (Date and Time)"
             return {
                "message": msg,
                "ui_action": "date_picker"
            }

    if state == BookingState.CONFIRM:
        name = data.get("name")
        phone = data.get("phone")
        email = data.get("email")
        service = data.get("service")
        date = data.get("date")
        return {"message": f"Please confirm details:\n- Name: {name}\n- Phone: {phone}\n- Email: {email}\n- Service: {service}\n- Date: {date}\n\nType 'yes' to confirm or 'cancel' to stop."}

    return {"message": "Something went wrong."}

def process_booking(session_id: str, message: str, state_data: dict):
    state = state_data.get("state", BookingState.IDLE)
    data = state_data.get("data", {})
    msg = message.strip().lower()
    
    if state == BookingState.IDLE:
        # Check for booking intent
        # Relaxed condition: check for any strong booking keyword
        booking_keywords = ["book", "appointment", "schedule", "visit", "reservation"]
        if any(k in msg for k in booking_keywords):
            # Smart extraction
            # Smart extraction
            # Retrieve context (last bot response) from session data if available
            history = state_data.get("history", [])
            context = "\n".join(history[-5:]) # Use last 5 turns
            extracted = extract_booking_details(message, context)
            
            # Merge extracted data
            initial_data = {}
            if extracted.get("name"): initial_data["name"] = extracted["name"]
            if extracted.get("phone"): initial_data["phone"] = extracted["phone"]
            if extracted.get("email"): initial_data["email"] = extracted["email"]
            if extracted.get("service"): initial_data["service"] = extracted["service"]
            if extracted.get("date"): initial_data["date"] = extracted["date"]
            
            sessions[session_id] = {"state": BookingState.ASK_NAME, "data": initial_data}
            
            # Check what we already have and jump to next state if needed
            # We use a recursive/iterative check or just check immediately
            
            # Recursively determine next state/question
            return get_next_question(session_id)
            
        return None  # Fallback to RAG

    if state == BookingState.ASK_NAME:
        sessions[session_id]["data"]["name"] = message
        sessions[session_id]["state"] = BookingState.ASK_PHONE
        return get_next_question(session_id)

    if state == BookingState.ASK_PHONE:
        sessions[session_id]["data"]["phone"] = message
        sessions[session_id]["state"] = BookingState.ASK_EMAIL
        return get_next_question(session_id)

    if state == BookingState.ASK_EMAIL:
        sessions[session_id]["data"]["email"] = message
        sessions[session_id]["state"] = BookingState.ASK_SERVICE
        return get_next_question(session_id)

    if state == BookingState.ASK_SERVICE:
        sessions[session_id]["data"]["service"] = message
        sessions[session_id]["state"] = BookingState.ASK_DATE
        return get_next_question(session_id)

    if state == BookingState.ASK_DATE:
        sessions[session_id]["data"]["date"] = message
        sessions[session_id]["state"] = BookingState.CONFIRM
        return get_next_question(session_id)

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
        sessions[session_id] = {"state": BookingState.IDLE, "data": {}, "history": []}
    
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
    
    # Update context with the latest Q&A for future reference
    if "history" not in sessions[session_id]:
        sessions[session_id]["history"] = []
    sessions[session_id]["history"].append(f"User: {q.message}")
    sessions[session_id]["history"].append(f"Bot: {res.content}")
    
    return {"reply": res.content}
