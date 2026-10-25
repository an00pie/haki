"""Deterministic rule modules for ScamTrace AI.

Every rule module exposes an `evaluate(...)` pure function that returns a FindingModel
with outcome: "positive" (risk detected), "negative" (clean/corroborated), or "unknown" (default whenever data is missing/inconclusive).
"""
