#!/usr/bin/env bash
set -euo pipefail

case "$MODE" in
  pull_request)
    [[ "$PR_NUMBER" =~ ^[1-9][0-9]*$ ]] || { echo "Pull request mode requires a pull request event" >&2; exit 1; }
    sha=$HEAD_SHA
    payload=$(jq -n --arg sha "$sha" --arg branch "$HEAD_REF" --argjson pr "$PR_NUMBER" --arg id "$RECORDING_ID" '{kind:"pull_request",pull_request:$pr,sha:$sha,branch:$branch,recording_id:$id}')
    ;;
  baseline)
    [[ "$EVENT_NAME" == push || "$EVENT_NAME" == workflow_dispatch ]] && [[ "$REF_NAME" == "$DEFAULT_BRANCH" && -n "$DEFAULT_BRANCH" ]] || { echo "Baselines require a push or workflow_dispatch on the default branch" >&2; exit 1; }
    sha=$RECORDING_SHA
    payload=$(jq -n --arg sha "$sha" --arg branch "$REF_NAME" --argjson order "$RUN_NUMBER" --arg id "$RECORDING_ID" '{kind:"baseline",pull_request:null,sha:$sha,branch:$branch,source_order:$order,recording_id:$id}')
    ;;
  *) echo "Unknown publish mode: $MODE" >&2; exit 1 ;;
esac

shopt -s nullglob
videos=("$VIDEOS"/*.webm)
if (( ${#videos[@]} == 0 )); then echo "No videos recorded"; exit 0; fi

if [[ -f "$VIDEOS/sha.txt" ]]; then
  recorded=$(tr -d '[:space:]' < "$VIDEOS/sha.txt")
  [[ "$recorded" == "$sha" ]] || { echo "Videos were recorded at $recorded, not $sha" >&2; exit 1; }
fi

names=()
for video in "${videos[@]}"; do names+=("$(basename "$video" .webm)"); done

review='[]'
if [[ "$MODE" == pull_request ]]; then
  review=$(jq -Rs -f "$(dirname "${BASH_SOURCE[0]}")/review.jq" <<< "${PR_BODY:-}")
fi
jq -nr --argjson review "$review" '$review[].flow_key | select(IN($ARGS.positional[]) | not)
  | "::warning::Browser review lists \(.), but no video has that flow key."' --args "${names[@]}"
mapfile -t names < <(jq -rn --argjson review "$review" '($review | map(.flow_key)) as $keys
  | ($keys - ($keys - $ARGS.positional)) + ($ARGS.positional - $keys) | .[]' --args "${names[@]}")

fast=false
if jq -e '.capture_version == 1' "${videos[0]%.webm}.json" >/dev/null 2>&1; then
  fast=true
fi
for video in "${videos[@]}"; do
  captured_fast=false
  if jq -e ".capture_version == 1" "${video%.webm}.json" >/dev/null 2>&1; then captured_fast=true; fi
  [[ "$captured_fast" == "$fast" ]] || { echo "Cannot mix fast and legacy recordings." >&2; exit 1; }
done
if [[ "$fast" == false ]]; then
command -v ffmpeg >/dev/null || { sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg >/dev/null; }
fi
if [[ -z "${DIFF_STAGE_TOKEN:-}" && ( -z "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" || -z "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}" ) ]]; then
  echo 'Allow id-token: write on the publishing job and connect this repository to the Diff Stage GitHub App. No api-token is needed.' >&2
  exit 1
fi

api() {
  local credential="${DIFF_STAGE_TOKEN:-}"
  if [[ -z "$credential" ]]; then
    credential=$(curl -sSf --get --data-urlencode 'audience=diff-stage' \
      -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" "$ACTIONS_ID_TOKEN_REQUEST_URL" | \
      jq -er '.value | select(type == "string" and length > 0)') || {
      echo 'Unable to obtain GitHub Actions identity. Check id-token: write on the publishing job.' >&2
      return 1
    }
    echo "::add-mask::$credential" >&2
  fi
  local response
  response=$(curl --silent --show-error --fail-with-body -H "Authorization: Bearer $credential" -H 'Accept: application/json' "$@") || {
    printf '%s\n' "$response" >&2
    return 1
  }
  printf '%s' "$response"
}

run=$(api -X POST "${DIFF_STAGE_URL%/}/api/runs" \
  -H "Content-Type: application/json" --data "$payload")
run_id=$(jq -r .id <<< "$run")
run_url=$(jq -r .url <<< "$run")

queued=''
if [[ "$fast" == true ]]; then
  archive=$(mktemp --suffix=.zip)
  trap 'rm -f "$archive"' EXIT
  python3 - "$VIDEOS" "$archive" <<'PYTHON'
from pathlib import Path
import sys, zipfile
root = Path(sys.argv[1])
with zipfile.ZipFile(sys.argv[2], 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    archive.write(root / 'titles.json', 'titles.json')
    for video in sorted(root.glob('*.webm')):
        archive.write(video, video.name)
        telemetry = video.with_suffix('.json')
        archive.write(telemetry, telemetry.name)
PYTHON
  queued=$(api -X POST "${DIFF_STAGE_URL%/}/api/runs/$run_id/recordings" \
    -F "archive=@$archive;type=application/zip" --form-string "review=$review")
  rm -f "$archive"
  trap - EXIT
  echo "Recordings queued for server processing: $run_url"
fi

previews=''
links=''
reviewed=''
preview_count=0
for name in "${names[@]}"; do
  video="$VIDEOS/$name.webm"
  title=$(jq -r --arg f "$name.webm" '.[$f] // empty' "$VIDEOS/titles.json" 2>/dev/null || true)
  title=${title:-$name}
  mp4="${video%.webm}.mp4"
  poster="${video%.webm}.jpg"

  entry=$(jq -c --arg key "$name" 'map(select(.flow_key == $key))[0] // empty' <<< "$review")
  if [[ "$fast" == true ]]; then
    uploaded=$(jq -c --arg key "$name" '.videos[] | select(.flow_key == $key) | . + {poster_public:false,poster_url:null}' <<< "$queued")
  else
  bash "$COMPRESS" "$video" "$mp4"
  ffmpeg -v error -y -sseof -0.5 -i "$mp4" -frames:v 1 -q:v 3 "$poster"

  telemetry="${mp4}.json"
  [[ -f "$telemetry" ]] || printf '{"steps":[],"problems":[]}\n' > "$telemetry"

  entry=$(jq -c --arg key "$name" 'map(select(.flow_key == $key))[0] // empty' <<< "$review")
  fields=()
  if [[ -n "$entry" ]]; then
    fields=(--form-string "review_reason=$(jq -r .reason <<< "$entry")" --form-string "review_order=$(jq -r .order <<< "$entry")")
  fi

  uploaded=$(api -X POST "${DIFF_STAGE_URL%/}/api/runs/$run_id/videos" \
    --form-string "name=$title" --form-string "flow_key=$name" "${fields[@]}" \
    -F "telemetry=@$telemetry;type=application/json" -F "video=@$mp4;type=video/mp4" -F "poster=@$poster;type=image/jpeg")
  fi
  video_url=$(jq -r '.url | @html' <<< "$uploaded")
  poster_url=$(jq -r '.poster_url | @html' <<< "$uploaded")
  escaped_title=$(jq -nr --arg title "$title" '$title | @html')
  if [[ -n "$entry" ]]; then
    reviewed+=$(printf '<li><a href="%s">%s</a>: %s</li>' "$video_url" "$escaped_title" "$(jq -r '.reason | @html' <<< "$entry")")
  fi
  if (( preview_count < 3 )) && [[ $(jq '.poster_public != false' <<< "$uploaded") == true ]]; then
    previews+=$(printf '<td><a href="%s"><img src="%s" height="120" alt="%s"></a></td>' \
      "$video_url" "$poster_url" "$escaped_title")
    preview_count=$(( preview_count + 1 ))
  fi
  links+=$(printf '<li><a href="%s">%s</a></li>' "$video_url" "$escaped_title")
done

if [[ "$fast" == false ]]; then
api -X POST "${DIFF_STAGE_URL%/}/api/runs/$run_id/complete" \
  -H 'Content-Type: application/json' --data "{\"expected_videos\":${#videos[@]}}" >/dev/null

fi

if [[ "$MODE" == baseline ]]; then
  echo "Baseline run: $run_url"
  exit 0
fi

body=$(mktemp)
trap 'rm -f "$body"' EXIT
{
  echo '<!-- diff-stage -->'
  echo "### Browser test videos for ${HEAD_SHA::7}"
  echo
  echo "**[Watch all ${#videos[@]} on Diff Stage]($run_url)**"
  if [[ "$fast" == true ]]; then
    echo
    echo 'Recordings are processing on Diff Stage and will appear here when ready.'
  fi
  echo
  if [[ -n "$previews" ]]; then
    echo "<table><tr>$previews</tr></table>"
    echo
  fi
  if [[ -n "$reviewed" ]]; then
    echo '**What to check**'
    echo
    echo "<ol>$reviewed</ol>"
    echo
  fi
  echo '<details>'
  echo "<summary>All browser tests (${#videos[@]})</summary>"
  echo
  echo "<ol>$links</ol>"
  echo
  echo '</details>'
} > "$body"

existing=$(gh api "repos/$GITHUB_REPOSITORY/issues/$PR_NUMBER/comments" --paginate \
  --jq '.[] | select(.body | startswith("<!-- diff-stage -->") or startswith("<!-- pr-proof -->")) | .id' | tail -n 1)
if [[ -n "$existing" ]]; then
  gh api -X PATCH "repos/$GITHUB_REPOSITORY/issues/comments/$existing" -F body=@"$body" >/dev/null
else
  gh pr comment "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --body-file "$body"
fi
