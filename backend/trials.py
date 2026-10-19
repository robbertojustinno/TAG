"""Server-owned evaluation deadlines; existing customers remain unrestricted."""
from datetime import datetime, timezone
import math

def now():
    return datetime.now(timezone.utc)

def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def status(company):
    end = company.trial_expires_at
    remaining = max(0, math.ceil((aware(end)-now()).total_seconds()/86400)) if end else None
    return {'trial_days': company.trial_days, 'trial_started_at': company.trial_started_at,
            'trial_expires_at': end, 'trial_remaining_days': remaining,
            'trial_status': 'customer' if company.trial_days is None else
                ('pending' if end is None else ('expired' if remaining == 0 else 'active'))}
