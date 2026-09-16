#!/usr/bin/env python3
"""Build the expanded Colombia report from verified flight records; no sending."""
import json
from datetime import datetime
from pathlib import Path

P = Path(__file__).parent / "results" / "colombia_expanded"
NAMES = {"MDE": "Medellin", "BOG": "Bogota", "CTG": "Cartagena"}


def stamp(value):
    return datetime.fromisoformat(value).strftime("%b %d, %Y %H:%M")


def home_dates(t):
    bookings = t["priced_bookings"]
    return (bookings[0]["flight"]["legs"][0]["departureDate"][:10],
            bookings[-1]["flight"]["legs"][-1]["arrivalDate"][:10])


def label(t):
    kinds = {b["fare_type"] for b in t["priced_bookings"]}
    return "GoWild + Discount Den" if len(kinds) > 1 else next(iter(kinds))


def detail(t, only_changed_from=None):
    start, end = home_dates(t)
    lines = [f"${t['total']:.2f} | {NAMES[t['arrival_city']]} in / {NAMES[t['departure_city']]} out | {label(t)}",
             f"  Leave SFO {start}; arrive home SFO {end}.",
             f"  Colombia: {t['colombia_arrival']} to {t['colombia_departure']} ({t['nights']} nights).",
             f"  Orlando connection time: outbound {t['outbound_mco_layover_hours']:.1f}h; return {t['inbound_mco_layover_hours']:.1f}h."]
    for index, booking in enumerate(t["priced_bookings"], 1):
        if only_changed_from is not None and booking == only_changed_from["priced_bookings"][index - 1]:
            continue
        f = booking["flight"]
        legs = f["legs"]
        route = "-".join([legs[0]["departureStation"]] + [leg["arrivalStation"] for leg in legs])
        lines.append(f"  Ticket {index}: {route} | ${booking['price']:.2f} {booking['fare_type']} | {f.get('duration', '')}")
        for leg in legs:
            lines.append(f"    F9 {leg['flightNumber']}: {leg['departureStation']} {stamp(leg['departureDate'])} -> {leg['arrivalStation']} {stamp(leg['arrivalDate'])}")
        lines.append("    Search: https://booking.flyfrontier.com/Flight/InternalSelect?" +
                     f"o1={legs[0]['departureStation']}&d1={legs[-1]['arrivalStation']}&dd1={legs[0]['departureDate'][:10]}&ADT=1&mon=true&promo=")
    return "\n".join(lines)


def main():
    trips = json.loads((P / "itineraries.json").read_text())
    best = [t for t in trips if t["category"] == "Lowest available"]
    dd = [t for t in trips if t["category"] == "Discount Den"]
    calendars = [json.loads(x) for x in (P / "calendars.jsonl").read_text().splitlines()]
    records = [json.loads(x) for x in (P / "flights.jsonl").read_text().splitlines()]
    verified = {(r["origin"], r["destination"], r["date"]): r for r in records if r["status"] == "ok"}
    candidates = json.loads((P / "shortlist.json").read_text())
    lines = ["FRONTIER COLOMBIA SPECIAL SEARCH — SFO VIA MCO",
             f"Prepared {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}",
             "Travel: December 2026, February–March 2027. One adult. Open-jaw trips welcome.", "",
             "All totals below include the SFO positioning flights and the international flights, with quoted taxes/fees.",
             "These are four separately priced one-way bookings, not a single through-ticket. Fares were observed, not purchased.",
             "Orlando hotels, travel between Colombian cities, bags, seats, and membership/pass purchase costs are NOT included.", "",
             "BEST VALIDATED OPTIONS (ranked by full airfare)"]
    for i, t in enumerate(best, 1):
        start, end = home_dates(t)
        lines.append(f"{i}. ${t['total']:.2f} — {NAMES[t['arrival_city']]} in / {NAMES[t['departure_city']]} out; "
                     f"Colombia {t['colombia_arrival']}–{t['colombia_departure']} ({t['nights']} nights); "
                     f"SFO {start}–{end}; {label(t)}")
    lines += ["", "DISCOUNT DEN ONLY — SAME SHORTLIST"]
    for t in dd:
        lines.append(f"${t['total']:.2f} — {NAMES[t['arrival_city']]} in / {NAMES[t['departure_city']]} out; "
                     f"Colombia {t['colombia_arrival']}–{t['colombia_departure']}")
    lines += ["", "DETAILED OPTIONS — YOUR MEDELLIN-IN / BOGOTA-OUT PREFERENCE FIRST", "All flight times below are local to the airport shown.", ""]
    preferred = [t for t in best if t["arrival_city"] == "MDE" and t["departure_city"] == "BOG"]
    selected = list(preferred)
    for predicate in (lambda t: not t["open_jaw"], lambda t: t["open_jaw"]):
        matches = [t for t in best if predicate(t)]
        if matches and matches[0] not in selected:
            selected.append(matches[0])
    for t in selected:
        lines += [detail(t), ""]
        alternatives = [a for a in trips if a["category"] == "Faster option" and a["jobs"] == t["jobs"]]
        for a in alternatives:
            lines += [f"FASTER ALTERNATIVE: +${a['extra_cost']:.2f} saves {a['hours_saved']:.1f} hours of combined outbound/return travel.",
                      "Only changed tickets are listed below; retain the other tickets shown above.", detail(a, only_changed_from=t), ""]
    all_gw = [t for t in trips if t["category"] == "GoWild"]
    lines += ["GOWILD STATUS",
              f"Fully GoWild-priced shortlisted trips: {len(all_gw)}.",
              "December domestic GoWild fares were available on checked flights. The Colombian flights checked for the shortlist did not offer enabled GoWild fares.",
              "February/March GoWild availability is not established by a Discount Den calendar. The exact shortlist checks are snapshots, not a prediction of later releases.", "",
              "PASS AND ROUTE NOTES",
              "The new routes launch December 10 (MDE), December 14 (BOG), and December 19 (CTG); October/November do not work. The announced service is subject to government approval.",
              "Frontier announcement: https://news.flyfrontier.com/frontier-announces-major-international-expansion-with-first-ever-service-to-colombia/",
              "Normal GoWild booking opens 10 days before international departure and the day before domestic departure. Early booking is offered on selected flights. A March GoWild trip needs a pass valid in March; the Fall/Winter pass ends February 28, 2027.",
              "GoWild terms: https://www.flyfrontier.com/deals/gowild-pass/", "",
              "SEARCH COVERAGE AND LIMITS",
              f"Successful month calendars: {sum(r['status']=='ok' for r in calendars)} (three Colombia routes both ways, plus SFO–MCO both ways, across three months).",
              f"Calendar combinations screened: {len(json.loads((P / 'calendar_candidates.json').read_text()))}; shortlisted trips: {len(candidates)}; successful exact route/date checks: {len(verified)}.",
              "Complete-ticket spot checks SFO–MDE (February 8 and March 1) and BOG–SFO (February 16 and March 9) returned no flights. The priced options therefore use separate SFO–MCO and MCO–Colombia bookings.",
              "Screening assumed 5–14 nights in Colombia, leaving SFO the day before the Colombia flight and starting MCO–SFO the day after the Colombia return flight.",
              "Actual connection checks use UTC timestamps and require 3–24 hours in Orlando outbound and 4–24 hours on return. Final arrival in SFO must remain within the requested travel periods.",
              "Long connections and overnight stays are shown in the detailed schedules. These are separate bookings; allow for baggage collection/check-in and immigration on the return.",
              "The ranking is the best of the validated shortlist, not an exhaustive optimization over every possible date, trip length, or same-day positioning option. Calendar prices were only used for screening; listed totals come from exact flight records.",
              "Some successful exact records were reused from earlier searches on the same day. The original December scan's HTTP errors are retained in its separate report; this expanded search has its own coverage records.",
              "", "Saved data: results/colombia_expanded/ (calendars, exact flights, candidates, and validated itineraries)."]
    report = "\n".join(lines) + "\n"
    (P / "report.txt").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
