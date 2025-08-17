"""
Default maintenance parameters for Restic repository operations
Centralized configuration following Restic best practices
"""
from dataclasses import dataclass


@dataclass
class MaintenanceDefaults:
    """Default maintenance parameters following Restic best practices"""
    # Retention policy - keeps reasonable amount while preventing unbounded growth
    KEEP_LAST = 7        # always keep last 7 snapshots regardless of age
    KEEP_HOURLY = 6      # keep 6 most recent hourly snapshots (6 hours coverage)
    KEEP_DAILY = 7       # keep 7 most recent daily snapshots (1 week coverage)
    KEEP_WEEKLY = 4      # keep 4 most recent weekly snapshots (1 month coverage)
    KEEP_MONTHLY = 6     # keep 6 most recent monthly snapshots (6 months coverage)
    KEEP_YEARLY = 0      # disable yearly retention by default
    
    # Scheduling defaults
    DISCARD_SCHEDULE = "0 3 * * *"         # daily at 3am - combines forget+prune operations
    CHECK_SCHEDULE = "0 2 * * 0"           # weekly Sunday 2am (staggered from backups)
    
    # Check operation defaults
    CHECK_READ_DATA_SUBSET = "5%"          # balance integrity vs performance
    
    # Resource priority (lower than backups)
    NICE_LEVEL = 10                        # vs backup nice -n 5
    IONICE_CLASS = 3                       # idle vs backup ionice -c 2
    IONICE_LEVEL = 7                       # vs backup ionice -n 4