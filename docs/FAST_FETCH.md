# Faster Frontier fetching from an already-verified browser tab (Oct 21, 2026)

Rendering every `InternalSelect` page in Chrome costs ~10 s and most of a CPU core. During
the Oct 2026 trip/cruise/Buffalo searches (~11,600 flight pages), three cheaper requests
were verified against normal page loads. All of them run **inside a tab that has already
loaded a normal booking.flyfrontier.com page** (same cookies, so PerimeterX is satisfied);
none of them work from plain `requests`/`curl_cffi`.

## 1. Flight pages: `fetch()` the InternalSelect HTML
`driver.execute_async_script` with `fetch(url, {credentials: 'include', headers: {Accept:
'text/html,...'}})`, then parse the embedded JSON model exactly like `colombia_search.model`.
- 30/30 pages matched a normal render flight-for-flight and fare-for-fare; ~1-3 s each, little CPU.
- Send a browser-like `Accept` header: in an A/B test, sessions without it got ~5x more
  HTTP 406s.
- A 406 (empty body) flags the session: load a page normally or start a fresh browser, then
  retry. ~5 s between requests per worker, 6 workers (~55 pages/min total) was sustainable;
  faster bursts drew 406s.

## 2. Month calendars: `POST /Flight/GetLowFareCalendarAvailability`
The calendar page (`c=true`) is drawn by JavaScript, so fetched HTML has only placeholder cells
(it would wrongly read as "no service"). The data comes from this JSON endpoint instead:
- Body: `jsonString=<search JSON>&__RequestVerificationToken=<token>`, form-encoded, with
  `X-Requested-With: XMLHttpRequest`. The token is in the page
  (`input[name=__RequestVerificationToken]`); the JSON template is what the page itself sends
  (originOne/destinationOne/departureDateOne = YYYY-MM-15).
- It answers for the **session's current search**, so fetch that route's InternalSelect page
  first. Each day returns `amountString` (the calendar price), `amount` (**base fare**),
  `taxesAndFees`, `isDiscountDen`, `isUnavailable`.
- Available-day sets matched rendered calendars exactly (including months with 0 days).

## 3. Route schedules: `GET /Flight/RetrieveSchedule?calendarSelectableDays.Origin=X&calendarSelectableDays.Destination=Y`
Session-independent and tiny: `lastAvailableDate` of `0001-01-01` means Frontier doesn't sell the
market; otherwise it gives the last bookable date and `disabledDates` (days with no flight).
Checking every hub x gateway pair this way (1,142 checks) mapped the network in minutes and let
calendar runs skip unserved routes.
