import requests
import uuid
import json

BASE_URL = "http://64.227.171.48:8000"
SESSION_ID = str(uuid.uuid4())

def send_message(message):
    print(f"\nUser: {message}")
    payload = {"message": message, "session_id": SESSION_ID}
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        print(f"Bot: {data.get('reply')}")
        return data.get('reply')
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_interruption():
    print("--- Test: Interruption Detection & Resume ---")
    send_message("Book an appointment")
    reply = send_message("John Doe") # Should ask for Phone next
    
    if "phone" in reply.lower():
        print("State check: Bot is asking for phone.")
    
    # Interrupt
    print("\n[Sending Interruption]")
    reply = send_message("Where are you located?")
    
    # valid transitions
    valid_transitions = [
        "back to your booking",
        "getting back to where we were",
        "continuing with your appointment",
        "get back on track"
    ]
    
    has_answer = "park ridge" in reply.lower() or "located" in reply.lower()
    has_resume = any(t in reply.lower() for t in valid_transitions) and "phone" in reply.lower()
    
    if has_answer and has_resume:
        print("PASS: Bot answered the question and resumed booking.")
    elif has_answer and not has_resume:
        print(f"FAIL: Bot answered but DID NOT resume booking. Reply: {reply}")
    elif not has_answer and has_resume:
        print("FAIL: Bot RESUMED but did not answer question (or RAG failed).")
    else:
        print("FAIL: Bot neither answered nor resumed correctly.")

if __name__ == "__main__":
    test_interruption()
