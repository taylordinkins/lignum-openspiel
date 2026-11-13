"""ACTIONS.md internal consistency: ID tables and rule-to-action mapping vs RULES_SPEC.md."""

import re


def _spec_rules(spec_text):
    return set(re.findall(r"^### (R-\d{3})\b", spec_text, re.M))


def _check_contiguous(table, total):
    expected = 0
    for lo, hi, name, _ in table:
        assert lo == expected, f"{name}: starts at {lo}, expected {expected} (gap or overlap)"
        assert hi >= lo, name
        expected = hi + 1
    assert expected == total


def test_R001_spec_has_117_rule_headings(spec_text):
    """RULES_SPEC defines R-001..R-117 as consecutive headings."""
    assert sorted(_spec_rules(spec_text)) == [f"R-{i:03d}" for i in range(1, 118)]


def test_R001_decision_ids_are_contiguous_and_total_440(decision_table, actions_text):
    """ACTIONS 3/7: decision IDs 0..439 are contiguous, non-overlapping, total 440."""
    _check_contiguous(decision_table, 440)
    assert "`num_distinct_actions` = **440**" in actions_text


def test_R001_chance_ids_are_contiguous_and_total_103(chance_table, actions_text):
    """ACTIONS 2/7: chance IDs 0..102 are contiguous, non-overlapping, total 103."""
    _check_contiguous(chance_table, 103)
    assert "`max_chance_outcomes` = **103**" in actions_text


def test_R001_action_names_are_unique_within_each_table(decision_table, chance_table):
    """ACTIONS 2/3: every action name appears once in its table."""
    for table in (decision_table, chance_table):
        names = [n for _, _, n, _ in table]
        assert len(names) == len(set(names))


def test_R001_totals_table_matches_header_counts(actions_text):
    """ACTIONS 7: totals table states 440 decision ids (0-439) and 103 chance outcomes (0-102)."""
    assert re.search(r"Decision IDs \| \*\*440\*\* \(0–439\)", actions_text)
    assert re.search(r"Chance outcomes \| \*\*103\*\* \(0–102\)", actions_text)


def test_R001_mapping_action_names_exist_in_id_table(mapping_rows, decision_table):
    """ACTIONS 6: every backticked action name in the mapping is in the decision ID table."""
    names = {n for _, _, n, _ in decision_table}
    for rule_cell, action_cell in mapping_rows:
        if rule_cell.startswith("Chance"):
            continue
        for token in re.findall(r"`([A-Z][A-Z_]+)", action_cell):
            assert token in names, f"{rule_cell}: unknown action {token}"


def test_R001_mapping_id_ranges_agree_with_id_table(mapping_rows, decision_table):
    """ACTIONS 6: a parenthesised range after an action name equals that action's range in section
    3.
    """
    ranges = {n: (lo, hi) for lo, hi, n, _ in decision_table}
    for rule_cell, action_cell in mapping_rows:
        for name, arg, a, b in re.findall(
            r"`([A-Z_]+)(\([^`]*\))?`\s*\((\d+)(?:(?:–|-|\.\.)(\d+))?\)", action_cell
        ):
            lo, hi = ranges[name]
            got = (int(a), int(b) if b else int(a))
            # sub-ranges (e.g. MOVE_TO(23)) are allowed; they must lie inside the table range
            assert lo <= got[0] <= got[1] <= hi, f"{rule_cell}: {name} {got} outside {lo}-{hi}"
            if not arg:
                assert got == (lo, hi), f"{rule_cell}: {name} {got} vs table {lo}-{hi}"


def test_R001_mapping_rule_ids_exist_in_spec(mapping_rows, no_action_text, spec_text, rule_ids):
    """ACTIONS 6: every rule id used in the mapping or the no-action list is a spec heading."""
    spec = _spec_rules(spec_text)
    used = rule_ids(" ".join(r for r, _ in mapping_rows)) | rule_ids(no_action_text)
    assert used - spec == set()


def test_R001_every_rule_is_mapped_or_listed_as_no_action(
    mapping_rows, no_action_text, spec_text, rule_ids
):
    """ACTIONS 6: each RULES_SPEC rule appears in the rule-to-action table (rule column) or the no-
    action list.
    """
    spec = _spec_rules(spec_text)
    mapped = rule_ids(" ".join(r for r, _ in mapping_rows))
    no_action = rule_ids(no_action_text)
    missing = sorted(spec - mapped - no_action)
    assert missing == [], f"rules in neither the mapping nor the no-action list: {missing}"


def test_R001_no_action_list_does_not_contradict_mapping(mapping_rows, no_action_text, rule_ids):
    """ACTIONS 6: a rule listed as having no action (parentheticals ignored) is not also mapped to
    a decision action (chance row excepted).
    """
    decision_rows = [r for r, _ in mapping_rows if not r.startswith("Chance")]
    overlap = sorted(
        rule_ids(" ".join(decision_rows)) & rule_ids(re.sub(r"\([^)]*\)", "", no_action_text))
    )
    assert overlap == [], f"rules both mapped to actions and listed as no-action: {overlap}"
