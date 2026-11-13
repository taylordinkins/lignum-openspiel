"""AlphaZero-style bot: policy-value net (primed on the strategist) plus PUCT search.

Modules: ``features`` (state encoding from one seat's point of view), ``net`` (numpy inference of
an exported policy-value net), ``search`` (PUCT with hidden-pick resampling and a per-seat value
vector), ``bot`` (the ``AZBot`` seat). Training lives in ``tools/az_train.py`` (torch, offline).
"""
