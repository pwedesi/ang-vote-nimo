#!/bin/bash

# Cloud Run Deployment Script
# This script builds, pushes, and deploys both API and Worker services

set -e

PROJECT_ID="cs323-voting-system-pwedesi"
REGION="asia-southeast1"
REGISTRY="asia-southeast1-docker.pkg.dev"
REPOSITORY="voting-system"

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Cloud Run Deployment Script ===${NC}"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Enable required APIs
echo -e "${BLUE}[1/6] Enabling required APIs...${NC}"
gcloud services enable artifactregistry.googleapis.com cloudbuild.googleapis.com run.googleapis.com --project=$PROJECT_ID

# Create Artifact Registry repository if it doesn't exist
echo -e "${BLUE}[2/6] Setting up Artifact Registry...${NC}"
gcloud artifacts repositories create $REPOSITORY \
  --repository-format=docker \
  --location=$REGION \
  --project=$PROJECT_ID 2>/dev/null || echo "Repository already exists"

# Authenticate Docker
echo -e "${BLUE}[3/6] Configuring Docker authentication...${NC}"
gcloud auth configure-docker $REGISTRY --quiet

# Build and push API service
echo -e "${BLUE}[4/6] Building and pushing API service...${NC}"
API_IMAGE="$REGISTRY/$PROJECT_ID/$REPOSITORY/vote-api:latest"
docker build -t $API_IMAGE api/
docker push $API_IMAGE
echo -e "${GREEN}✓ API image pushed: $API_IMAGE${NC}"

# Build and push Worker service
echo -e "${BLUE}[5/6] Building and pushing Worker service...${NC}"
WORKER_IMAGE="$REGISTRY/$PROJECT_ID/$REPOSITORY/vote-worker:latest"
docker build -t $WORKER_IMAGE worker/
docker push $WORKER_IMAGE
echo -e "${GREEN}✓ Worker image pushed: $WORKER_IMAGE${NC}"

# Deploy services to Cloud Run
echo -e "${BLUE}[6/6] Deploying to Cloud Run...${NC}"

# Deploy API
echo "Deploying API service..."
gcloud run deploy vote-api \
  --image=$API_IMAGE \
  --platform=managed \
  --region=$REGION \
  --project=$PROJECT_ID \
  --allow-unauthenticated \
  --memory=512Mi \
  --cpu=1 \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID"

echo -e "${GREEN}✓ API deployed${NC}"

# Deploy Worker
echo "Deploying Worker service..."
gcloud run deploy vote-worker \
  --image=$WORKER_IMAGE \
  --platform=managed \
  --region=$REGION \
  --project=$PROJECT_ID \
  --no-allow-unauthenticated \
  --memory=512Mi \
  --cpu=1 \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,PUBSUB_SUBSCRIPTION=vote-sub"

echo -e "${GREEN}✓ Worker deployed${NC}"

# Get service URLs
echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
API_URL=$(gcloud run services describe vote-api --platform=managed --region=$REGION --project=$PROJECT_ID --format='value(status.url)')
echo "API Service URL: $API_URL"
echo ""

# Display next steps
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Verify services are running:"
echo "   gcloud run services list --region=$REGION --project=$PROJECT_ID"
echo ""
echo "2. View API logs:"
echo "   gcloud run logs read vote-api --limit 50 --region=$REGION --project=$PROJECT_ID"
echo ""
echo "3. View Worker logs:"
echo "   gcloud run logs read vote-worker --limit 50 --region=$REGION --project=$PROJECT_ID"
echo ""
echo "4. Test the API:"
echo "   curl -X POST $API_URL/vote \\
     -H 'Content-Type: application/json' \\
     -d '{\"user_id\": \"user1\", \"poll_id\": \"poll1\", \"choice\": \"A\", \"edge_id\": \"edge1\"}'"
