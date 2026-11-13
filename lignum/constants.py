"""Derived constants (R-001, R-003..R-007, R-011, R-075; ACTIONS 1.5, 3, 7).

Plain ints, defined once. Card values live in data/components/*.yaml; tests check that the
counts here equal the yaml counts.
"""

# ACTIONS 7: totals of the two ID spaces.
NUM_DISTINCT_ACTIONS = 440
MAX_CHANCE_OUTCOMES = 103

# R-003
MIN_PLAYERS = 2
MAX_PLAYERS = 4

# ACTIONS 1.5 index ranges
NUM_AREAS = 6
NUM_KINDS = 3
NUM_PIECES = 6
NUM_ZONES = 6
NUM_CRAFTWORK_TYPES = 5

# R-005 card counts
NUM_TASKS = 19
NUM_TASK_SLOTS = 48
NUM_PLACEMENT_CARDS = 19
NUM_WINTER_CARDS = 8
NUM_BUILDINGS = 10
NUM_PW_CARDS = 10

# R-004, R-011, R-018
CLEARING_LOC = 23
MAX_LOANS = 2
MAX_JOINERS = 3  # R-078 (joiner spaces, R-010)
LOAN_AMOUNT = 4
STARTING_MONEY = 5

# Wood kinds (R-007)
KIND_FIREWOOD = 0
KIND_SOFTWOOD = 1
KIND_HARDWOOD = 2

# Zones (ACTIONS 1.5)
ZONE_SALE = 0
ZONE_DRYING_1 = 1
ZONE_DRYING_2 = 2
ZONE_DRYING_3 = 3
ZONE_SAWING = 4
ZONE_FIREWOOD_STORAGE = 5


def piece_index(kind: int, milled: bool) -> int:
    """Piece index p = 2*kind + milled (ACTIONS 1.5): 0 FW disk, 1 FW log, ... 5 HW log."""
    return 2 * kind + int(milled)
