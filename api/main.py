from flask import Flask, request
from google.cloud import pubsub_v1
import json
import os
import time

app = Flask(__name__)

PROJECT_ID = "cs323-voting-system-pwedesi"
TOPIC_ID = "vote-topic"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

@app.route("/")
def home():
    return {"message": "Ang Vote Nimo API Running"}

@app.route("/vote", methods=["POST"])
def receive_vote():
    vote = request.get_json()
    request_started_at = time.perf_counter()

    if not vote:
        print("Invalid payload received")
        return {"error": "Invalid payload"}, 400

    required = ["user_id", "poll_id", "choice", "edge_id"]

    for field in required:
        if field not in vote:
            print(f"Missing field: {field}")
            return {"error": f"Missing {field}"}, 400

    try:
        vote["received_at"] = time.time()
        data = json.dumps(vote).encode("utf-8")

        publish_future = publisher.publish(topic_path, data)
        publish_future.result(timeout=10)
        vote["published_at"] = time.time()
        vote["api_publish_ms"] = round((time.perf_counter() - request_started_at) * 1000, 3)

        # ✅ LOGGING HERE
        print(
            f"Vote accepted | "
            f"User: {vote['user_id']} | "
            f"Choice: {vote['choice']} | "
            f"Edge: {vote['edge_id']} | "
            f"API publish: {vote['api_publish_ms']:.3f} ms"
        )

        return {"status": "accepted"}, 200

    except Exception as e:
        # ✅ ERROR LOGGING
        print("Publish failed:", str(e))

        return {"error": str(e)}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)