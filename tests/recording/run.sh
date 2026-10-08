#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
port=$(php -r '$s=stream_socket_server("tcp://127.0.0.1:0"); echo parse_url("tcp://".stream_socket_get_name($s,false),PHP_URL_PORT);')
php -S "127.0.0.1:$port" -t public > server.log 2>&1 &
server=$!
trap 'kill "$server"; rm -f server.log' EXIT
export DIFF_STAGE_TEST_URL="http://127.0.0.1:$port"
for attempt in {1..50}; do
    if curl -fsS "$DIFF_STAGE_TEST_URL" >/dev/null 2>&1; then break; fi
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
    $expected = substr($file, 0, -5).".webm.expected";
    if (is_file($expected)) {
        $point = json_decode(file_get_contents($expected), true);
        $target = end($data["cursor"]);
        if (abs($point["x"] - $target["x"]) > 1 || abs($point["y"] - $target["y"]) > 1) throw new RuntimeException("Fast capture missed the real click location");
        if (strlen($target["screenshot"]) < 100) throw new RuntimeException("Fast capture omitted its viewport image");
    }
    $captionData = array_intersect_key($data, array_flip(["steps", "assertions", "problems"]));
    if (isset($data["capture_version"]) && $data["capture_version"] !== 1) throw new RuntimeException("Unsupported fast capture version");
    if (isset($data["capture_version"]) && strlen($data["final"]["screenshot"] ?? "") < 100) throw new RuntimeException("Fast capture omitted its final frame");
    $text = json_encode($captionData, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if (str_contains($text, "query-secret") || str_contains($text, "Compatibility verified") || str_contains($text, "Disposable private message")) throw new RuntimeException("Telemetry kept a typed or query value");
    if (! str_contains($text, "Opened /?token=…")) throw new RuntimeException("Missing redacted steps");
    if (str_contains(basename($file), "names-css-targets")) {
        $steps = array_column($data["steps"], "text");
        if (count(array_filter($steps, fn ($step) => str_starts_with($step, "Opened "))) !== 1) throw new RuntimeException("Fragment changes became page opens");
        if (count(array_filter($steps, fn ($step) => $step === "Clicked \"Player settings\"")) !== 2) throw new RuntimeException("Repeated clicks lost their readable names");
        foreach (["Clicked \"Save message\"", "Hovered over \"Playback position\"", "Typed into \"Private message\"", "Clicked (entered text)", "Clicked `#unnamed`"] as $step) {
            if (! in_array($step, $steps, true)) throw new RuntimeException("Missing named step: ".$step);
        }
    }
    $assertions = $data["assertions"];
    foreach ($assertions as $assertion) {
        if (! is_bool($assertion["passed"]) || $assertion["finished_at"] < $assertion["at"]) throw new RuntimeException("Invalid assertion outcome");
    }
    if (str_contains(basename($file), "successful-delayed")) {
        if (count($assertions) !== 7) throw new RuntimeException("Assertion retries were duplicated or unsupported checks recorded");
        if ($assertions[0]["finished_at"] - $assertions[0]["at"] < 0.5) throw new RuntimeException("Delayed assertion did not wait");
        if (array_column($assertions, "passed") !== [true, true, true, true, true, true, false]) throw new RuntimeException("Incorrect assertion outcomes");
        if (array_filter($data["steps"], fn ($step) => $step["failed"] ?? false)) throw new RuntimeException("Failed assertion marked an action as failed");
    } elseif (! str_contains($text, "Pressed a key")) {
        throw new RuntimeException("Missing redacted key press");
    }
    if (str_contains($text, "Pressed 7")) throw new RuntimeException("Telemetry kept a pressed character");
}
'
for video in videos/*.webm; do
    ffprobe -v error -show_entries format=duration -of csv=p=0 "$video"
done

# Prove exact scenario selection against real Pest and Browser.
selection=$(mktemp)
trap 'kill "$server"; rm -f server.log "$selection"' EXIT
cat > "$selection" <<'JSON'
[
  {"file":"tests/CursorTest.php","test":"it opens a menu through real pointer movement"},
  {"file":"tests/CursorTest.php","test":"it keeps touch recordings free of a mouse cursor"}
]
JSON
rm -rf selected-videos
../../bin/diff-stage-record "$selection" --record-videos=selected-videos --record-videos-fast
[[ $(find selected-videos -name '*.webm' | wc -l) == 2 ]]
