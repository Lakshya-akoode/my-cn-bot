import requests
import uuid
import json
import os
import time

BASE_URL = "http://64.227.171.48:8000"
CANCELLATIONS_FILE = "../data/cancellations.json"

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

def test_cancellation_reason():
    session_id = str(uuid.uuid4())
    print("\n=== Test: Cancellation Reason ===")
    
    # 1. Start booking
    send_message(session_id, "Book appointment")
    send_message(session_id, "John") 
    
    # 2. Cancel
    print("[Cancelling]")
    reply = send_message(session_id, "cancel booking")
    
    if "reason" in reply.lower():
        print("PASS: Bot asked for cancellation reason.")
    else:
        print(f"FAIL: Bot did not ask for reason. Got: {reply}")
        return

    # 3. Provide Reason
    reason = "Found a cheaper option"
    reply = send_message(session_id, reason)
    
    if "cancelled" in reply.lower():
        print("PASS: Cancellation confirmed.")
    else:
        print("FAIL: Cancellation confirmation missing.")

    # 4. Check File
    print("\n[Checking Storage]")
    if os.path.exists(CANCELLATIONS_FILE):
        with open(CANCELLATIONS_FILE, "r") as f:
            data = json.load(f)
            # Check last entry
            last_entry = data[-1]
            if last_entry.get("reason") == reason:
                print("PASS: Reason saved correctly to file.")
            else:
                print(f"FAIL: Reason mismatch. Saved: {last_entry.get('reason')}")
            
            if "ip_address" in last_entry:
                print(f"PASS: IP Address saved: {last_entry['ip_address']}")
            else:
                print("FAIL: IP Address NOT saved.")
    else:
        print("FAIL: cancellations.json not found.")

if __name__ == "__main__":
    test_cancellation_reason()
