from google.cloud import pubsub_v1
from google.cloud import firestore
import json
import time

PROJECT_ID = "cs323-voting-system-pwedesi"
SUBSCRIPTION_ID = "vote-sub"

subscriber = pubsub_v1.SubscriberClient()
db = firestore.Client()

subscription_path = subscriber.subscription_path(
    PROJECT_ID,
    SUBSCRIPTION_ID
)

def process_vote(message):
    try:
        vote = json.loads(message.data.decode("utf-8"))

        doc_id = f"{vote['user_id']}_{vote['poll_id']}"

        db.collection("votes").document(doc_id).set(vote)

        print(f"Processed vote: {vote['user_id']}")

        message.ack()

    except Exception as e:
        print("Error:", e)

def main():
    streaming_pull_future = subscriber.subscribe(
        subscription_path,
        callback=process_vote
    )

    print("Worker listening...")

    with subscriber:
        streaming_pull_future.result()

if __name__ == "__main__":
    main()