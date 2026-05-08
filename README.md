
# ang-vote-nimo

Distributed voting system built on Google Cloud.

Overview
- This repository contains a small distributed voting prototype composed of three components:
	- `api` — HTTP API service for clients and vote aggregation ([api/main.py](api/main.py)).
	- `edge` — Edge node that accepts local votes and forwards them ([edge/edge_node.py](edge/edge_node.py)).
	- `worker` — Background worker for processing and persisting votes (Dockerfile at [worker/Dockerfile](worker/Dockerfile)).

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

Notes and security
- Do NOT commit service account keys or secrets. The repository `.gitignore` excludes common credential patterns.
- Adjust cloud configuration (topics, buckets, databases) in each component's configuration or environment variables.

Repository layout
- [api/main.py](api/main.py)
- [edge/edge_node.py](edge/edge_node.py)
- [worker/main.py](worker/main.py)
- [worker/Dockerfile](worker/Dockerfile)

License
- MIT (replace or update as needed)
