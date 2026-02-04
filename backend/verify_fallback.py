import requests
import uuid
import time

BASE_URL = "http://64.227.171.48:8000"

def send_message(session_id, message):
    print(f"\nUser: {message}")
    payload = {"message": message, "session_id": session_id}
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        print(f"Bot: {data.get('reply')}")
        return data.get('reply')
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_rag_fallback():
    session_id = str(uuid.uuid4())
    print("\n=== Test: RAG Fallback Replacement ===")
    
    # Start booking
    send_message(session_id, "Book appointment")
    reply = send_message(session_id, "John") 
    
    # Trigger fallback (ask complex question)
    print("[Triggering Fallback]")
    reply = send_message(session_id, "what are the prices exactly?")
    
    # Check for NEW phrasing
    if "doctor can explain" in reply.lower():
        print("PASS: Fallback message was replaced correctly.")
    else:
        print(f"FAIL: Fallback message NOT replaced. Got: {reply}")
        
    # Check for Resume
    if "phone" in reply.lower():
        print("PASS: Resumed booking (asked for phone).")
    else:
        print("FAIL: Did NOT resume booking.")

if __name__ == "__main__":
    test_rag_fallback()
