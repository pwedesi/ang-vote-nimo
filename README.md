
# ang-vote-nimo

Distributed voting system built on Google Cloud.

Latency benchmarking
- Each vote now carries a generation timestamp from the edge, plus API receipt and publish timestamps, and worker processing timestamps.
- The worker stores `end_to_end_latency_ms` and `api_to_worker_latency_ms` in Firestore for each processed vote.
- The observer dashboard shows latency averages, min/max values, and per-vote end-to-end latency in the recent votes table.
- To benchmark the system, run several edge nodes, let the pipeline settle, then compare the latency cards in the observer during normal load, worker downtime, and recovery.

Reflection - Hans Matthew E. Del Mundo

Implementing and testing the distributed voting system made the difference between sequential execution and distributed execution very clear. In a sequential setup, vote generation, validation, processing, and storage happen in one straight path, but in this project each stage behaved independently across the edge nodes, Cloud Run API, Pub/Sub, the worker, and Firestore. Under normal operation, the API stayed lightweight and returned quickly, while the worker processed messages asynchronously and Firestore eventually reflected the final state. As the number of votes increased, the edge nodes could still generate traffic continuously, but I noticed the system became more about buffering and coordination than raw speed: Pub/Sub absorbed bursts, the worker processed messages at its own pace, and the end-to-end latency varied depending on load and service startup behavior. The most useful part of the implementation was seeing eventual consistency in action, because the final Firestore collection converged correctly even when the components were not operating in lockstep.

We also ran into the usual distributed-systems pain points while deploying and debugging the project on GCP. IAM permissions, Cloud Run configuration, Pub/Sub setup, and service-to-service wiring all had to be correct before the pipeline behaved reliably, as well as issues with the clocks on the various instances differing, causing some issues benchmarking, and debugging was harder because failures could happen in different places without breaking the whole system immediately. I do not fully agree with the way the worker was suggested to be implemented: pull-based consumption makes more sense for persistent always-on machines like 24/7 VMs, but in our case, where the workload runs on Cloud Run, it would have been more beneficial to use Pub/Sub push delivery because Cloud Run services are meant to be ephemeral and event-driven. Even so, I complied with the suggested implementation, and it still demonstrated the distributed behavior required for the lab; however, I think the persistent pull model is not idiomatic for Cloud Run plus Pub/Sub and adds unnecessary complexity compared with a push-based approach, Plus the added risk that cloud run does not in fact guarantee the instances will persistently and reliably run, so after some time I expect the current setup to turn off at some point.

Overview
- This repository contains a small distributed voting prototype composed of three components:
	- `api` — HTTP API service for clients and vote aggregation ([api/main.py](api/main.py)).
	- `edge` — Edge node that accepts local votes and forwards them ([edge/edge_node.py](edge/edge_node.py)).
	- `edge` — Multi-edge launcher for timed runs ([edge/run_edges.py](edge/run_edges.py)).
	- `worker` — Cloud Run HTTP worker that receives Pub/Sub push messages and persists idempotent votes to Firestore ([worker/main.py](worker/main.py)).

Architecture
- Components communicate using cloud messaging and storage (configure Google Cloud Pub/Sub, Firestore or Cloud Storage as needed).
- Designed for deployment to GCP. Use a service account with appropriate permissions and set `GOOGLE_APPLICATION_CREDENTIALS` to the key file path.

Quickstart (local development)
1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies (root and per-component requirements):

```bash
pip install -r requirements.txt
pip install -r api/requirements.txt
pip install -r edge/requirements.txt
pip install -r worker/requirements.txt
```

3. Run services locally (in separate terminals):

```bash
python api/main.py
python edge/edge_node.py
python worker/main.py
```

Run several edge nodes for a fixed duration:

```bash
cd edge
python run_edges.py --nodes 3 --seconds 20 --api-url "https://vote-api-cm2ntl2x6q-as.a.run.app/vote"
```

Docker (worker)
- Build and run the worker image:

```bash
docker build -t ang-vote-worker ./worker
docker run --rm ang-vote-worker
```

Google Cloud setup
- Create a GCP project and service account with required roles (Pub/Sub, Firestore, Cloud Storage as used).
- Download the service account JSON and set:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

- Configure Pub/Sub push delivery to the worker Cloud Run URL:

```bash
gcloud pubsub subscriptions update vote-sub \
  --push-endpoint=https://<worker-cloud-run-url>/ \
  --push-auth-service-account=<SERVICE_ACCOUNT_EMAIL>
```

Notes and security
- Do NOT commit service account keys or secrets. The repository `.gitignore` excludes common credential patterns.
- Adjust cloud configuration (topics, buckets, databases) in each component's configuration or environment variables.

Repository layout
- [api/main.py](api/main.py)
- [edge/edge_node.py](edge/edge_node.py)
- [edge/run_edges.py](edge/run_edges.py)
- [worker/main.py](worker/main.py)
- [worker/Dockerfile](worker/Dockerfile)
- [observer/main.py](observer/main.py)
- [observer/Dockerfile](observer/Dockerfile)

Vote observer
- A simple Firestore-backed dashboard lives in [observer/main.py](observer/main.py).
- It shows total votes, counts by choice, counts by edge node, and the most recent stored votes.
- Local configuration lives in [observer/.env](observer/.env) and points to the service-account JSON file.
- Run it locally with:

```bash
cd observer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
set -a
source .env
set +a
python main.py
```

- Deploy it to Cloud Run with:

```bash
gcloud run deploy vote-observer \
	--source=observer \
	--region=asia-southeast1 \
	--project=cs323-voting-system-pwedesi \
	--allow-unauthenticated \
	--set-env-vars="GCP_PROJECT_ID=cs323-voting-system-pwedesi,FIRESTORE_COLLECTION=votes"
```

- Open `GET /` for the dashboard, `GET /api/summary` for JSON, and `GET /healthz` for health checks.

License
- MIT (replace or update as needed)
