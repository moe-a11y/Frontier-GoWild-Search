#!/usr/bin/env python3
"""Screen rounded calendar fares; final totals require exact flight validation."""
import json
from datetime import date, timedelta
from pathlib import Path

P = Path(__file__).parent / "results" / "colombia_expanded"
CITIES = ("MDE", "BOG", "CTG")


def calendar_candidates():
    fares = {}
    for line in (P / "calendars.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["status"] != "ok":
            continue
        for d in r["days"]:
            if d["available"] and d["calendar_price"] is not None:
                fares[(r["origin"], r["destination"], d["date"])] = d["calendar_price"]
    candidates = []
    for (origin, arrival, out_date), out_price in fares.items():
        if origin != "MCO" or arrival not in CITIES:
            continue
        out = date.fromisoformat(out_date)
        sfo_day = (out - timedelta(days=1)).isoformat()
        first = ("SFO", "MCO", sfo_day)
        if first not in fares:
            continue
        for nights in range(5, 15):
            back = out + timedelta(days=nights)
            back_date = back.isoformat()
            last = ("MCO", "SFO", (back + timedelta(days=1)).isoformat())
            if last not in fares:
                continue
            for departure in CITIES:
                returning = (departure, "MCO", back_date)
                if returning not in fares:
                    continue
                jobs = [first, (origin, arrival, out_date), returning, last]
                candidates.append(dict(arrival_city=arrival, departure_city=departure,
                                       colombia_arrival=out_date, colombia_departure=back_date,
                                       nights=nights, open_jaw=arrival != departure,
                                       calendar_total=sum(fares[j] for j in jobs),
                                       jobs=[dict(origin=o, destination=d, date=dt) for o, d, dt in jobs]))
    return sorted(candidates, key=lambda c: (c["calendar_total"], not c["open_jaw"], abs(c["nights"] - 8)))


def main():
    candidates = calendar_candidates()
    (P / "calendar_candidates.json").write_text(json.dumps(candidates, indent=2))
    picked = []
    for month in ("2026-12", "2027-02", "2027-03"):
        pool = [c for c in candidates if c["colombia_arrival"].startswith(month)]
        # Include best open jaw, best same-city trip, and the user's MDE-in/BOG-out preference.
        predicates = [lambda c: c["open_jaw"],
                      lambda c: not c["open_jaw"],
                      lambda c: c["arrival_city"] == "MDE" and c["departure_city"] == "BOG"]
        for predicate in predicates:
            matches = [c for c in pool if predicate(c)]
            if matches and matches[0] not in picked:
                picked.append(matches[0])
        # Include Cartagena's best option to represent all three new destinations.
        matches = [c for c in pool if "CTG" in (c["arrival_city"], c["departure_city"])]
        if matches and matches[0] not in picked:
            picked.append(matches[0])
    jobs = []
    for c in picked:
        for j in c["jobs"]:
            if j not in jobs:
                jobs.append(j)
    (P / "shortlist.json").write_text(json.dumps(picked, indent=2))
    (P / "flight_jobs.json").write_text(json.dumps(jobs, indent=2))
    for c in picked:
        print(c["colombia_arrival"], c["arrival_city"], c["departure_city"], c["colombia_departure"], c["nights"], c["calendar_total"])
    print(f"{len(candidates)} calendar combinations; {len(picked)} candidates; {len(jobs)} exact date queries")


if __name__ == "__main__":
    main()
