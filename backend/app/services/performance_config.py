"""
Teacher Performance Score — configurable weights.

Change these values here to adjust the scoring model without touching
any other code.  All weights must sum to 1.0.

Score is always in the range [0.0, 5.0].
"""

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

WEIGHTS: dict[str, float] = {
    # 35 % — average lecture rating (1–5 scale)
    "overall_rating": 0.35,

    # 25 % — problem solving: doubts answered / total doubts
    "problem_solving": 0.25,

    # 20 % — student engagement: % of students who started watching a lecture
    #         combined with whether they interacted (pause/replay/rewind)
    "student_engagement": 0.20,

    # 10 % — lecture completion: average completion % across all students
    "lecture_completion": 0.10,

    # 10 % — AI dependency signal: NOT simply "fewer = better".
    #         High AI questions + low completion + high rewinds = bad signal.
    #         High AI questions + high completion + high engagement = curious students.
    "ai_dependency": 0.10,
}

# Minimum data thresholds before a sub-score is included
MIN_RATINGS: int = 1         # at least this many ratings for rating sub-score
MIN_DOUBTS: int = 1          # at least this many doubts for problem-solving sub-score
MIN_PLAYBACK_ROWS: int = 1   # at least this many playback rows for engagement sub-score
