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

    def test_blackout_drops_gowild_only(self):
        flights = by_key(
            flight("SFO", "SLC", "2026-11-26T09:00:00", "2026-11-26T11:45:00", gw=14.0, dd=40.0),
            flight("SLC", "SFO", "2026-11-29T18:00:00", "2026-11-29T19:00:00", gw=14.0, dd=45.0),
        )
        cats = {i["category"]: i for i in tp.build_itineraries("park_city", flights, NOW)}
        self.assertNotIn("GoWild", cats)               # Nov 29 is a blackout
        self.assertEqual(59.0, cats["GoWild + Discount Den"]["total"])
        self.assertEqual(85.0, cats["Discount Den"]["total"])

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
        self.assertEqual({"Discount Den", "GoWild pending"}, cats)
        report = tp.build_report({"puerto_rico": items}, ["Coverage: test"], NOW)
        self.assertIn("GoWild opens Tue Oct 27 (SFO midnight)", report)
        self.assertIn("Cheapest Discount Den round trips found", report)
        self.assertIn("OVERALL TOP 3", report)

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
