import json
import logging
import os
import threading
import time

from flask import Flask
from google.cloud import firestore, pubsub_v1

db = firestore.Client()
app = Flask(__name__)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("vote-worker")

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
        worker_started_at = time.perf_counter()
        processed_at = time.time()
        # Step 1: Receive and decode message
        vote = json.loads(message.data.decode("utf-8"))
        logger.info("Received vote user_id=%s poll_id=%s edge_id=%s", vote.get("user_id"), vote.get("poll_id"), vote.get("edge_id"))
        
        # Validate the vote structure
        validate_vote(vote)
        
        # Step 2: Ensure Data Consistency (Idempotency)
        # Create a unique document ID using user_id and poll_id
        doc_id = f"{vote['user_id']}_{vote['poll_id']}"
        doc_ref = db.collection("votes").document(doc_id)
        doc = doc_ref.get()
        
        if doc.exists:
            logger.info("Duplicate vote ignored doc_id=%s", doc_id)
            message.ack()
            return
        
        # Step 3: Store Processed Votes in Firestore
        vote["processed_at"] = processed_at
        if "created_at" in vote:
            end_to_end_latency_ms = round((processed_at - float(vote["created_at"])) * 1000, 3)
            if end_to_end_latency_ms >= 0:
                vote["end_to_end_latency_ms"] = end_to_end_latency_ms
        if "received_at" in vote:
            api_to_worker_latency_ms = round((processed_at - float(vote["received_at"])) * 1000, 3)
            if api_to_worker_latency_ms >= 0:
                vote["api_to_worker_latency_ms"] = api_to_worker_latency_ms
        firestore_start = time.perf_counter()
        doc_ref.set(vote)
        firestore_write_ms = round((time.perf_counter() - firestore_start) * 1000, 3)
        worker_total_ms = round((time.perf_counter() - worker_started_at) * 1000, 3)
        vote["firestore_write_ms"] = firestore_write_ms
        vote["worker_total_ms"] = worker_total_ms
        vote["cloud_latency_ms"] = worker_total_ms
        doc_ref.update(
            {
                "firestore_write_ms": firestore_write_ms,
                "worker_total_ms": worker_total_ms,
                "cloud_latency_ms": worker_total_ms,
            }
        )
        logger.info("Vote stored in Firestore doc_id=%s", doc_id)
        logger.info(
            "Vote latency doc_id=%s worker_total_ms=%s firestore_write_ms=%s",
            doc_id,
            worker_total_ms,
            firestore_write_ms,
        )
        
        # Step 4: Acknowledge message after successful processing
        message.ack()
        logger.info("Message acknowledged doc_id=%s", doc_id)
        
    except json.JSONDecodeError as e:
        logger.warning("Malformed message data error=%s", e)
        message.nack()
    except ValueError as e:
        logger.warning("Validation error error=%s", e)
        message.nack()
    except Exception as e:
        logger.exception("Processing error error=%s", e)
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
    project_id = os.environ.get("GCP_PROJECT_ID", "ang-vote-nimo")
    subscription_id = os.environ.get("PUBSUB_SUBSCRIPTION", "vote-sub")

    while True:
        subscriber = None
        streaming_pull_future = None
        try:
            logger.info("Subscriber thread starting")
            subscriber = pubsub_v1.SubscriberClient()
            subscription_path = subscriber.subscription_path(project_id, subscription_id)
            logger.info("Worker listening subscription=%s", subscription_path)

            streaming_pull_future = subscriber.subscribe(subscription_path, callback=process_vote)
            streaming_pull_future.result(timeout=None)
        except KeyboardInterrupt:
            logger.info("Stopping worker")
            if streaming_pull_future is not None:
                streaming_pull_future.cancel()
            break
        except Exception as e:
            logger.exception("Subscriber loop error error=%s", e)
            time.sleep(5)
        finally:
            if streaming_pull_future is not None:
                streaming_pull_future.cancel()
            if subscriber is not None:
                subscriber.close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    
    # Start Pub/Sub processing in a background thread
    pubsub_thread = threading.Thread(target=pull_and_process_votes, daemon=True)
    pubsub_thread.start()
    
    # Start Flask health check server in main thread
    logger.info("Starting Flask health check server port=%s", port)
    app.run(host="0.0.0.0", port=port, threaded=True)
