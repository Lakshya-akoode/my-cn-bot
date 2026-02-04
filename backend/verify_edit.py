import requests
import uuid
import json

BASE_URL = "http://localhost:8000"
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

def test_explicit_edit():
    print("--- Test 1: Explicit Edit ---")
    send_message("Book an appointment")
    send_message("John Doe") # Name
    send_message("555-1234") # Phone
    
    # Now try to edit name
    reply = send_message("Wait, change my name")
    if "What is your name?" in reply:
        print("PASS: Correctly asked for name again.")
    else:
        print("FAIL: Did not ask for name.")
        
    send_message("Jane Doe") # New Name
    reply = send_message("test@example.com") # Email (should proceed normally)
    
def test_ambiguous_edit():
    print("\n--- Test 2: Ambiguous Edit ---")
    # Reset session or just continue
    # Let's say we are at Ask Service
    reply = send_message("Consultation") # Service
    
    # Ambiguous edit
    reply = send_message("I need to update something")
    if "What would you like to update?" in reply:
         print("PASS: Correctly asked for clarification.")
    else:
         print("FAIL: Did not ask for clarification.")
         
    reply = send_message("The date")
    if "when would you like" in reply.lower():
        print("PASS: Correctly transitioned to Date question.")
    else:
        print("FAIL: Did not transition to Date question.")

if __name__ == "__main__":
    test_explicit_edit()
    test_ambiguous_edit()
