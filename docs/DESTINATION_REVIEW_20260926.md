# Destination review — September 26, 2026

Added six search targets to the shared config: Los Cabos (SJD), Mexico City
(MEX), Guadalajara (GDL), Medellin (MDE), Bogota (BOG), and Cartagena (CTG).
Existing destinations are retained: empty results on two dates do not establish
that an airline has discontinued service.

## Sources and availability limits

- [Frontier's September 10 Colombia announcement](https://news.flyfrontier.com/frontier-announces-major-international-expansion-with-first-ever-service-to-colombia/)
  gives MCO–MDE a December 10 launch, MCO–BOG December 14, and MCO–CTG
  December 19, 2026. Service is subject to government approval. The scheduled
  checker skips travel dates before these launches, then searches normally in
  its 10/7/4-day window, subject to the existing blackout rules. It does not
  construct separate-ticket connections via Orlando.
- [Frontier's flights from Mexico page](https://flights.flyfrontier.com/en/flights-from-mexico)
  lists SJD, CUN, and PVR. SJD is included as a search target; a working Bay Area
  connection was not found in the recovered two-date probe.
- [Frontier's codeshare explanation](https://www.flyfrontier.com/travel/travel-info/codeshare-partners/)
  explains that itineraries sold by Frontier can include partner-operated flights.
  [Its GoWild international FAQ](https://faq.flyfrontier.com/help/can-i-book-international-flights-using-the-gowild-pass)
  excludes codeshare travel. MEX/GDL results are not evidence of GoWild eligibility.
  The checker only reports GoWild when the flight has `isGoWildFareEnabled`
  and a positive `goWildFare`, and Discount Den when a positive
  `discountDenFare` is returned. Ordinary cash fares are not reported.

## Recovered probe

Claude's background job `b8nm0xzoq` completed with exit code 0. Its saved output
was recovered on September 26; these are that run's results, not a new live scan.
All searches originated at SFO.

| Destination | Travel dates in 2026 | Flights returned | GoWild returned |
| --- | --- | --- | --- |
| MEX | October 6 / October 9 | 3 / 4 | 0 / 0 |
| GDL | October 6 / October 9 | 5 / 9 | 0 / 0 |
| SJD, MTY, CZM, MZT, ZIH, HUX, AUA, SAP, LIR, NAS, SXM | October 6 / October 9 | 0 / 0 each | 0 / 0 each |
| MDE | December 12 / December 15 | 0 / 0 | 0 / 0 |
| BOG | December 15 / December 17 | 0 / 0 | 0 / 0 |
| CTG | December 19 / December 26 | 0 / 0 | 0 / 0 |

The probe reported no captcha blocks, but its parser also returns an empty list
for missing flight data. Empty results therefore cannot prove no service.
It did not record Discount Den availability or operating carriers. No other
candidate destinations were added based solely on this probe.

## Scheduler handoff

The existing `Frontier Deal Check` task was verified ready, last result 0,
with Monday/Tuesday/Wednesday triggers (mask 14), at 03:01 Eastern / 00:01
Pacific. Its next run at inspection was September 28, 2026 at 03:01 Eastern.
The existing task reads this working tree, so these changes apply on its next
run without reinstalling the task. No new email or full live scan was triggered
during this handoff.
