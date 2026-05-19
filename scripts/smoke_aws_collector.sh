#!/usr/bin/env bash
set -euo pipefail

COLLECTOR_HEALTH_URL="${COLLECTOR_HEALTH_URL:-http://127.0.0.1:8686/health}"
CORE_API_URL="${CORE_API_URL:-${INCIDENTOPS_API_URL:-}}"
PROJECT_ID="${PROJECT_ID:-${INCIDENTOPS_PROJECT_ID:-}}"
SOURCE_PATH="${SOURCE_PATH:-tests/fixtures/basic_project}"
QUERY="${QUERY:-What evidence is available for investigation?}"
RUN_VALIDATE_RAG_PIPELINE="${RUN_VALIDATE_RAG_PIPELINE:-1}"
RUN_SYNC="${RUN_SYNC:-0}"

echo "collector_health_url=${COLLECTOR_HEALTH_URL}"
curl -fsS "${COLLECTOR_HEALTH_URL}"
echo

if [[ -n "${CORE_API_URL}" ]]; then
  echo "core_health_url=${CORE_API_URL%/}/health"
  if [[ -n "${INCIDENTOPS_TOKEN:-}" ]]; then
    curl -fsS -H "Authorization: Bearer ${INCIDENTOPS_TOKEN}" "${CORE_API_URL%/}/health"
  else
    curl -fsS "${CORE_API_URL%/}/health"
  fi
  echo
else
  echo "CORE_API_URL or INCIDENTOPS_API_URL is not set; skipping Core health check."
fi

if [[ "${RUN_VALIDATE_RAG_PIPELINE}" == "1" && -d "${SOURCE_PATH}" ]]; then
  echo "validate_rag_pipeline_source=${SOURCE_PATH}"
  args=(validate-rag-pipeline --path "${SOURCE_PATH}" --query "${QUERY}" --format json)
  if [[ -n "${CORE_API_URL}" && -n "${PROJECT_ID}" ]]; then
    args+=(--api-url "${CORE_API_URL}" --project-id "${PROJECT_ID}")
  fi
  opsincident-collector "${args[@]}"
fi

if [[ "${RUN_SYNC}" == "1" ]]; then
  if [[ -z "${CORE_API_URL}" || -z "${PROJECT_ID}" ]]; then
    echo "RUN_SYNC=1 requires CORE_API_URL/INCIDENTOPS_API_URL and PROJECT_ID/INCIDENTOPS_PROJECT_ID." >&2
    exit 1
  fi
  echo "starting_one_off_sync_source=${SOURCE_PATH}"
  sync_output="$(
    opsincident-collector sync \
      --path "${SOURCE_PATH}" \
      --export api \
      --api-url "${CORE_API_URL}" \
      --project-id "${PROJECT_ID}" \
      --source-name "${SOURCE_NAME:-aws-smoke-source}" \
      --source-type "${SOURCE_TYPE:-filesystem}" \
      --yes \
      --force
  )"
  echo "${sync_output}"
  SYNC_OUTPUT="${sync_output}" python - <<'PY'
import os
import json

payload = json.loads(os.environ["SYNC_OUTPUT"])
print(f"source_id={payload.get('source_id')}")
print(f"sync_id={payload.get('sync_id')}")
print(f"documents_synced={payload.get('documents_synced')}")
PY
fi
