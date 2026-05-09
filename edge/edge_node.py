import os
import requests
import uuid
import random
import time

# Read full API URL (including /vote) from env or use localhost default
API_URL = os.environ.get("API_URL", "http://localhost:8080/vote")

EDGE_ID = os.environ.get("EDGE_ID") or str(random.randint(1, 999))


def generate_vote():
    created_at = time.time()
    return {
        "edge_id": EDGE_ID,
        "user_id": str(uuid.uuid4()),
        "poll_id": "poll_1",
        "choice": random.choice(["A", "B", "C"]),
        "timestamp": created_at,
        "created_at": created_at,
    }


def send_vote(vote):
    try:
        response = requests.post(API_URL, json=vote, timeout=5)
        print(f"Vote sent: status={response.status_code} body={response.text}")
    except Exception as e:
        print("Transmission failed:", e)


def run_edge_node(delay_min=1.0, delay_max=3.0):
    while True:
        vote = generate_vote()
        print(f"Generated vote: {vote['user_id']} (edge={EDGE_ID})")
        send_vote(vote)
        time.sleep(random.uniform(delay_min, delay_max))


if __name__ == "__main__":
    run_edge_node()