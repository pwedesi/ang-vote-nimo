
# ang-vote-nimo

Distributed voting system built on Google Cloud.

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
