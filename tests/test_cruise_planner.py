"""Offline checks for cruise_planner; no browser, network, or email.
Flight records are synthetic, shaped like the ones colombia_search.search keeps."""
import unittest
from datetime import date

import cruise_planner as cp
from tests.test_trip_planner import NOW, by_key, flight


def cruise(**kw):
    base = dict(id="#1", nights=4, sail="Nov 30", now=169, save=95, rating="5", line="Norwegian",
                ship="Norwegian Getaway", note="", link=None, **{"from": "Port Canaveral, FL",
                                                                  "to": "Port Canaveral, FL"})
    base.update(kw)
    return base


class CandidateTests(unittest.TestCase):
    def test_sail_dates_roll_into_next_year(self):
        self.assertEqual(date(2026, 11, 30), cp.sail_date("Nov 30"))
        self.assertEqual(date(2027, 1, 5), cp.sail_date("Jan 5"))

    def test_window_nights_and_ports(self):
        deals = [cruise(), cruise(id="#2", nights=14), cruise(id="#3", sail="Jan 5"),
                 cruise(id="#4", **{"from": "Honolulu, Oahu, HI", "to": "Honolulu, Oahu, HI"}),
                 cruise(id="#5", **{"from": "San Francisco, CA", "to": "San Francisco, CA"})]
        got = {c["id"]: c for c in cp.candidates(deals)}
        self.assertEqual({"#1", "#5"}, set(got))
        self.assertEqual("2026-12-04", got["#1"]["debark_date"])

    def test_deal_page_rates_both_layouts(self):
        a = "Cheapest Inside $937 Vacations To Go Rate $905 You Save $32 Cheapest Balcony $1,069 Vacations To Go Rate $1,030"
        b = "Brochure Inside $1,953 Our Inside $485 You Save 75% Brochure Oceanview $2,553 Our Oceanview $631"
        self.assertEqual({"Inside": 905, "Balcony": 1030}, cp.parse_deal_page(a)["rates"])
        self.assertEqual({"Inside": 485, "Oceanview": 631}, cp.parse_deal_page(b)["rates"])


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.c = cp.candidates([cruise()])[0]

    def test_timing_and_price_for_two(self):
        flights = by_key(
            # Day before: fine (hotel night). Morning of: must land by 11:00 - 1 h transfer.
            flight("SFO", "MCO", "2026-11-29T22:00:00", "2026-11-30T06:15:00", dd=99.0),
            flight("SFO", "MCO", "2026-11-30T06:00:00", "2026-11-30T14:30:00", dd=49.0),  # too late
            # Home: ship docks 08:30 + 2.5 h + 1 h transfer -> flights from 12:00.
            flight("MCO", "SFO", "2026-12-04T10:00:00", "2026-12-04T13:00:00", dd=39.0),  # too early
            flight("MCO", "SFO", "2026-12-04T15:00:00", "2026-12-04T18:00:00", gw=38.98, dd=59.0),
        )
        best = cp.cruise_packages(self.c, flights, NOW, keep=5)
        self.assertTrue(best)
        top = best[0]
        self.assertEqual(338, 2 * self.c["now"])
        self.assertEqual("2026-11-29T22:00:00", top["out"][0]["legs"][0]["departureDate"])
        self.assertEqual("2026-12-04T15:00:00", top["back"][0]["legs"][0]["departureDate"])
        # You: DD out $99 + GoWild back $38.98; partner DD $99 + $59.
        self.assertEqual("you GoWild + Discount Den + partner DD", top["how"])
        self.assertEqual(round(99 + 38.98 + 99 + 59, 2), top["flights_two"])
        self.assertEqual(round(338 + top["flights_two"], 2), top["total"])
        self.assertEqual(0, top["hotel_nights"])  # red-eye lands the morning of sailing

    def test_bay_area_port_needs_no_flights(self):
        sf = cp.candidates([cruise(**{"from": "San Francisco, CA", "to": "San Francisco, CA"})])[0]
        best = cp.cruise_packages(sf, {}, NOW)
        self.assertEqual(0.0, best[0]["flights_two"])
        self.assertEqual(338, best[0]["total"])
        report = cp.build_report(best, ["x"], NOW)
        self.assertIn("No flights: sails from and returns to the Bay Area", report)

    def test_no_valid_flights_means_no_package(self):
        late = by_key(flight("SFO", "MCO", "2026-11-30T09:00:00", "2026-11-30T17:30:00", dd=49.0),
                      flight("MCO", "SFO", "2026-12-04T15:00:00", "2026-12-04T18:00:00", dd=59.0))
        self.assertEqual([], cp.cruise_packages(self.c, late, NOW))


if __name__ == "__main__":
    unittest.main()
