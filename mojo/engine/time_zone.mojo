"""
time_zone.mojo — Time zone handling and conversion. Zero Python imports.
Replaces pytz basics for the decision engine.

Public API:
  utc_offset, convert_time, is_dst, effective_offset, time_difference,
  format_offset, is_valid_zone, local_to_utc, utc_to_local, overlap_hours
"""
from std.math import abs as fabs


# ── Zone Offset Lookup ────────────────────────────────────────────────────────


fn utc_offset(zone_name: String) -> Float64:
    """Return UTC offset in hours for named zone."""
    if zone_name == "UTC" or zone_name == "GMT":
        return 0.0
    if zone_name == "EST":
        return -5.0
    if zone_name == "CST":
        return -6.0
    if zone_name == "MST":
        return -7.0
    if zone_name == "PST":
        return -8.0
    if zone_name == "CET":
        return 1.0
    if zone_name == "EET":
        return 2.0
    if zone_name == "JST":
        return 9.0
    if zone_name == "IST":
        return 5.5
    if zone_name == "AEST":
        return 10.0
    return 0.0


# ── Valid Zone Check ──────────────────────────────────────────────────────────


fn is_valid_zone(name: String) -> Bool:
    """Check if zone name is supported."""
    if name == "UTC":
        return True
    if name == "GMT":
        return True
    if name == "EST":
        return True
    if name == "CST":
        return True
    if name == "MST":
        return True
    if name == "PST":
        return True
    if name == "CET":
        return True
    if name == "EET":
        return True
    if name == "JST":
        return True
    if name == "IST":
        return True
    if name == "AEST":
        return True
    return False


# ── DST Check ─────────────────────────────────────────────────────────────────


fn is_dst(month: Int, zone_name: String) -> Bool:
    """Simplified DST: US zones (EST/CST/MST/PST) observe Mar-Nov.
    European CET/EET observe Mar-Oct. Others: no DST."""
    if zone_name == "EST" or zone_name == "CST" or zone_name == "MST" or zone_name == "PST":
        return month >= 3 and month <= 11
    if zone_name == "CET" or zone_name == "EET":
        return month >= 3 and month <= 10
    return False


# ── Effective Offset ──────────────────────────────────────────────────────────


fn effective_offset(zone_name: String, month: Int) -> Float64:
    """utc_offset + 1 if DST is active."""
    var base = utc_offset(zone_name)
    if is_dst(month, zone_name):
        return base + 1.0
    return base


# ── Time Difference ───────────────────────────────────────────────────────────


fn time_difference(zone1: String, zone2: String) -> Float64:
    """Difference in hours between two zones (zone2 - zone1)."""
    return utc_offset(zone2) - utc_offset(zone1)


# ── Format Offset ─────────────────────────────────────────────────────────────


fn format_offset(offset_hours: Float64) -> String:
    """Format as '+05:30' or '-08:00'."""
    var sign: String = "+"
    var h = offset_hours
    if h < 0.0:
        sign = "-"
        h = -h
    var hours_int = Int(h)
    var frac = h - Float64(hours_int)
    var minutes_int = Int(frac * 60.0 + 0.5)

    var h_str: String = ""
    if hours_int < 10:
        h_str = "0" + String(hours_int)
    else:
        h_str = String(hours_int)

    var m_str: String = ""
    if minutes_int < 10:
        m_str = "0" + String(minutes_int)
    else:
        m_str = String(minutes_int)

    return sign + h_str + ":" + m_str


# ── Normalize Hours ───────────────────────────────────────────────────────────


fn _normalize_time(total_minutes: Int) -> List[Int]:
    """Normalize total minutes from midnight to [hour, minute] in 0-23."""
    var m = total_minutes % 1440
    if m < 0:
        m += 1440
    var result = List[Int]()
    result.append(m // 60)
    result.append(m % 60)
    return result^


# ── Convert Time ──────────────────────────────────────────────────────────────


fn convert_time(
    hour: Int, minute: Int, from_zone: String, to_zone: String,
) -> List[Int]:
    """Convert time between zones. Returns [hour, minute] (0-23)."""
    var from_off = utc_offset(from_zone)
    var to_off = utc_offset(to_zone)
    var diff = to_off - from_off
    var total_minutes = hour * 60 + minute + Int(diff * 60.0)
    return _normalize_time(total_minutes)


# ── Local to UTC ──────────────────────────────────────────────────────────────


fn local_to_utc(hour: Int, minute: Int, zone: String) -> List[Int]:
    """Convert local time to UTC."""
    return convert_time(hour, minute, zone, "UTC")


# ── UTC to Local ──────────────────────────────────────────────────────────────


fn utc_to_local(hour: Int, minute: Int, zone: String) -> List[Int]:
    """Convert UTC to local time."""
    return convert_time(hour, minute, "UTC", zone)


# ── Overlap Hours ─────────────────────────────────────────────────────────────


fn overlap_hours(
    zone1: String,
    zone2: String,
    work_start: Int = 9,
    work_end: Int = 17,
) -> Int:
    """Business hour overlap between two zones.
    Computes overlap of [work_start, work_end) in each zone mapped to UTC."""
    var off1 = utc_offset(zone1)
    var off2 = utc_offset(zone2)

    # Convert business hours to UTC
    var start1_utc = work_start - Int(off1)
    var end1_utc = work_end - Int(off1)
    var start2_utc = work_start - Int(off2)
    var end2_utc = work_end - Int(off2)

    # Normalize to 0-23
    start1_utc = start1_utc % 24
    if start1_utc < 0:
        start1_utc += 24
    end1_utc = end1_utc % 24
    if end1_utc < 0:
        end1_utc += 24
    start2_utc = start2_utc % 24
    if start2_utc < 0:
        start2_utc += 24
    end2_utc = end2_utc % 24
    if end2_utc < 0:
        end2_utc += 24

    # Simple non-wrapping overlap calculation
    var s1 = start1_utc
    var e1 = end1_utc
    var s2 = start2_utc
    var e2 = end2_utc

    # Handle wrapping (shouldn't happen for typical offsets)
    if e1 <= s1:
        e1 += 24
    if e2 <= s2:
        e2 += 24

    var overlap_start = s1
    if s2 > overlap_start:
        overlap_start = s2
    var overlap_end = e1
    if e2 < overlap_end:
        overlap_end = e2

    var result = overlap_end - overlap_start
    if result < 0:
        result = 0
    return result
