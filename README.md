# ang-vote-nimo

Distributed voting prototype built for Google Cloud — a small example of an event-driven, microservice-style voting pipeline.

---

## Table of Contents

- [Team](#team)
- [Overview](#overview)
- [Architecture](#architecture)
- [Components](#components)
- [Quickstart (local)](#quickstart-local)
- [Docker](#docker)
- [Google Cloud setup](#google-cloud-setup)
- [Vote observer](#vote-observer)
- [Reflections](#reflections)
- [Notes & Security](#notes--security)
- [License](#license)

---

## Team

<div align="center">

<table>
<tr>
<td align="center" width="50%" valign="top">
  <img src="https://github.com/hdmGOAT.png" width="88" height="88" alt="Hans Matthew Del Mundo" /><br />
  <strong>Hans Matthew Del Mundo</strong><br />
  <a href="https://github.com/hdmGOAT"><kbd>@hdmGOAT</kbd></a>
</td>
<td align="center" width="50%" valign="top">
  <img src="https://github.com/potakaaa.png" width="88" height="88" alt="Gerald Helbiro Jr." /><br />
  <strong>Gerald Helbiro Jr.</strong><br />
  <a href="https://github.com/potakaaa"><kbd>@potakaaa</kbd></a>
</td>
</tr>
<tr>
<td align="center" width="50%" valign="top">
  <img src="https://github.com/areeesss.png" width="88" height="88" alt="Vin Marcus Gerebise" /><br />
  <strong>Vin Marcus Gerebise</strong><br />
  <a href="https://github.com/areeesss"><kbd>@areeesss</kbd></a>
</td>
<td align="center" width="50%" valign="top">
  <img src="https://github.com/unripelo.png" width="88" height="88" alt="Ira Chloie Narisma" /><br />
  <strong>Ira Chloie Narisma</strong><br />
  <a href="https://github.com/unripelo"><kbd>@unripelo</kbd></a>
</td>
</tr>
</table>

</div>

---

## Overview

This repository contains a small distributed voting prototype that demonstrates how to decouple client-facing APIs, edge nodes, and background workers using messaging (Pub/Sub) and backing storage (Firestore). It was implemented to explore event-driven design, idempotency, and eventual consistency in a cloud environment.

## Architecture

- Clients -> `api` (HTTP) -> Pub/Sub -> `worker` (Cloud Run) -> Firestore
- Edge nodes generate votes locally and forward them to the API.
- The worker consumes Pub/Sub messages and writes idempotent vote records to Firestore.

## Components

- `api` — HTTP API service for clients and vote aggregation (`api/main.py`).
- `edge` — Edge node that accepts local votes and forwards them (`edge/edge_node.py`).
- `edge/run_edges.py` — Multi-edge launcher for timed runs.
- `worker` — Cloud Run HTTP worker that receives Pub/Sub push messages and persists idempotent votes to Firestore (`worker/main.py`).
- `observer` — Simple Firestore-backed dashboard and summary (`observer/main.py`).

## Quickstart (local)

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

3. Run services locally (use separate terminals for each):

```bash
python api/main.py
python edge/edge_node.py
python worker/main.py
```

To run multiple edge nodes for a timed run:

```bash
cd edge
python run_edges.py --nodes 3 --seconds 20 --api-url "https://vote-api-cm2ntl2x6q-as.a.run.app/vote"
```

## Docker (worker)

Build and run the worker image locally:

```bash
docker build -t ang-vote-worker ./worker
docker run --rm ang-vote-worker
```

## Google Cloud setup

1. Create a GCP project and a service account with the required roles (Pub/Sub, Firestore, Cloud Run, etc.).
2. Download the service account JSON and export the credentials:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

3. (Optional) Configure a Pub/Sub subscription for push delivery to Cloud Run:

```bash
gcloud pubsub subscriptions update vote-sub \
  --push-endpoint=https://<worker-cloud-run-url>/ \
  --push-auth-service-account=<SERVICE_ACCOUNT_EMAIL>
```

> Note: The repo implements a pull-style worker variation; for Cloud Run deployments, Pub/Sub push delivery is often simpler and more idiomatic.

## Vote observer

The `observer` component provides a Firestore-backed dashboard that shows totals, counts by choice, counts by edge node, and recent stored votes.

Run locally:

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

Deploy to Cloud Run example:

```bash
gcloud run deploy vote-observer \
  --source=observer \
  --region=asia-southeast1 \
  --project=YOUR_PROJECT_ID \
  --allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=YOUR_PROJECT_ID,FIRESTORE_COLLECTION=votes"
```

Endpoints:

- `GET /` — Dashboard UI
- `GET /api/summary` — JSON summary
- `GET /healthz` — Health check

---

## Reflections

### Hans Matthew E. Del Mundo

Implementing and testing the distributed voting system made the difference between sequential execution and distributed execution very clear. In a sequential setup, vote generation, validation, processing, and storage happen in one straight path, but in this project each stage behaved independently across the edge nodes, Cloud Run API, Pub/Sub, the worker, and Firestore. Under normal operation, the API stayed lightweight and returned quickly, while the worker processed messages asynchronously and Firestore eventually reflected the final state. As the number of votes increased, the edge nodes could still generate traffic continuously, but I noticed the system became more about buffering and coordination than raw speed: Pub/Sub absorbed bursts, the worker processed messages at its own pace, and the end-to-end latency varied depending on load and service startup behavior. The most useful part of the implementation was seeing eventual consistency in action, because the final Firestore collection converged correctly even when the components were not operating in lockstep.

We also ran into the usual distributed-systems pain points while deploying and debugging the project on GCP. IAM permissions, Cloud Run configuration, Pub/Sub setup, and service-to-service wiring all had to be correct before the pipeline behaved reliably, as well as issues with the clocks on the various instances differing, causing some issues benchmarking, and debugging was harder because failures could happen in different places without breaking the whole system immediately. I do not fully agree with the way the worker was suggested to be implemented: pull-based consumption makes more sense for persistent always-on machines like 24/7 VMs, but in our case, where the workload runs on Cloud Run, it would have been more beneficial to use Pub/Sub push delivery because Cloud Run services are meant to be ephemeral and event-driven. Even so, I complied with the suggested implementation, and it still demonstrated the distributed behavior required for the lab; however, I think the persistent pull model is not idiomatic for Cloud Run plus Pub/Sub and adds unnecessary complexity compared with a push-based approach, Plus the added risk that cloud run does not in fact guarantee the instances will persistently and reliably run, so after some time I expect the current setup to turn off at some point.

### Ira Chloie C. Narisma

Working on the “ang-vote-nimo” project was a meaningful learning experience that helped me better understand how a complete voting system functions from end to end. Through this activity, I was able to see how different parts of a web application such as the user interface, backend logic, and data storage work together to create a working system. It gave me a clearer picture of how user actions like casting a vote are processed, recorded, and then reflected in the results page. This helped me appreciate the importance of proper data flow and system structure in building functional applications.

Aside from the technical side, this project also improved my understanding of real-world system challenges. I realized that even a simple voting application requires careful attention to accuracy, fairness, and data integrity. Small mistakes in logic or structure can affect the entire outcome of the system. It also made me think about how real election systems must be much more secure and reliable, which involves additional layers like authentication, validation, and protection against duplicate or fraudulent votes. Overall, this activity not only strengthened my programming and problem-solving skills but also helped me develop a deeper appreciation for how important well-designed systems are in real-life applications.

### Gerald Helbiro Jr.

Through this project, I learned how distributed systems work by integrating different cloud services into one scalable architecture. I gained practical experience using Google Cloud Run to deploy containerized backend services and Google Cloud Pub/Sub to enable asynchronous communication between components. I also understood the importance of event-driven design, where services can work independently through message passing instead of directly depending on each other. Building the voting system helped me realize how modern cloud-native applications achieve scalability, reliability, and flexibility using microservices and serverless technologies.

Additionally, this project improved my problem-solving and collaboration skills while working in a team environment. I learned how APIs, background workers, databases, and frontend applications connect together in a real-world distributed setup. Troubleshooting issues such as Pub/Sub message handling, Cloud Run deployment, and backend integration taught me the value of debugging, testing, and understanding documentation carefully. Overall, the project strengthened both my technical knowledge and confidence in developing cloud-based systems that can handle real-time user interactions efficiently.


### Vin Marcus Gerebise

Implementing the worker in this distributed voting setup helped me see how different the system feels compared to running everything sequentially in one script. In normal operation, the flow was smooth: edge nodes sent votes to the API, Pub/Sub absorbed the traffic, and the worker stored results in Firestore without blocking the API. The biggest lesson for me was that distributed execution improves responsiveness for users because requests can be accepted quickly even when processing happens later. At the same time, it required more discipline in validating payloads and handling duplicates, since messages can arrive more than once and not always in the order I expected.

Under higher vote volume and during failure-recovery tests, I learned that distributed systems are more resilient but also harder to reason about in real time. When processing slowed down, Pub/Sub acted like a buffer and protected the API from overload, but it also made debugging less straightforward because delays can appear between components. Recovery behavior was reassuring: once the worker resumed, queued votes were eventually processed and persisted, which reinforced the importance of idempotency for consistent final results. Overall, the experience taught me that distributed design is less about “faster code” and more about reliability, clear responsibility per service, and careful coordination across independent components.

## Notes & Security

- Do NOT commit service account keys or secrets. Keep credentials out of the repo.
- Adjust cloud configuration (topics, buckets, database names) via environment variables or component configs.

## Repository layout

- `api/main.py`
- `edge/edge_node.py`
- `edge/run_edges.py`
- `worker/main.py`
- `worker/Dockerfile`
- `observer/main.py`
- `observer/Dockerfile`

## License

MIT — replace or update as appropriate.
