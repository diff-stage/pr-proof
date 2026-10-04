# Reads the "Browser review:" list from a pull request description:
#
#   Browser review:
#   1. `flow-key`: What this video proves and where to look.
#
# Outputs [{flow_key, reason, order}] in list order, first entry per flow key.
def item: "^\\s*\\d+[.)]\\s+`(?<flow_key>[^`]+)`\\s*(?:—|–|-|:)\\s*(?<reason>\\S.*?)\\s*$";

def fence: [capture("^\\s*(?<marks>`{3,}|~{3,})(?<info>.*)$")][0];

# Lines inside fenced code blocks are examples, so they never count. Only a
# fence of the same character, at least as long and with nothing after it,
# closes the block.
[foreach (split("\n")[] | rtrimstr("\r")) as $line ({open: null};
  .open as $open | ($line | fence) as $fence
  | if $open == null then
      if $fence != null and ($fence.marks[:1] == "~" or ($fence.info | contains("`") | not))
      then {open: $fence.marks, line: null} else {open: null, line: $line} end
    elif $fence != null and $fence.marks[:1] == $open[:1]
      and ($fence.marks | length) >= ($open | length) and ($fence.info | test("^\\s*$"))
    then {open: null, line: null}
    else {open: $open, line: null} end;
  .line)] as $lines
| ($lines | map(. != null and test("^browser review:\\s*$"; "i")) | index(true)) as $start
| if $start == null then [] else
    [label $done | $lines[$start + 1:][]
      | if . == null then break $done elif test("^\\s*$") then empty elif test(item) then capture(item) else break $done end]
  end
| reduce .[] as $entry ([]; if any(.[]; .flow_key == $entry.flow_key) then . else . + [$entry] end)
| to_entries | map({flow_key: .value.flow_key, reason: .value.reason[:1000], order: (.key + 1)})
