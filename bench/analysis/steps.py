def durations(lines):
    found = {}
    for line in lines:
        found.setdefault((line["size"], line["step"], line["engine"]), []).append(line)
    seconds = {}
    for key, invocations in found.items():
        state_id = invocations[-1]["state_id"]
        seconds[key] = (invocations[-1]["seconds"] if state_id is None
                        else sum(line["seconds"] for line in invocations if line["state_id"] == state_id))
    return seconds
