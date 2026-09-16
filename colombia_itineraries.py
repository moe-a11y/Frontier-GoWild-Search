#!/usr/bin/env python3
"""Validate separate-ticket MCO connections and price shortlisted itineraries."""
import json
from datetime import datetime
from itertools import product
from pathlib import Path

from gowild_deal_report import _seats_left

P = Path(__file__).parent / "results" / "colombia_expanded"


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def boundary(flight, arrival=False):
    leg = flight["legs"][-1 if arrival else 0]
    return utc(leg["arrivalDateUtc" if arrival else "departureDateUtc"])


def fare(flight, kind):
    key = "goWildFare" if kind == "GoWild" else "discountDenFare"
    value = flight.get(key)
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    if kind == "GoWild" and not flight.get("isGoWildFareEnabled"):
        return None
    if _seats_left(flight.get(key + "SeatsRemaining")) == 0:
        return None
    return round(value, 2)


def build(candidates, records, min_outbound_hours=3, min_inbound_hours=4,
          travel_periods=(("2026-10-01", "2026-12-31"), ("2027-02-01", "2027-03-31")),
          max_faster_extra=50):
    trips = []
    for candidate in candidates:
        options = []
        for job in candidate["jobs"]:
            key = (job["origin"], job["destination"], job["date"])
            record = records.get(key, {})
            flights = record.get("flights", []) if record.get("status") == "ok" else []
            options.append(flights)
        if not all(options):
            continue
        for category in ("Discount Den", "Lowest available", "GoWild"):
            best = None
            feasible = []
            for flights in product(*options):
                a, b, c, d = flights
                # Keep actual final arrival, including overnight domestic travel,
                # inside one of the user's requested travel periods.
                final_day = d["legs"][-1]["arrivalDate"][:10]
                if not any(start <= final_day <= end for start, end in travel_periods):
                    continue
                out_gap = (boundary(b) - boundary(a, True)).total_seconds() / 3600
                back_gap = (boundary(d) - boundary(c, True)).total_seconds() / 3600
                if not (min_outbound_hours <= out_gap <= 24 and min_inbound_hours <= back_gap <= 24):
                    continue
                if boundary(c) <= boundary(b, True):
                    continue
                priced = []
                for f in flights:
                    kinds = ("GoWild", "Discount Den") if category == "Lowest available" else (category,)
                    available = [(fare(f, k), k) for k in kinds if fare(f, k) is not None]
                    if not available:
                        break
                    value, kind = min(available)
                    priced.append(dict(fare_type=kind, price=value, flight=f))
                if len(priced) != 4:
                    continue
                total = round(sum(x["price"] for x in priced), 2)
                journey_hours = ((boundary(b, True) - boundary(a)) +
                                 (boundary(d, True) - boundary(c))).total_seconds() / 3600
                key = (total, journey_hours)
                item = dict(candidate, category=category, total=total,
                            travel_hours=round(journey_hours, 2),
                            outbound_mco_layover_hours=round(out_gap, 2),
                            inbound_mco_layover_hours=round(back_gap, 2),
                            priced_bookings=priced)
                if category == "Lowest available":
                    feasible.append(item)
                if best is None or key < best[0]:
                    best = (key, item)
            if best:
                trips.append(best[1])
                if feasible:
                    quicker = min((t for t in feasible if t["total"] <= best[1]["total"] + max_faster_extra),
                                  key=lambda t: (t["travel_hours"], t["total"]))
                    if quicker["travel_hours"] <= best[1]["travel_hours"] - 2:
                        trips.append(dict(quicker, category="Faster option",
                                          extra_cost=round(quicker["total"] - best[1]["total"], 2),
                                          hours_saved=round(best[1]["travel_hours"] - quicker["travel_hours"], 2)))
    return sorted(trips, key=lambda t: (t["total"], not t["open_jaw"], t["travel_hours"]))


def main():
    records = {}
    for line in (P / "flights.jsonl").read_text().splitlines():
        r = json.loads(line)
        key = (r["origin"], r["destination"], r["date"])
        if r["status"] == "ok" or key not in records:
            records[key] = r
    candidates = json.loads((P / "shortlist.json").read_text())
    trips = build(candidates, records)
    (P / "itineraries.json").write_text(json.dumps(trips, indent=2))
    for t in trips:
        print(t["category"], t["total"], t["colombia_arrival"], t["arrival_city"], t["departure_city"], t["colombia_departure"],
              'MCO hours', t["outbound_mco_layover_hours"], t["inbound_mco_layover_hours"])
    print(len(trips), "validated fare/candidate combinations")


if __name__ == "__main__":
    main()
