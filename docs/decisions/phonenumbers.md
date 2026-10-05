# Phone numbers with `phonenumbers`

**Status:** in use (since #31)

## Context

The Donate page asks monthly supporters for an optional mobile number, so the charity can later
send them a monthly reminder on WhatsApp, or by text message in Nepal. Sending to a number needs
it in one consistent international form (`+9779841234567`), and a number that can't receive a
message is worse than none. Supporters type numbers in many ways (`984-1234567`,
`+977 9841234567`, `07400 123456`), and each country has its own lengths and mobile ranges.

## Decision

- **Add [`phonenumbers`](https://pypi.org/project/phonenumbers/),** the Python port of Google's
  libphonenumber. It's pure Python with no dependencies of its own and knows every country's
  number lengths and which ranges are mobiles.
- **Forms ask for a country and a number.** The country select starts on the one chosen in Site
  settings (Nepal by default); a number typed with its own `+code` keeps it.
- **Store E.164** (`+<country code><number>`), and accept only numbers that can receive a
  message: mobiles, plus the countries (such as the US and India) whose numbers can't be told
  apart from landlines.
- The countries offered are a short list in `core/phone.py`: Nepal and the countries where most
  Nepali supporters live or work. Add to it when a charity needs another.

A hand-written check (a country code plus 6–12 digits) was the alternative. It needs no
dependency, but it would accept numbers that can't exist.

## Consequences

- A third runtime dependency (after Wagtail and WhiteNoise), with country data that changes
  several times a year. Keep it up to date with the other dependencies.
- `core.phone.normalise_mobile()` is the one place numbers are checked; anything that stores a
  phone number uses it.
