import requests
import uuid
import random
import time

API_URL = "YOUR_CLOUD_RUN_API_URL/vote"

EDGE_ID = random.randint(1, 999)

def generate_vote():
    return {
        "edge_id": EDGE_ID,
        "user_id": str(uuid.uuid4()),
        "poll_id": "poll_1",
        "choice": random.choice(["A", "B", "C"]),
        "timestamp": time.time()
    }

def send_vote(vote):
    try:
        response = requests.post(API_URL, json=vote)

        print("Vote sent:", response.status_code)

    except Exception as e:
        print("Transmission failed:", e)

def run_edge_node():
    while True:
        vote = generate_vote()

        print(f"Generated vote: {vote['user_id']}")

        send_vote(vote)

        time.sleep(random.uniform(1, 3))

if __name__ == "__main__":
    run_edge_node()