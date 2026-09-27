"""Offline regression checks; no browser, network, or email."""
import contextlib
import io
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import gowild_deal_report as report
from config import DESTINATION_SERVICE_STARTS, INTERNATIONAL_DESTINATIONS


class DestinationScheduleTests(unittest.TestCase):
    def search(self, code, day, blackout=False):
        driver = object()
        with (
            patch.object(report, "ORIGINS", ["SFO", "SJC"]),
            patch.object(report, "is_blackout_date", return_value=blackout),
            patch.object(report, "_fetch_route", return_value=([], False)) as fetch,
            patch.object(report.time, "sleep"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            deals, count, returned_driver = report.search_group(
                driver, {code: INTERNATIONAL_DESTINATIONS[code]}, day, True, []
            )
        self.assertIs(driver, returned_driver)
        self.assertEqual([], deals)
        return count, fetch

    def test_colombia_launch_boundary_for_both_origins(self):
        for code, start in DESTINATION_SERVICE_STARTS.items():
            launch = datetime.fromisoformat(start)
            with self.subTest(code=code):
                count, fetch = self.search(code, launch - timedelta(days=1))
                self.assertEqual(0, count)
                fetch.assert_not_called()
                count, fetch = self.search(code, launch)
                self.assertEqual(2, count)
                self.assertEqual(2, fetch.call_count)
                for call in fetch.call_args_list:
                    self.assertIn(f"d1={code}&", call.args[1])

    def test_blackout_still_skips_launched_destination(self):
        count, fetch = self.search("CTG", datetime(2026, 12, 19), blackout=True)
        self.assertEqual(0, count)
        fetch.assert_not_called()

    def test_mexico_additions_searched_without_launch_restriction(self):
        for code in ("SJD", "MEX", "GDL"):
            with self.subTest(code=code):
                count, fetch = self.search(code, datetime(2026, 10, 6))
                self.assertEqual(2, count)
                self.assertEqual(2, fetch.call_count)

    def test_bookable_flight_does_not_imply_gowild(self):
        deals = report.extract_deals(
            [{"isGoWildFareEnabled": False, "goWildFare": 10,
              "discountDenFare": 120}],
            "SFO", "MEX", INTERNATIONAL_DESTINATIONS["MEX"], "Oct 6, 2026", True,
        )
        self.assertEqual(["Discount Den"], [deal["type"] for deal in deals])


if __name__ == "__main__":
    unittest.main()
