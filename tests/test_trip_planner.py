"""Offline checks for trip_planner; no browser, network, or email.
Flight records are synthetic, shaped like the ones colombia_search.search keeps."""
import unittest
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import trip_planner as tp

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)


def _utc(code, local):
    dt = datetime.fromisoformat(local).replace(tzinfo=ZoneInfo(tp.AIRPORT_TZ[code]))
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def flight(o, d, dep, arr, gw=None, dd=None):
    leg = dict(departureStation=o, arrivalStation=d, departureDate=dep, arrivalDate=arr,
               departureDateUtc=_utc(o, dep), arrivalDateUtc=_utc(d, arr), flightNumber="100")
    return dict(legs=[leg], isGoWildFareEnabled=gw is not None, goWildFare=gw,
                discountDenFare=dd, stopsText="Nonstop", duration="1h 30m")


def by_key(*flights):
    out = {}
    for f in flights:
        leg = f["legs"][0]
        out.setdefault((leg["departureStation"], f["legs"][-1]["arrivalStation"],
                        leg["departureDate"][:10]), []).append(f)
    return out


class DateRuleTests(unittest.TestCase):
    def test_weekend_rule(self):
        self.assertTrue(tp.spans_weekend(date(2026, 11, 6), date(2026, 11, 8)))   # Fri-Sun
        self.assertTrue(tp.spans_weekend(date(2026, 11, 7), date(2026, 11, 9)))   # Sat-Mon
        self.assertFalse(tp.spans_weekend(date(2026, 11, 6), date(2026, 11, 7)))  # Fri-Sat
        self.assertFalse(tp.spans_weekend(date(2026, 11, 8), date(2026, 11, 10)))  # Sun-Tue

    def test_date_pairs_lengths_and_window(self):
        pairs = tp.date_pairs(tp.TRIPS["desert"])
        self.assertEqual(54, len(pairs))  # 9 per weekend x 6 weekends
        self.assertTrue(all(3 <= (b - a).days + 1 <= 5 for a, b in pairs))
        self.assertTrue(all(b <= date(2026, 12, 16) for _, b in pairs))
        pr = tp.date_pairs(tp.TRIPS["puerto_rico"])
        self.assertTrue(all((b - a).days + 1 >= 8 for a, b in pr))

    def test_colombia_launch_dates(self):
        trip = tp.TRIPS["latam_caribbean"]
        self.assertTrue(all(a >= date(2026, 12, 10) for a, _ in tp.date_pairs(trip, "MDE")))
        self.assertEqual([], tp.date_pairs(trip, "BOG"))
        self.assertEqual(["2026-12"], tp._months(trip, "BOG"))  # open-jaw return only
        self.assertEqual([], tp._months(trip, "CTG"))

    def test_gowild_windows(self):
        self.assertEqual(date(2026, 11, 6), tp.gowild_opens("SFO", "LAS", date(2026, 11, 7)))
        self.assertEqual(date(2026, 10, 28), tp.gowild_opens("SFO", "SJU", date(2026, 11, 7)))
        self.assertEqual(date(2026, 10, 28), tp.gowild_opens("SJU", "MCO", date(2026, 11, 7)))
        self.assertTrue(tp.gowild_window_open("SFO", "SJO", date(2026, 10, 31), NOW))
        self.assertFalse(tp.gowild_window_open("SFO", "SJO", date(2026, 11, 1), NOW))
        self.assertFalse(tp.gowild_window_open("SFO", "LAS", date(2026, 10, 23), NOW))

    def test_pto(self):
        dt = datetime.fromisoformat
        self.assertEqual(0, tp.pto_days(dt("2026-11-06T18:30"), dt("2026-11-08T21:00")))
        self.assertEqual(3, tp.pto_days(dt("2026-11-05T08:00"), dt("2026-11-09T21:00")))
        self.assertEqual(0, tp.pto_days(dt("2026-11-26T08:00"), dt("2026-11-29T21:00")))


class ScreenTests(unittest.TestCase):
    def cal(self, o, d, month, prices, dd=False):
        days = [dict(date=f"{month}-{n:02d}", available=n in prices,
                     is_discount_den=dd, calendar_price=prices.get(n))
                for n in range(1, 31)]
        return dict(origin=o, destination=d, month=month, status="ok", days=days)

    def test_self_connect_and_dd_candidates(self):
        records = [
            self.cal("SFO", "SLC", "2026-11", {6: 120}),
            self.cal("SLC", "SFO", "2026-11", {8: 110}),
            self.cal("SFO", "DEN", "2026-11", {6: 30}, dd=True),
            self.cal("DEN", "SLC", "2026-11", {6: 25}, dd=True),
            self.cal("SLC", "SFO", "2026-11", {8: 60}, dd=True),
        ]
        fares = tp.load_calendar_fares(records)
        cands = tp.screen_trip("park_city", fares)
        best = min(cands, key=lambda c: c["calendar_total"])
        self.assertEqual(115, best["calendar_total"])  # later SLC->SFO record wins
        self.assertTrue(best["self_connect"] and best["all_dd"])
        self.assertEqual(["SFO-DEN", "DEN-SLC", "SLC-SFO"],
                         [f"{leg['origin']}-{leg['destination']}" for leg in best["legs"]])
        self.assertIn(best, tp.shortlist(cands, "park_city"))


class ItineraryTests(unittest.TestCase):
    def test_open_jaw_gowild_round_trip(self):
        flights = by_key(
            flight("SFO", "LAS", "2026-11-06T18:30:00", "2026-11-06T20:00:00", gw=14.0, dd=49.0),
            flight("PSP", "SFO", "2026-11-08T19:00:00", "2026-11-08T20:30:00", gw=15.0, dd=59.0),
        )
        items = tp.build_itineraries("desert", flights, NOW)
        cats = {i["category"]: i for i in items}
        self.assertEqual(29.0, cats["GoWild"]["total"])
        self.assertEqual(108.0, cats["Discount Den"]["total"])
        self.assertEqual(0, cats["GoWild"]["pto"])
        self.assertTrue(cats["GoWild"]["open_jaw"])
        ranked = tp.rank_trip(items)
        self.assertEqual(["GoWild"], [i["category"] for i in ranked["gowild"]])
        self.assertEqual([108.0], [i["total"] for i in ranked["dd_target"]])

    def test_blackout_gowild_kept_with_peak_label(self):
        # Frontier sells GoWild on blackout dates with a Peak Day Charge (in the fare).
        flights = by_key(
            flight("SFO", "SLC", "2026-11-26T09:00:00", "2026-11-26T11:45:00", gw=14.0, dd=40.0),
            flight("SLC", "SFO", "2026-11-29T18:00:00", "2026-11-29T19:00:00", gw=158.99, dd=45.0),
        )
        items = tp.build_itineraries("park_city", flights, NOW)
        cats = {i["category"]: i for i in items}
        self.assertEqual(172.99, cats["GoWild"]["total"])
        self.assertEqual(85.0, cats["Discount Den"]["total"])
        lines = "\n".join(tp._trip_lines(1, cats["GoWild"], NOW))
        self.assertIn("$158.99 GoWild (blackout date: incl. Peak Day Charge)", lines)
        # For you, the cheaper fare per flight wins: Discount Den home on the peak day.
        self.assertEqual(59.0, cats["GoWild + Discount Den"]["total"])

    def test_self_connect_needs_connection_time(self):
        out_leg = flight("SFO", "DEN", "2026-11-06T06:00:00", "2026-11-06T09:30:00", dd=30.0)
        back = flight("SLC", "SFO", "2026-11-08T18:00:00", "2026-11-08T19:00:00", dd=40.0)
        tight = flight("DEN", "SLC", "2026-11-06T10:30:00", "2026-11-06T12:00:00", dd=20.0)
        ok = flight("DEN", "SLC", "2026-11-06T13:00:00", "2026-11-06T14:30:00", dd=25.0)
        items = tp.build_itineraries("park_city", by_key(out_leg, tight, back), NOW)
        self.assertEqual([], items)
        items = tp.build_itineraries("park_city", by_key(out_leg, tight, ok, back), NOW)
        dd = [i for i in items if i["category"] == "Discount Den"]
        self.assertEqual([95.0], [i["total"] for i in dd])
        self.assertTrue(dd[0]["self_connect"])

    def test_pending_gowild_and_report(self):
        flights = by_key(
            flight("SFO", "SJU", "2026-11-06T22:00:00", "2026-11-07T09:30:00", dd=99.0),
            flight("SJU", "SFO", "2026-11-14T10:00:00", "2026-11-14T16:00:00", dd=89.0),
        )
        items = tp.build_itineraries("puerto_rico", flights, NOW)
        cats = {i["category"] for i in items}
        self.assertEqual({"Discount Den", "Couple DD", "GoWild pending"}, cats)
        report = tp.build_report({"puerto_rico": items}, ["Coverage: test"], NOW)
        self.assertIn("GoWild opens Tue Oct 27 (SFO midnight)", report)
        self.assertIn("Discount Den round trips (top 5; ★ = under $150; 0 date/airport combinations "
                      "under $150 found)", report)
        self.assertIn("Solo with your $100 voucher: ≈$90.00", report)  # $45/leg PR tax estimate
        self.assertIn("OVERALL TOP 3 — THE PERFECT TRIP FOR TWO", report)
        self.assertIn("Best GoWild bets still to be released", report)
        # No GoWild yet, so the trip for two is both of you on Discount Den: 2 x $188 minus
        # the voucher on your own base fare only ($54 + $44).
        self.assertIn("$278.00 for two (both Discount Den, one booking)", report)

    def desert_trip(self, back_gw=15.0):
        return by_key(
            flight("SFO", "LAS", "2026-11-06T18:30:00", "2026-11-06T20:00:00", gw=14.0, dd=49.0),
            flight("PSP", "SFO", "2026-11-08T19:00:00", "2026-11-08T20:30:00", gw=back_gw, dd=59.0),
        )

    def test_rule_checks(self):
        items = tp.build_itineraries("desert", self.desert_trip(), NOW)
        for item in items:
            self.assertEqual([], tp.rule_problems(item), item["category"])
        bad = dict(next(i for i in items if i["category"] == "GoWild"), days=9)
        bad["total"] += 1
        problems = tp.rule_problems(bad)
        self.assertIn("total doesn't match its fares", problems)
        self.assertTrue(any("outside 3-5" in p for p in problems))

    def test_reprice(self):
        item = next(i for i in tp.build_itineraries("desert", self.desert_trip(), NOW)
                    if i["category"] == "GoWild")
        self.assertEqual(29.0, tp.reprice(item, self.desert_trip(), NOW))
        self.assertEqual(34.0, tp.reprice(item, self.desert_trip(back_gw=20.0), NOW))
        self.assertIsNone(tp.reprice(item, self.desert_trip(back_gw=None), NOW))

    def test_run_validate_rebuilds_from_fresh_pages(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        def records(flights_by):
            return [dict(origin=o, destination=d, date=day, status="ok", flights=fl,
                         checked_at="2026-10-21T05:00:00-07:00")
                    for (o, d, day), fl in flights_by.items()]

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(tp, "OUTPUT", Path(tmp)), \
                patch.object(tp, "FLIGHTS", Path(tmp) / "flights.jsonl"), \
                patch.object(tp, "CALENDARS", Path(tmp) / "calendars.jsonl"), \
                patch("builtins.print"):
            tp.FLIGHTS.write_text("".join(json.dumps(r) + "\n" for r in records(self.desert_trip())))
            fetched = []

            def fake_fetch(legs, refresh):  # the return GoWild fare went up $5
                fetched.extend(legs)
                with tp.FLIGHTS.open("a") as out:
                    for r in records(self.desert_trip(back_gw=20.0)):
                        out.write(json.dumps(r) + "\n")

            report, by_trip, _ = tp.run_validate(["desert"], True, fetch=fake_fetch)
        self.assertEqual(2, len(fetched))
        self.assertIn("VALIDATION (final review)", report)
        self.assertIn("$29.00 → $34.00", report)
        self.assertIn("all passed.", report)
        self.assertIn("$34.00 GoWild", report)

    def test_couple_and_voucher(self):
        # The voucher is non-transferable: it only ever covers YOUR base fare.
        items = tp.build_itineraries("desert", self.desert_trip(), NOW)
        couple = next(i for i in items if i["category"] == "Couple")
        # You fly GoWild both ways ($0.01 base), so the voucher covers nothing here.
        self.assertEqual(0.0, couple["voucher"])
        self.assertEqual(29.0, couple["user_total"])
        self.assertEqual(29 + 108, couple["total"])
        self.assertEqual([], tp.rule_problems(couple))
        self.assertEqual(couple["total"], tp.reprice(couple, self.desert_trip(), NOW))
        dd = next(i for i in items if i["category"] == "Discount Den")
        # Your DD $49 + $59; est. base = (fare - $15.40 domestic taxes) / 1.075 each.
        self.assertEqual(71.81, dd["voucher"])
        self.assertAlmostEqual(108 - 71.81, tp._effective(dd))
        # Both on Discount Den on one booking: still only your base fare.
        both = next(i for i in items if i["category"] == "Couple DD")
        self.assertEqual(71.81, both["voucher"])
        self.assertEqual(round(2 * 108 - 71.81, 2), both["total"])
        self.assertEqual([], tp.rule_problems(both))
        self.assertEqual(both["total"], tp.reprice(both, self.desert_trip(), NOW))
        cheap = by_key(
            flight("SFO", "ONT", "2026-12-05T21:56:00", "2026-12-05T23:23:00", dd=18.98),
            flight("ONT", "SFO", "2026-12-08T19:26:00", "2026-12-08T21:01:00", dd=18.98),
        )
        two = next(i for i in tp.build_itineraries("desert", cheap, NOW) if i["category"] == "Couple DD")
        one_base = 2 * (18.98 - 15.40) / 1.075
        self.assertAlmostEqual(round(one_base, 2), two["voucher"])
        self.assertAlmostEqual(round(2 * 37.96 - one_base, 2), two["total"], places=1)
        # A mix: the voucher covers your Discount Den flight's base, on its own booking.
        mixed = by_key(
            flight("SFO", "LAS", "2026-11-06T18:30:00", "2026-11-06T20:00:00", gw=79.0, dd=49.0),
            flight("PSP", "SFO", "2026-11-08T19:00:00", "2026-11-08T20:30:00", gw=15.0, dd=59.0),
        )
        mix = next(i for i in tp.build_itineraries("desert", mixed, NOW) if i["category"] == "Couple")
        self.assertEqual("GoWild + Discount Den", mix["user_category"])
        self.assertEqual(round((49 - 15.40) / 1.075, 2), mix["voucher"])
        # Same dates and airports: the list keeps the cheaper way for two (GoWild here).
        self.assertEqual(["Couple"], [i["category"] for i in tp.rank_trip(items)["couple"]])
        # The voucher caps at $100, and with separate tickets only the largest ticket counts.
        big = flight("SFO", "SLC", "2026-11-06T09:00:00", "2026-11-06T11:45:00", dd=300.0)
        self.assertEqual(100, tp._voucher([big, big], [300.0, 300.0], False))
        small = flight("SFO", "DEN", "2026-11-06T09:00:00", "2026-11-06T11:45:00", dd=40.0)
        self.assertEqual(round((40 - 15.40) / 1.075, 2), tp._voucher([small, small], [40.0, 40.0], True))

    def test_prune_keeps_every_winner(self):
        from unittest.mock import patch
        fares_out = [(None, 23.0), (79.0, 49.0), (98.99, None), (59.0, 102.98), (None, 66.0)]
        fares_back = [(None, 19.0), (79.0, None), (59.0, 54.0), (None, 88.0)]
        flights = []
        for day in ("2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08", "2026-11-09"):
            for n, h in enumerate(range(6, 23, 2)):
                for gw in ("LAS", "ONT"):
                    g, d = fares_out[(n + len(gw)) % len(fares_out)]
                    flights.append(flight("SFO", gw, f"{day}T{h:02d}:00:00", f"{day}T{h+1:02d}:30:00", gw=g, dd=d))
                    g, d = fares_back[(n * 3 + len(day)) % len(fares_back)]
                    flights.append(flight(gw, "SFO", f"{day}T{h:02d}:15:00", f"{day}T{h+1:02d}:45:00", gw=g, dd=d))
        data = by_key(*flights)
        key = lambda i: (i["category"], i["leave"][:10], i["home_arrival"][:10], i["gateway_in"], i["gateway_out"])
        pruned = {key(i): round(tp._value(i), 2) for i in tp.build_itineraries("desert", data, NOW)}
        with patch.object(tp, "_prune", lambda ways, now, keep=3: ways):
            full = {key(i): round(tp._value(i), 2) for i in tp.build_itineraries("desert", data, NOW)}
        self.assertTrue(full)
        self.assertEqual(full, pruned)

    def test_reprice_couple_keeps_your_fare_mix(self):
        # GoWild on both flights, but Discount Den is cheaper outbound: you pay the mix.
        flights = by_key(
            flight("SFO", "MIA", "2026-11-14T12:20:00", "2026-11-15T00:44:00", gw=152.36, dd=132.36),
            flight("MIA", "SFO", "2026-11-17T05:50:00", "2026-11-17T11:17:00", gw=72.36, dd=132.36),
        )
        items = tp.build_itineraries("key_west", flights, NOW)
        couple = min((i for i in items if i["category"] == "Couple"), key=lambda i: i["total"])
        self.assertEqual("GoWild + Discount Den", couple["user_category"])
        self.assertEqual(204.72, couple["user_total"])
        self.assertEqual(couple["total"], tp.reprice(couple, flights, NOW))

    def test_death_valley_joshua_tree_combo(self):
        flights = by_key(
            flight("OAK", "LAS", "2026-11-26T15:58:00", "2026-11-26T17:34:00", dd=27.98),
            flight("ONT", "SFO", "2026-11-30T20:31:00", "2026-11-30T22:04:00", dd=72.98),
            # A Fri-Sun trip is too short for both parks.
            flight("SFO", "LAS", "2026-11-06T18:30:00", "2026-11-06T20:00:00", gw=14.0, dd=49.0),
            flight("PSP", "SFO", "2026-11-08T19:00:00", "2026-11-08T20:30:00", gw=15.0, dd=59.0),
        )
        items = tp.build_itineraries("desert", flights, NOW)
        combo = tp.combo_items(items, tp.TRIPS["desert"]["combo"])
        # Only the Thanksgiving trip has enough time on the ground for both parks.
        self.assertEqual({("2026-11-26", "LAS", "ONT")},
                         {(i["leave"][:10], i["gateway_in"], i["gateway_out"]) for i in combo})
        report = tp.build_report({"desert": items}, ["Coverage: test"], NOW)
        self.assertIn("Death Valley + Joshua Tree in one trip", report)
        self.assertIn("OAK/SFO ⇄ LAS in / ONT out", report)

    def test_both_on_discount_den_needs_two_seats(self):
        out_leg = flight("SFO", "SLC", "2026-11-21T11:20:00", "2026-11-21T14:16:00", dd=60.98)
        out_leg["discountDenFareSeatsRemaining"] = "1 Seat Left!"
        back = flight("SLC", "SFO", "2026-11-24T13:30:00", "2026-11-24T14:56:00", dd=86.98)
        cats = {i["category"] for i in tp.build_itineraries("park_city", by_key(out_leg, back), NOW)}
        self.assertIn("Discount Den", cats)       # one traveller can still book it
        self.assertNotIn("Couple DD", cats)       # two can't at that fare
        out_leg["discountDenFareSeatsRemaining"] = "3 Seats Left!"
        cats = {i["category"] for i in tp.build_itineraries("park_city", by_key(out_leg, back), NOW)}
        self.assertIn("Couple DD", cats)

    def test_watch_due(self):
        jobs = [dict(origin="SFO", destination="SJU", date="2026-10-30"),
                dict(origin="SFO", destination="SJU", date="2026-11-06"),
                dict(origin="SFO", destination="LAS", date="2026-10-22")]
        due = tp.watch_due(jobs, {}, NOW)
        self.assertEqual(["2026-10-30", "2026-10-22"], [j["date"] for j in due])
        latest = {("SFO", "SJU", "2026-10-30"): dict(status="ok", checked_at="2026-10-21T08:00:00-07:00")}
        self.assertEqual(["2026-10-22"], [j["date"] for j in tp.watch_due(jobs, latest, NOW)])


if __name__ == "__main__":
    unittest.main()
