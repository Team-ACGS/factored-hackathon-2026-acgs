from datetime import timedelta, timezone

UTC_OFFSET_HOURS = {"PE": -5, "MX": -6, "CO": -5, "AR": -3, "US": -5, "BR": -3}


def zone(country: str) -> timezone:
    return timezone(timedelta(hours=UTC_OFFSET_HOURS[country]))
