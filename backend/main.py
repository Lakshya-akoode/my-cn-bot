from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from prompts import SYSTEM_PROMPT
import os
import json
from datetime import datetime
import re
import random
from dotenv import load_dotenv

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

class BookingState:
    IDLE = "IDLE"
    ASK_NAME = "ASK_NAME"
    ASK_PHONE = "ASK_PHONE"
    ASK_EMAIL = "ASK_EMAIL"
    ASK_SERVICE = "ASK_SERVICE"
    ASK_DATE = "ASK_DATE"
    CONFIRM = "CONFIRM"
    ASK_EDIT_FIELD = "ASK_EDIT_FIELD"
    ASK_CANCEL_REASON = "ASK_CANCEL_REASON"

# In-memory session store: session_id -> {state: ..., data: {...}}
sessions = {}

APPOINTMENTS_FILE = os.path.join(project_root, "data", "appointments.json")
CANCELLATIONS_FILE = os.path.join(project_root, "data", "cancellations.json")

def save_appointment(data, ip_address=None):
    appointments = []
    if os.path.exists(APPOINTMENTS_FILE):
        with open(APPOINTMENTS_FILE, "r") as f:
            try:
                appointments = json.load(f)
            except:
                pass
    
    data["created_at"] = datetime.now().isoformat()
    if ip_address:
        data["ip_address"] = ip_address
        
    appointments.append(data)
    
    # Ensure directory exists just in case
    os.makedirs(os.path.dirname(APPOINTMENTS_FILE), exist_ok=True)
    
    with open(APPOINTMENTS_FILE, "w") as f:
        json.dump(appointments, f, indent=4)

def save_cancellation(data, reason, ip_address=None):
    cancellations = []
    if os.path.exists(CANCELLATIONS_FILE):
        with open(CANCELLATIONS_FILE, "r") as f:
            try:
                cancellations = json.load(f)
            except:
                pass
    
    entry = {
        "data": data,
        "reason": reason,
        "cancelled_at": datetime.now().isoformat()
    }
    if ip_address:
        entry["ip_address"] = ip_address

    cancellations.append(entry)
    
    os.makedirs(os.path.dirname(CANCELLATIONS_FILE), exist_ok=True)
    
    with open(CANCELLATIONS_FILE, "w") as f:
        json.dump(cancellations, f, indent=4)

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

    if state == BookingState.ASK_CANCEL_REASON:
        return {"message": "I understand. May I ask the reason for the cancellation?", "resume_message": "May I confirm why you'd like to cancel?"}

    if state == BookingState.ASK_EDIT_FIELD:
        return {"message": "What would you like to update? (e.g., name, date, service)", "resume_message": "What details would you like to update?"}

    # If currently in ASK_NAME, but we already have name, move to ASK_PHONE
    if state == BookingState.ASK_NAME:
        if data.get("name"):
            sessions[session_id]["state"] = BookingState.ASK_PHONE
            state = BookingState.ASK_PHONE
        else:
            if service:
                return {"message": f"I can definitely help you book a {service}. First, what is your name?", "resume_message": "Could I get your name for the booking?"}
            return {"message": "Sure! I can help you with that. What is your name?", "resume_message": "May I have your name to get started?"}

    if state == BookingState.ASK_PHONE:
        if data.get("phone"):
            sessions[session_id]["state"] = BookingState.ASK_EMAIL
            state = BookingState.ASK_EMAIL
        else:
            return {"message": f"Thanks {name}. What is your phone number?", "resume_message": "What is the best phone number to reach you?"}

    if state == BookingState.ASK_EMAIL:
        if data.get("email"):
            sessions[session_id]["state"] = BookingState.ASK_SERVICE
            state = BookingState.ASK_SERVICE
        else:
            return {"message": "Got it. What is your email address?", "resume_message": "And your email address?"}

    if state == BookingState.ASK_SERVICE:
        if data.get("service"):
            sessions[session_id]["state"] = BookingState.ASK_DATE
            state = BookingState.ASK_DATE
        else:
            return {"message": f"Thanks {name}. What service are you interested in?", "resume_message": "Which service were you interested in?"}

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
                "resume_message": "When would you prefer to come in?",
                "ui_action": "date_picker"
            }

    if state == BookingState.CONFIRM:
        name = data.get("name")
        phone = data.get("phone")
        email = data.get("email")
        service = data.get("service")
        date = data.get("date")
        return {"message": f"Please confirm details:\n- Name: {name}\n- Phone: {phone}\n- Email: {email}\n- Service: {service}\n- Date: {date}\n\nType 'yes' to confirm, 'edit' to change details, or 'cancel' to stop.", "resume_message": "Please confirm if these details look correct."}

    return {"message": "Something went wrong."}

def is_interruption(message: str, current_state: str) -> bool:
    """
    Determines if the user's message is an interruption/question rather than an answer to the booking question.
    """
    # Heuristics for obvious cases
    msg = message.lower()
    if msg in ["cancel", "stop", "exit", "quit"]: return False
    
    # If the message is very short (like a name or number), likely not an interruption
    if len(msg.split()) < 3 and current_state not in [BookingState.ASK_SERVICE, BookingState.ASK_EDIT_FIELD, BookingState.ASK_CANCEL_REASON]:
         return False
         
    # Use LLM for smarter detection
    prompt = f"""
    Context: The bot is currently asking the user a question to book an appointment.
    Current State: {current_state} (waiting for this info)
    User Message: "{message}"
    
    Is the user's message providing the requested information, or is it a completely separate question/interruption?
    
    Examples:
    State: ASK_NAME, Message: "John" -> Answer (False)
    State: ASK_NAME, Message: "Who are you?" -> Interruption (True)
    State: ASK_DATE, Message: "tomorrow at 5" -> Answer (False)
    State: ASK_DATE, Message: "Where is the clinic?" -> Interruption (True)
    
    Return ONLY "True" if it is an interruption, or "False" if it is an answer.
    """
    try:
        res = llm.invoke(prompt)
        return "True" in res.content
    except:
        return False

def process_booking(session_id: str, message: str, state_data: dict):
    state = state_data.get("state", BookingState.IDLE)
    data = state_data.get("data", {})
    ip_address = state_data.get("ip", None)
    msg = message.strip().lower()
    
    # Check for Edit Intent globally if we are already in flow (not IDLE)
    if state != BookingState.IDLE:
        # Check for Cancellation FIRST
        cancel_keywords = ["cancel", "stop", "exit", "quit", "abort", "no booking"]
        if any(k in msg for k in cancel_keywords) and state != BookingState.ASK_CANCEL_REASON:
             sessions[session_id]["state"] = BookingState.ASK_CANCEL_REASON
             return get_next_question(session_id)

        # Check for Interruption
        if is_interruption(message, state):
            return None # Treat as RAG query

        edit_keywords = ["edit", "change", "modify", "update", "correct", "wrong"]
        if any(k in msg for k in edit_keywords) and state not in [BookingState.ASK_EDIT_FIELD, BookingState.ASK_CANCEL_REASON]:
            
            # Identify field to edit using regex for whole word matching
            target_field = None
            if re.search(r'\bname\b', msg): target_field = "name"
            elif re.search(r'\b(phone|number)\b', msg): target_field = "phone"
            elif re.search(r'\b(email|mail)\b', msg): target_field = "email"
            elif re.search(r'\bservice\b', msg): target_field = "service"
            elif re.search(r'\b(date|time)\b', msg): target_field = "date"
            
            if target_field:
                # Clear the field so get_next_question prompts for it
                if target_field in data:
                    del data[target_field]
                
                # Transition to the appropriate state
                if target_field == "name": sessions[session_id]["state"] = BookingState.ASK_NAME
                elif target_field == "phone": sessions[session_id]["state"] = BookingState.ASK_PHONE
                elif target_field == "email": sessions[session_id]["state"] = BookingState.ASK_EMAIL
                elif target_field == "service": sessions[session_id]["state"] = BookingState.ASK_SERVICE
                elif target_field == "date": sessions[session_id]["state"] = BookingState.ASK_DATE
                
                # Update session data reference (mutable dict)
                sessions[session_id]["data"] = data
                return get_next_question(session_id)
            else:
                # Ambiguous edit
                sessions[session_id]["state"] = BookingState.ASK_EDIT_FIELD
                return get_next_question(session_id)

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

    if state == BookingState.ASK_CANCEL_REASON:
        save_cancellation(data, message, ip_address)
        sessions[session_id] = {"state": BookingState.IDLE, "data": {}}
        return {"message": "Thank you for your feedback. Your booking has been cancelled."}

    if state == BookingState.ASK_EDIT_FIELD:
        # User is replying to "What would you like to update?"
        target_field = None
        if "name" in msg: target_field = "name"
        elif "phone" in msg or "number" in msg: target_field = "phone"
        elif "email" in msg or "mail" in msg: target_field = "email"
        elif "service" in msg: target_field = "service"
        elif "date" in msg or "time" in msg: target_field = "date"
        
        if target_field:
            if target_field in data:
                del data[target_field]
            
            if target_field == "name": sessions[session_id]["state"] = BookingState.ASK_NAME
            elif target_field == "phone": sessions[session_id]["state"] = BookingState.ASK_PHONE
            elif target_field == "email": sessions[session_id]["state"] = BookingState.ASK_EMAIL
            elif target_field == "service": sessions[session_id]["state"] = BookingState.ASK_SERVICE
            elif target_field == "date": sessions[session_id]["state"] = BookingState.ASK_DATE
            
            sessions[session_id]["data"] = data
            return get_next_question(session_id)
        else:
             return {"message": "I didn't catch that. Please tell me which field to update (Name, Phone, Email, Service, or Date)."}

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
            save_appointment(sessions[session_id]["data"], ip_address)
            sessions[session_id] = {"state": BookingState.IDLE, "data": {}}
            return {"message": "Appointment saved! We look forward to seeing you."}
        elif msg in ["no", "cancel", "stop"]:
            sessions[session_id] = {"state": BookingState.IDLE, "data": {}}
            return {"message": "Booking cancelled."}
        else:
            return {"message": "Please type 'yes' to save the appointment, 'edit' to change details, or 'cancel' to stop."}

    return None

@app.post("/chat")
def chat(q: Query, request: Request):
    session_id = q.session_id
    client_ip = request.client.host
    
    # Initialize session if not exists
    if session_id not in sessions:
        sessions[session_id] = {"state": BookingState.IDLE, "data": {}, "history": [], "ip": client_ip, "last_fallback": False}
    else:
        # Update IP just in case it changed (though unlikely for same session)
        sessions[session_id]["ip"] = client_ip
    
    # Check if user is saying "yes" after receiving the fallback message
    msg_lower = q.message.strip().lower()
    yes_keywords = ["yes", "yeah", "yep", "sure", "ok", "okay", "y", "please", "go ahead", "arrange"]
    
    if sessions[session_id].get("last_fallback", False) and any(keyword in msg_lower for keyword in yes_keywords):
        # User agreed to arrange a call - initiate booking with context
        history = sessions[session_id].get("history", [])
        context = "\n".join(history[-5:])  # Use last 5 turns
        
        # Extract service from context
        extracted = extract_booking_details(q.message, context)
        
        initial_data = {}
        if extracted.get("service"):
            initial_data["service"] = extracted["service"]
        
        # Start booking flow
        sessions[session_id] = {"state": BookingState.ASK_NAME, "data": initial_data, "history": history, "ip": client_ip, "last_fallback": False}
        
        return {
            "reply": get_next_question(session_id)["message"],
            "ui_action": get_next_question(session_id).get("ui_action")
        }
    
    # Try to process booking flow
    booking_response = process_booking(session_id, q.message, sessions[session_id])
    if booking_response:
        # Clear fallback flag when in active booking
        sessions[session_id]["last_fallback"] = False
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
    bot_reply = res.content

    # Check if the fallback message was sent
    fallback_trigger = "Shall I arrange a quick call?"
    if fallback_trigger in bot_reply:
        sessions[session_id]["last_fallback"] = True
    else:
        sessions[session_id]["last_fallback"] = False

    # If we are in a booking flow but just answered an interruption, attempt to resume
    if sessions[session_id].get("state") != BookingState.IDLE:
        # Check if RAG returned the specific fallback message
        fallback_trigger_alt = "connect you with the right person"
        if fallback_trigger_alt in bot_reply:
             # Replace the fallback text with something more relevant to an existing booking
             bot_reply = "Good question — this actually depends on a few details. The doctor can explain this clearly during your visit."

        # Get the question we *should* be asking
        resume_data = get_next_question(session_id)
        if resume_data:
            # Pick a random transition phrase
            transitions = [
                "Anyway, back to your booking,",
                "Getting back to where we were,",
                "Now, continuing with your appointment,",
                "Let's get back on track -"
            ]
            transition = random.choice(transitions)
            
            # Use resume_message if available, otherwise fallback to standard message
            next_q = resume_data.get("resume_message", resume_data.get("message", "")).lower()
            
            bot_reply += f"\n\n{transition} {next_q}"
            
            if "ui_action" in resume_data:
                return {
                    "reply": bot_reply,
                    "ui_action": resume_data.get("ui_action")
                }
    
    # Update context with the latest Q&A for future reference
    if "history" not in sessions[session_id]:
        sessions[session_id]["history"] = []
    sessions[session_id]["history"].append(f"User: {q.message}")
    sessions[session_id]["history"].append(f"Bot: {res.content}")
    
    return {"reply": bot_reply}
