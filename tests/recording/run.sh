#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
port=$(php -r '$s=stream_socket_server("tcp://127.0.0.1:0"); echo parse_url("tcp://".stream_socket_get_name($s,false),PHP_URL_PORT);')
php -S "127.0.0.1:$port" -t public > server.log 2>&1 &
server=$!
trap 'kill "$server"; rm -f server.log' EXIT
export PR_PROOF_TEST_URL="http://127.0.0.1:$port"
for attempt in {1..50}; do
    if curl -fsS "$PR_PROOF_TEST_URL" >/dev/null 2>&1; then break; fi
    sleep 0.1
done
php unsupported.php
rm -rf videos
vendor/bin/pest
[[ ! -d videos ]]
vendor/bin/pest --record-videos=videos "$@"
compgen -G 'videos/*.webm' >/dev/null
php -r '
$files = glob("videos/*.json");
foreach ($files as $file) {
    if (basename($file) === "titles.json") continue;
    $data = json_decode(file_get_contents($file), true, flags: JSON_THROW_ON_ERROR);
    if (count($data["steps"]) < 3) throw new RuntimeException("Missing recorded actions");
    if ($data["problems"] !== []) throw new RuntimeException("Unexpected browser problems");
    $text = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if (str_contains($text, "query-secret") || str_contains($text, "Compatibility verified")) throw new RuntimeException("Telemetry kept a typed or query value");
    if (! str_contains($text, "Opened /?token=…")) throw new RuntimeException("Missing redacted page step");
}
'
for video in videos/*.webm; do
    ffprobe -v error -show_entries format=duration -of csv=p=0 "$video"
done
