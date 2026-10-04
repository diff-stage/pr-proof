# Reads the "Browser review:" list from a pull request description:
#
#   Browser review:
#   1. `flow-key`: What this video proves and where to look.
#
# Outputs [{flow_key, reason, order}] in list order, first entry per flow key.
def item: "^\\s*\\d+[.)]\\s+`(?<flow_key>[^`]+)`\\s*(?:—|–|-|:)\\s*(?<reason>\\S.*?)\\s*$";

# Lines inside fenced code blocks are examples, so they never count.
[foreach (split("\n")[] | rtrimstr("\r")) as $line (false;
  if $line | test("^\\s*(```|~~~)") then not else . end;
  if $line | test("^\\s*(```|~~~)") then null elif . then null else $line end)] as $lines
| ($lines | map(. != null and test("^browser review:\\s*$"; "i")) | index(true)) as $start
| if $start == null then [] else
    [label $done | $lines[$start + 1:][]
      | if . == null then break $done elif test("^\\s*$") then empty elif test(item) then capture(item) else break $done end]
  end
| reduce .[] as $entry ([]; if any(.[]; .flow_key == $entry.flow_key) then . else . + [$entry] end)
| to_entries | map({flow_key: .value.flow_key, reason: .value.reason[:1000], order: (.key + 1)})
