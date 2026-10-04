# Reads the "Browser review:" list from a pull request description:
#
#   Browser review:
#   1. `flow-key`: What this video proves and where to look.
#
# Outputs [{flow_key, reason, order}] in list order, first entry per flow key.
def item: "^\\s*\\d+[.)]\\s+`(?<flow_key>[^`]+)`\\s*(?:—|–|-|:)\\s*(?<reason>\\S.*?)\\s*$";

split("\n") | map(rtrimstr("\r")) as $lines
| ($lines | map(test("^browser review:\\s*$"; "i")) | index(true)) as $start
| if $start == null then [] else
    [label $done | $lines[$start + 1:][]
      | if test("^\\s*$") then empty elif test(item) then capture(item) else break $done end]
  end
| reduce .[] as $entry ([]; if any(.[]; .flow_key == $entry.flow_key) then . else . + [$entry] end)
| to_entries | map({flow_key: .value.flow_key, reason: .value.reason[:1000], order: (.key + 1)})
