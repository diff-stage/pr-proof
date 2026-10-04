#!/usr/bin/env bash
set -euo pipefail

case "$MODE" in
  pull_request)
    [[ "$PR_NUMBER" =~ ^[1-9][0-9]*$ ]] || { echo "Pull request mode requires a pull request event" >&2; exit 1; }
    payload=$(jq -n --arg sha "$HEAD_SHA" --arg branch "$HEAD_REF" --argjson pr "$PR_NUMBER" '{kind:"pull_request",pull_request:$pr,sha:$sha,branch:$branch}')
    ;;
  baseline)
    [[ "$EVENT_NAME" == push || "$EVENT_NAME" == workflow_dispatch ]] && [[ "$REF_NAME" == "$DEFAULT_BRANCH" && -n "$DEFAULT_BRANCH" ]] || { echo "Baselines require a push or workflow_dispatch on the default branch" >&2; exit 1; }
    payload=$(jq -n --arg sha "$RECORDING_SHA" --arg branch "$REF_NAME" --argjson order "$RUN_NUMBER" '{kind:"baseline",pull_request:null,sha:$sha,branch:$branch,source_order:$order}')
    ;;
  *) echo "Unknown publish mode: $MODE" >&2; exit 1 ;;
esac

shopt -s nullglob
videos=("$VIDEOS"/*.webm)
if (( ${#videos[@]} == 0 )); then echo "No videos recorded"; exit 0; fi

command -v ffmpeg >/dev/null || { sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg >/dev/null; }
api() { curl -sSf -H "Authorization: Bearer $PR_PROOF_TOKEN" -H 'Accept: application/json' "$@"; }

run=$(api -X POST "${PR_PROOF_URL%/}/api/runs" \
  -H "Content-Type: application/json" --data "$payload")
run_id=$(jq -r .id <<< "$run")
run_url=$(jq -r .url <<< "$run")

cells=''
for video in "${videos[@]}"; do
  name=$(basename "$video" .webm)
  title=$(jq -r --arg f "$name.webm" '.[$f] // empty' "$VIDEOS/titles.json" 2>/dev/null || true)
  title=${title:-$name}
  mp4="${video%.webm}.mp4"
  poster="${video%.webm}.jpg"

  bash "$COMPRESS" "$video" "$mp4"
  ffmpeg -v error -y -sseof -0.5 -i "$mp4" -frames:v 1 -q:v 3 "$poster"

  telemetry="${mp4}.json"
  [[ -f "$telemetry" ]] || printf '{"steps":[],"problems":[]}\n' > "$telemetry"

  uploaded=$(api -X POST "${PR_PROOF_URL%/}/api/runs/$run_id/videos" \
    -F "name=$title" -F "flow_key=$name" -F "telemetry=@$telemetry;type=application/json" -F "video=@$mp4;type=video/mp4" -F "poster=@$poster;type=image/jpeg")
  cells+=$(printf '<a href="%s"><img src="%s" width="280" alt="%s"></a> ' \
    "$(jq -r .url <<< "$uploaded")" "$(jq -r .poster_url <<< "$uploaded")" "${title//\"/&quot;}")
done

api -X POST "${PR_PROOF_URL%/}/api/runs/$run_id/complete" \
  -H 'Content-Type: application/json' --data "{\"expected_videos\":${#videos[@]}}" >/dev/null

if [[ "$MODE" == baseline ]]; then
  echo "Approved baseline run: $run_url"
  exit 0
fi

body=$(mktemp)
trap 'rm -f "$body"' EXIT
{
  echo '<!-- pr-proof -->'
  echo "### Browser test videos for ${HEAD_SHA::7}"
  echo
  echo "**[Watch all ${#videos[@]} on pr-proof]($run_url)**"
  echo
  echo "$cells"
} > "$body"

existing=$(gh api "repos/$GITHUB_REPOSITORY/issues/$PR_NUMBER/comments" --paginate \
  --jq '.[] | select(.body | startswith("<!-- pr-proof -->")) | .id' | tail -n 1)
if [[ -n "$existing" ]]; then
  gh api -X PATCH "repos/$GITHUB_REPOSITORY/issues/comments/$existing" -F body=@"$body" >/dev/null
else
  gh pr comment "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --body-file "$body"
fi
