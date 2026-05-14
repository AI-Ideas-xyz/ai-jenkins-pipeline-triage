#!/bin/bash
# Simulates an EKS pod deployment failure.
# Generates a synthetic kubectl-style failure log, uploads to a secret GitHub Gist,
# and dispatches a pipeline-failure event to GitHub Actions with category="eks-deploy".

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/triage-logs"
LOG_FILE="$LOG_DIR/eks-run.log"
LAST_GIST_FILE="$SCRIPT_DIR/.triage-eks-last-gist"

# ── Load .env ─────────────────────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

: "${GITHUB_TOKEN:?GITHUB_TOKEN is not set. Add it to .env or export it.}"
: "${GITHUB_REPO:?GITHUB_REPO is not set. Example: owner/repo}"

mkdir -p "$LOG_DIR"

# ── Pick scenario ──────────────────────────────────────────────────────────────
SCENARIOS=("CrashLoopBackOff" "OOMKilled" "ImagePullBackOff" "ReadinessProbeFailed")
SCENARIO=${1:-${SCENARIOS[$RANDOM % ${#SCENARIOS[@]}]}}

echo ""
echo "[1/4] Generating EKS failure log (scenario: $SCENARIO)..."
echo "---------------------------------------"
python3 "$SCRIPT_DIR/scripts/gen_eks_log.py" "$SCENARIO" > "$LOG_FILE"
cat "$LOG_FILE"
echo "---------------------------------------"

LINE_COUNT=$(wc -l < "$LOG_FILE" | tr -d ' ')
echo "[2/4] Log generated ($LINE_COUNT lines). Uploading to GitHub Gist..."

# Verify token has gist scope
TOKEN_SCOPES=$(curl -s -I \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  https://api.github.com/user | grep -i "x-oauth-scopes" | tr -d '\r')
echo "      Token scopes: ${TOKEN_SCOPES:-none detected}"
if ! echo "$TOKEN_SCOPES" | grep -qi "gist"; then
  echo "      ERROR: GITHUB_TOKEN is missing 'gist' scope."
  echo "      Go to github.com/settings/tokens → edit token → tick 'gist' → update .env"
  exit 1
fi

# Delete previous EKS gist if exists
if [ -f "$LAST_GIST_FILE" ]; then
  LAST_GIST_ID=$(cat "$LAST_GIST_FILE")
  curl -s -X DELETE \
    -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/gists/${LAST_GIST_ID}" > /dev/null
  echo "      Cleaned up previous Gist: $LAST_GIST_ID"
  rm "$LAST_GIST_FILE"
fi

LOG_CONTENT=$(python3 -c "import sys,json; print(json.dumps(open('$LOG_FILE').read()))")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

GIST_RESPONSE=$(curl -s -X POST \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/gists \
  -d "{
    \"description\": \"EKS triage log — ${SCENARIO} — ${TIMESTAMP}\",
    \"public\": false,
    \"files\": {
      \"eks-failure.log\": {
        \"content\": $LOG_CONTENT
      }
    }
  }")

GIST_ID=$(echo "$GIST_RESPONSE" | python3 -c \
  "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('id',''))" 2>/dev/null)
GIST_RAW_URL=$(echo "$GIST_RESPONSE" | python3 -c \
  "import sys,json; d=json.loads(sys.stdin.read()); f=list(d.get('files',{}).values()); print(f[0].get('raw_url','') if f else '')" 2>/dev/null)
GIST_HTML_URL=$(echo "$GIST_RESPONSE" | python3 -c \
  "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('html_url',''))" 2>/dev/null)

if [ -z "$GIST_ID" ]; then
  echo "      ERROR: Gist upload failed. Response: $GIST_RESPONSE"
  exit 1
fi

echo "$GIST_ID" > "$LAST_GIST_FILE"
echo "      Gist created: $GIST_HTML_URL"

echo "[3/4] Dispatching pipeline-failure event to GitHub Actions..."

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/${GITHUB_REPO}/dispatches" \
  -d "{
    \"event_type\": \"pipeline-failure\",
    \"client_payload\": {
      \"job\": \"eks-deploy-simulation\",
      \"category\": \"eks-deploy\",
      \"scenario\": \"$SCENARIO\",
      \"branch\": \"$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)\",
      \"commit\": \"$(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)\",
      \"gist_raw_url\": \"$GIST_RAW_URL\"
    }
  }")

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS:")

echo "[4/4] curl response: HTTP $HTTP_STATUS"
if [ "$HTTP_STATUS" -eq 204 ]; then
  echo "      Dispatch sent. Full log: $GIST_HTML_URL"
  echo "      Actions: https://github.com/${GITHUB_REPO}/actions"
else
  echo "      ERROR: Dispatch failed. Body: $BODY"
  exit 1
fi
