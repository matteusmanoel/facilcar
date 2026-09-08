"""Derived age from a validated birth date — never an independent persisted fact."""

from __future__ import annotations

import re
from datetime import date

from sdr.domain.clock import now_brt


def compute_age(birth_date_str: str | None, *, today: date | None = None) -> int | None:
    """Age in years from DD/MM/AAAA or AAAA-MM-DD using the commercial BRT clock.

    Birthday on the reference day counts. Invalid calendar dates return None.
    """
    if not birth_date_str:
        return None
    text = str(birth_date_str).strip()
    if not text:
        return None
    try:
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
            if not m2:
                return None
            year, month, day = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        born = date(year, month, day)
    except ValueError:
        return None
    ref = today or now_brt().date()
    age = ref.year - born.year - ((ref.month, ref.day) < (born.month, born.day))
    return age if 0 < age < 130 else None
