#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-http://127.0.0.1:8899}"

SESSION_ID=$(curl -s "$BASE/sessions" \
  -H 'content-type: application/json' \
  -d '{"title":"Backend Engineer Interview","candidate_name":"Jane Doe","job_description":"Senior backend engineer with Python, APIs, and ownership","rubric":["ownership","system design","debugging","communication"]}' | python3 -c 'import sys, json; print(json.load(sys.stdin)["session_id"])')

echo "session=$SESSION_ID"

curl -s "$BASE/sessions/$SESSION_ID/chunks" -H 'content-type: application/json' -d '{"speaker":"candidate","text":"I led migration from monolith to services and cut p95 by 40%"}' >/dev/null
curl -s "$BASE/sessions/$SESSION_ID/chunks" -H 'content-type: application/json' -d '{"speaker":"candidate","text":"I usually align PM and design in weekly design review"}' >/dev/null

echo "--- interview suggestions"
curl -s "$BASE/sessions/$SESSION_ID/suggestions" -H 'content-type: application/json' -d '{"max_questions":3}' | python3 -m json.tool

echo "--- ambient suggestions"
curl -s "$BASE/sessions/$SESSION_ID/ambient-suggestions" -H 'content-type: application/json' -d '{"max_questions":3}' | python3 -m json.tool

echo "--- summary"
curl -s "$BASE/sessions/$SESSION_ID/summary" | python3 -m json.tool

if [ -n "${NOTION_PARENT_PAGE_ID:-}" ]; then
  echo "--- notion-sync"
  curl -s "$BASE/sessions/$SESSION_ID/notion-sync" \
    -H 'content-type: application/json' \
    -d "{\"parent_page_id\":\"$NOTION_PARENT_PAGE_ID\"}" | python3 -m json.tool
fi
