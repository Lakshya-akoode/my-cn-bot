import requests
import uuid
import json
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

def test_cancellation():
    session_id = str(uuid.uuid4())
    print("\n=== Test: Cancellation Logic ===")
    
    # Start booking
    send_message(session_id, "Book appointment")
    reply = send_message(session_id, "John") # Name
    
    # Cancel midway
    print("[Attempting Cancellation]")
    reply = send_message(session_id, "cancel my booking process")
    
    if "cancelled" in reply.lower():
        print("PASS: Booking cancelled correctly.")
    else:
        print("FAIL: Booking NOT cancelled.")

    # Check state reset by starting new one
    reply = send_message(session_id, "Book appointment")
    if "what is your name" in reply.lower():
        print("PASS: State was reset, starting new booking.")
    else:
        print("FAIL: State was not reset properly.")

if __name__ == "__main__":
    test_cancellation()
