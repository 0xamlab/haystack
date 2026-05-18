"""
datetime.mojo — Date/time operations. Zero Python imports.

Replaces Python's datetime module with pure algorithmic epoch ↔ date conversion.
All times are UTC. Uses Unix epoch (1970-01-01T00:00:00Z).

Public API:
  Timestamp          — struct with epoch seconds + nanoseconds
  DateComponents     — struct for civil date/time components
  now_epoch()        — current Unix epoch via libc time()
  epoch_to_iso()     — format epoch as ISO 8601
  iso_to_epoch()     — parse ISO 8601 to epoch
  format_duration_ms() — human-readable duration
  days_between()     — days between two epochs
  add_days()         — add days to epoch
  day_of_week()      — 0=Monday...6=Sunday
  is_leap_year()     — leap year check
  year/month/day/hour/minute/second — date component extraction
"""


# ── Constants ────────────────────────────────────────────────────────────────

comptime _SECONDS_PER_MINUTE = 60
comptime _SECONDS_PER_HOUR = 3600
comptime _SECONDS_PER_DAY = 86400


# ── Timestamp struct ─────────────────────────────────────────────────────────


struct Timestamp(Copyable, Movable):
    """Unix timestamp with optional nanosecond precision."""
    var epoch_sec: Int
    var nano: Int

    fn __init__(out self, epoch_sec: Int = 0, nano: Int = 0):
        self.epoch_sec = epoch_sec
        self.nano = nano

    fn __copyinit__(out self, copy: Self):
        self.epoch_sec = copy.epoch_sec
        self.nano = copy.nano

    fn total_ms(self) -> Int:
        """Total milliseconds since epoch."""
        return self.epoch_sec * 1000 + self.nano // 1_000_000

    fn total_us(self) -> Int:
        """Total microseconds since epoch."""
        return self.epoch_sec * 1_000_000 + self.nano // 1000


# ── DateComponents struct ────────────────────────────────────────────────────


struct DateComponents(Copyable, Movable):
    """Civil date/time components."""
    var yr: Int
    var mo: Int
    var dy: Int
    var hr: Int
    var mn: Int
    var sc: Int

    fn __init__(out self, yr: Int = 0, mo: Int = 0, dy: Int = 0, hr: Int = 0, mn: Int = 0, sc: Int = 0):
        self.yr = yr
        self.mo = mo
        self.dy = dy
        self.hr = hr
        self.mn = mn
        self.sc = sc

    fn __copyinit__(out self, copy: Self):
        self.yr = copy.yr
        self.mo = copy.mo
        self.dy = copy.dy
        self.hr = copy.hr
        self.mn = copy.mn
        self.sc = copy.sc


# ── now_epoch — current Unix epoch via libc ──────────────────────────────────


def now_epoch() raises -> Int:
    """Return current Unix epoch seconds via Python's time module.
    Uses Python interop as a portable fallback.
    """
    from std.python import Python
    var time_mod = Python.import_module("time")
    return Int(py=time_mod.time())


# ── Leap year ────────────────────────────────────────────────────────────────


fn is_leap_year(y: Int) -> Bool:
    """Return True if year is a leap year."""
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)


# ── Internal: days in month ──────────────────────────────────────────────────


fn _days_in_month(y: Int, m: Int) -> Int:
    """Days in given month (1-12) for given year."""
    if m == 2:
        if is_leap_year(y):
            return 29
        return 28
    if m == 4 or m == 6 or m == 9 or m == 11:
        return 30
    return 31


# ── Epoch → date components (civil_from_days algorithm) ──────────────────────
# Based on Howard Hinnant's civil_from_days algorithm:
# https://howardhinnant.github.io/date_algorithms.html


fn _civil_from_epoch(epoch: Int) -> DateComponents:
    """Convert epoch seconds to DateComponents(year, month, day, hour, minute, second)."""
    var s = epoch
    var sign = 1
    if s < 0:
        sign = -1
        s = -s

    var day_seconds: Int
    var z: Int
    if sign < 0:
        # For negative epochs: floor division
        z = -((s + _SECONDS_PER_DAY - 1) // _SECONDS_PER_DAY)
        var remainder = s % _SECONDS_PER_DAY
        if remainder == 0:
            day_seconds = 0
            z = -(s // _SECONDS_PER_DAY)
        else:
            day_seconds = _SECONDS_PER_DAY - remainder
    else:
        z = s // _SECONDS_PER_DAY
        day_seconds = s % _SECONDS_PER_DAY

    var h = day_seconds // _SECONDS_PER_HOUR
    var m = (day_seconds % _SECONDS_PER_HOUR) // _SECONDS_PER_MINUTE
    var sec = day_seconds % _SECONDS_PER_MINUTE

    # Howard Hinnant civil_from_days
    # z = days since 1970-01-01
    z = z + 719468  # shift epoch from 1970-01-01 to 0000-03-01
    var era: Int
    if z >= 0:
        era = z // 146097
    else:
        era = (z - 146096) // 146097
    var doe = z - era * 146097  # day of era [0, 146096]
    var yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365  # year of era
    var y = yoe + era * 400
    var doy = doe - (365 * yoe + yoe // 4 - yoe // 100)  # day of year [0, 365]
    var mp = (5 * doy + 2) // 153  # month index [0, 11]
    var d = doy - (153 * mp + 2) // 5 + 1  # day [1, 31]
    var mn: Int
    if mp < 10:
        mn = mp + 3
    else:
        mn = mp - 9
    if mn <= 2:
        y = y + 1

    return DateComponents(y, mn, d, h, m, sec)


# ── Date component accessors ─────────────────────────────────────────────────


fn year(epoch: Int) -> Int:
    """Extract year from epoch."""
    var result = _civil_from_epoch(epoch)
    return result.yr


fn month(epoch: Int) -> Int:
    """Extract month (1-12) from epoch."""
    var result = _civil_from_epoch(epoch)
    return result.mo


fn day(epoch: Int) -> Int:
    """Extract day (1-31) from epoch."""
    var result = _civil_from_epoch(epoch)
    return result.dy


fn hour(epoch: Int) -> Int:
    """Extract hour (0-23) from epoch."""
    var result = _civil_from_epoch(epoch)
    return result.hr


fn minute(epoch: Int) -> Int:
    """Extract minute (0-59) from epoch."""
    var result = _civil_from_epoch(epoch)
    return result.mn


fn second(epoch: Int) -> Int:
    """Extract second (0-59) from epoch."""
    var result = _civil_from_epoch(epoch)
    return result.sc


# ── Epoch → ISO 8601 ─────────────────────────────────────────────────────────


fn _pad2(v: Int) -> String:
    """Zero-pad integer to 2 digits."""
    if v < 10:
        return "0" + String(v)
    return String(v)


fn _pad4(v: Int) -> String:
    """Zero-pad integer to 4 digits."""
    if v < 10:
        return "000" + String(v)
    if v < 100:
        return "00" + String(v)
    if v < 1000:
        return "0" + String(v)
    return String(v)


fn epoch_to_iso(epoch: Int) -> String:
    """Format epoch seconds as ISO 8601 UTC string: YYYY-MM-DDTHH:MM:SSZ."""
    var parts = _civil_from_epoch(epoch)
    return (
        _pad4(parts.yr) + "-" + _pad2(parts.mo) + "-" + _pad2(parts.dy)
        + "T"
        + _pad2(parts.hr) + ":" + _pad2(parts.mn) + ":" + _pad2(parts.sc)
        + "Z"
    )


# ── ISO 8601 → Epoch ─────────────────────────────────────────────────────────
# Civil date → days since epoch (Howard Hinnant days_from_civil)


fn _days_from_civil(y_in: Int, m: Int, d: Int) -> Int:
    """Convert year/month/day to days since 1970-01-01."""
    var y = y_in
    if m <= 2:
        y = y - 1
    var era: Int
    if y >= 0:
        era = y // 400
    else:
        era = (y - 399) // 400
    var yoe = y - era * 400  # year of era [0, 399]
    var doy: Int
    if m > 2:
        doy = (153 * (m - 3) + 2) // 5 + d - 1
    else:
        doy = (153 * (m + 9) + 2) // 5 + d - 1
    var doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


fn _parse_int_at(s: String, start: Int, length: Int) -> Int:
    """Parse an integer from string at position start with given length."""
    var bs = s.as_bytes()
    var result = 0
    for i in range(length):
        var idx = start + i
        if idx < len(s):
            var c = Int(bs[idx])
            if c >= 48 and c <= 57:
                result = result * 10 + (c - 48)
    return result


fn iso_to_epoch(iso: String) -> Int:
    """Parse ISO 8601 string (YYYY-MM-DDTHH:MM:SSZ) to Unix epoch seconds."""
    var n = len(iso)
    # Minimum: YYYY-MM-DDTHH:MM:SSZ = 20 chars
    if n < 20:
        return 0

    var y = _parse_int_at(iso, 0, 4)
    var m = _parse_int_at(iso, 5, 2)
    var d = _parse_int_at(iso, 8, 2)
    var hh = _parse_int_at(iso, 11, 2)
    var mm = _parse_int_at(iso, 14, 2)
    var ss = _parse_int_at(iso, 17, 2)

    var days = _days_from_civil(y, m, d)
    return days * _SECONDS_PER_DAY + hh * _SECONDS_PER_HOUR + mm * _SECONDS_PER_MINUTE + ss


# ── Duration formatting ──────────────────────────────────────────────────────


fn format_duration_ms(ms: Int) -> String:
    """Format milliseconds as human-readable duration.
    Examples: '150ms', '3.75s', '2m 30s', '1h 5m 30s'.
    """
    if ms < 0:
        return "-" + format_duration_ms(-ms)
    if ms == 0:
        return "0ms"

    var total_sec = ms // 1000
    var rem_ms = ms % 1000

    if total_sec == 0:
        return String(ms) + "ms"

    var hours = total_sec // 3600
    var mins = (total_sec % 3600) // 60
    var secs = total_sec % 60

    var result = String("")

    if hours > 0:
        result += String(hours) + "h"
        if mins > 0 or secs > 0:
            result += " " + String(mins) + "m"
        if secs > 0:
            result += " " + String(secs) + "s"
        return result

    if mins > 0:
        result += String(mins) + "m"
        if secs > 0:
            result += " " + String(secs) + "s"
        elif rem_ms > 0:
            result += " 0." + _ms_frac(rem_ms) + "s"
        return result

    # Seconds only — include fractional
    if rem_ms > 0:
        var frac = _ms_frac(rem_ms)
        return String(secs) + "." + frac + "s"
    else:
        return String(secs) + "s"


fn _ms_frac(ms: Int) -> String:
    """Format milliseconds as decimal fraction (strip trailing zeros)."""
    var d1 = ms // 100
    var d2 = (ms // 10) % 10
    var d3 = ms % 10
    if d3 != 0:
        return String(d1) + String(d2) + String(d3)
    if d2 != 0:
        return String(d1) + String(d2)
    return String(d1)


# ── Day arithmetic ───────────────────────────────────────────────────────────


fn days_between(epoch1: Int, epoch2: Int) -> Int:
    """Number of days between two epochs (absolute value)."""
    var diff = epoch2 - epoch1
    if diff < 0:
        diff = -diff
    return diff // _SECONDS_PER_DAY


fn add_days(epoch: Int, days: Int) -> Int:
    """Add (or subtract) days to an epoch."""
    return epoch + days * _SECONDS_PER_DAY


# ── Day of week ──────────────────────────────────────────────────────────────


fn day_of_week(epoch: Int) -> Int:
    """Day of week: 0=Monday, 1=Tuesday, ..., 6=Sunday.
    1970-01-01 was a Thursday (3).
    """
    var days = epoch // _SECONDS_PER_DAY
    # 1970-01-01 is Thursday = day 3 (Mon=0)
    var dow = (days + 3) % 7
    if dow < 0:
        dow += 7
    return dow
