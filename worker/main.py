import json
import os
import threading

from flask import Flask
from google.cloud import firestore, pubsub_v1

db = firestore.Client()
app = Flask(__name__)

REQUIRED_FIELDS = ["user_id", "poll_id", "choice", "edge_id"]


def validate_vote(vote):
    """Validate that the vote contains all required fields."""
    for field in REQUIRED_FIELDS:
        if field not in vote:
            raise ValueError(f"Missing vote field: {field}")


def process_vote(message):
    """
    Decode and parse incoming vote message.
    Ensure safe handling of malformed data.
    """
    try:
        # Step 1: Receive and decode message
        vote = json.loads(message.data.decode("utf-8"))
        print(f"Received vote: {vote}")
        
        # Validate the vote structure
        validate_vote(vote)
        
        # Step 2: Ensure Data Consistency (Idempotency)
        # Create a unique document ID using user_id and poll_id
        doc_id = f"{vote['user_id']}_{vote['poll_id']}"
        doc_ref = db.collection("votes").document(doc_id)
        doc = doc_ref.get()
        
        if doc.exists:
            print(f"Duplicate vote ignored: {doc_id}")
            message.ack()
            return
        
        # Step 3: Store Processed Votes in Firestore
        doc_ref.set(vote)
        print(f"Vote stored in Firestore: {doc_id}")
        
        # Step 4: Acknowledge message after successful processing
        message.ack()
        print(f"Message acknowledged: {doc_id}")
        
    except json.JSONDecodeError as e:
        print(f"Malformed message data: {e}")
        message.nack()
    except ValueError as e:
        print(f"Validation error: {e}")
        message.nack()
    except Exception as e:
        print(f"Processing error: {e}")
        message.nack()


# === HEALTH CHECK ENDPOINT ===
@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint for Google Cloud Run."""
    return {"status": "healthy"}, 200


# === DISTRIBUTED PROCESSING LAYER ===
def pull_and_process_votes():
    """
    Step 5: Continuous Processing Loop
    The worker runs continuously, listening for new messages without manual intervention.
    This reflects the nature of real-world distributed processing systems.
    """
    subscriber = pubsub_v1.SubscriberClient()
    project_id = os.environ.get("GCP_PROJECT_ID", "ang-vote-nimo")
    subscription_id = os.environ.get("PUBSUB_SUBSCRIPTION", "vote-sub")
    subscription_path = subscriber.subscription_path(project_id, subscription_id)
    
    print(f"Worker started. Listening to subscription: {subscription_path}")
    
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=process_vote)
    
    try:
        # Keep the subscriber running indefinitely
        streaming_pull_future.result(timeout=None)
    except KeyboardInterrupt:
        print("Stopping worker...")
        streaming_pull_future.cancel()
        streaming_pull_future.result()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    
    # Start Pub/Sub processing in a background thread
    pubsub_thread = threading.Thread(target=pull_and_process_votes, daemon=True)
    pubsub_thread.start()
    
    # Start Flask health check server in main thread
    print(f"Starting Flask health check server on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
