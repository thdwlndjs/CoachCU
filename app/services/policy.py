from __future__ import annotations

from datetime import time

from app.models import DevicePolicy


def parse_hhmm(value: str) -> time:
    hour_text, minute_text = value.split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid HH:MM time: {value}")
    return time(hour=hour, minute=minute)


def is_within_active_window(policy: DevicePolicy, current: time) -> bool:
    start = parse_hhmm(policy.active_start_time)
    end = parse_hhmm(policy.active_end_time)
    if start == end:
        return True
    if start < end:
        return start <= current <= end
    return current >= start or current <= end


def should_present_for_trigger(policy: DevicePolicy, trigger: str, current: time) -> bool:
    if trigger == "manual":
        return True
    if trigger == "login" and not policy.run_on_login:
        return False
    if trigger == "unlock" and not policy.run_on_unlock:
        return False
    return is_within_active_window(policy, current)
