import base64
import binascii
import json
import os

from flask import Flask, request
from google.cloud import firestore

app = Flask(__name__)
db = firestore.Client()

REQUIRED_FIELDS = ["user_id", "poll_id", "choice", "edge_id"]


def decode_pubsub_message(envelope):
    message = envelope.get("message")
    if not message:
        raise ValueError("Missing Pub/Sub message in request body")

    data = message.get("data")
    if not data:
        raise ValueError("Missing message data in Pub/Sub payload")

    try:
        decoded = base64.b64decode(data).decode("utf-8")
        return json.loads(decoded)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"Malformed Pub/Sub vote payload: {e}") from e


def validate_vote(vote):
    for field in REQUIRED_FIELDS:
        if field not in vote:
            raise ValueError(f"Missing vote field: {field}")


def store_vote(vote):
    doc_id = f"{vote['user_id']}_{vote['poll_id']}"
    doc_ref = db.collection("votes").document(doc_id)
    doc = doc_ref.get()

    if doc.exists:
        print(f"Duplicate vote ignored: {doc_id}")
        return "duplicate"

    doc_ref.set(vote)
    print(f"Vote stored: {doc_id}")
    return "stored"


@app.route("/", methods=["GET"])
def home():
    return {"message": "Worker service running"}, 200


@app.route("/", methods=["POST"])
def process_vote():
    envelope = request.get_json(silent=True)
    if not envelope:
        return {"error": "Invalid or empty JSON payload"}, 400

    try:
        vote = decode_pubsub_message(envelope)
        validate_vote(vote)
        result = store_vote(vote)
        return {"status": result}, 200
    except ValueError as e:
        print(f"Validation error: {e}")
        return {"error": str(e)}, 400
    except Exception as e:
        print(f"Processing error: {e}")
        return {"error": "Vote processing failed"}, 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
