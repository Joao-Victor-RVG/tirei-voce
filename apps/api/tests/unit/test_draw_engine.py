import itertools
import random
from collections.abc import Sequence

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.modules.draws.engine import (
    BlockedPair,
    DrawRules,
    ImpossibleDrawError,
    NotEnoughParticipantsError,
    allowed_edges,
    check_feasibility,
    cycle_count,
    draw,
    hopcroft_karp,
    is_valid_assignment,
)


def brute_force_possible(rules: DrawRules[int]) -> bool:
    edges = allowed_edges(rules)
    people = list(edges)
    return any(
        all(r in edges[g] for g, r in zip(people, perm, strict=True))
        for perm in itertools.permutations(people)
    )


@st.composite
def draw_rules(draw_: st.DrawFn, min_size: int = 3, max_size: int = 12) -> DrawRules[int]:
    n = draw_(st.integers(min_value=min_size, max_value=max_size))
    people = list(range(n))
    circles = draw_(st.lists(st.sets(st.sampled_from(people), min_size=2, max_size=4), max_size=3))
    pairs = draw_(
        st.lists(
            st.tuples(st.sampled_from(people), st.sampled_from(people), st.booleans()).filter(
                lambda t: t[0] != t[1]
            ),
            max_size=n,
        )
    )
    return DrawRules(
        participants=people,
        circles=[sorted(c) for c in circles],
        blocked_pairs=[BlockedPair(g, r, b) for g, r, b in pairs],
    )


def assert_respects_rules(rules: DrawRules[int], result: dict[int, int]) -> None:
    people = set(rules.participants)
    # Permutação: todos dão e recebem exatamente uma vez.
    assert set(result) == people
    assert sorted(result.values()) == sorted(people)
    for giver, receiver in result.items():
        assert giver != receiver, "ninguém tira a si mesmo"
        for circle in rules.circles:
            assert not (giver in circle and receiver in circle), "círculo violado"
        for pair in rules.blocked_pairs:
            assert (giver, receiver) != (pair.giver, pair.receiver), "par bloqueado violado"
            if pair.bidirectional:
                assert (giver, receiver) != (pair.receiver, pair.giver), "par bidirecional violado"
    assert is_valid_assignment(rules, result)


# --- Testes de propriedade ---


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(rules=draw_rules(), seed=st.integers(), prefer_cycle=st.booleans())
def test_draw_always_respects_rules_or_reports_impossible(
    rules: DrawRules[int], seed: int, prefer_cycle: bool
) -> None:
    feasibility = check_feasibility(rules)
    try:
        result = draw(rules, prefer_single_cycle=prefer_cycle, rng=random.Random(seed))
    except ImpossibleDrawError as exc:
        assert not feasibility.possible
        assert exc.most_constrained
        return
    assert feasibility.possible
    assert_respects_rules(rules, result)


@settings(max_examples=300, deadline=None)
@given(rules=draw_rules(max_size=7))
def test_feasibility_matches_brute_force(rules: DrawRules[int]) -> None:
    assert check_feasibility(rules).possible == brute_force_possible(rules)


@settings(max_examples=100, deadline=None)
@given(n=st.integers(min_value=3, max_value=60), seed=st.integers())
def test_unconstrained_groups_get_a_single_cycle(n: int, seed: int) -> None:
    rules = DrawRules(participants=list(range(n)))
    result = draw(rules, prefer_single_cycle=True, rng=random.Random(seed))
    assert_respects_rules(rules, result)
    assert cycle_count(result) == 1


# --- Casos específicos ---


def test_couples_never_draw_each_other() -> None:
    rules = DrawRules(
        participants=["joao", "maria", "pedro", "ana", "lia"],
        circles=[{"joao", "maria"}, {"pedro", "ana"}],
    )
    for seed in range(200):
        result = draw(rules, rng=random.Random(seed))
        assert_respects_rules(rules, result)  # type: ignore[arg-type]
        assert result["joao"] != "maria" and result["maria"] != "joao"


def test_impossible_when_circle_is_majority() -> None:
    # 3 de 4 numa mesma família: os três só poderiam tirar o 4, que só recebe um presente.
    rules = DrawRules(participants=[1, 2, 3, 4], circles=[{1, 2, 3}])
    feasibility = check_feasibility(rules)
    assert not feasibility.possible
    assert feasibility.most_constrained == [(1, 1), (2, 1), (3, 1)]
    with pytest.raises(ImpossibleDrawError) as exc:
        draw(rules)
    assert exc.value.most_constrained == [(1, 1), (2, 1), (3, 1)]


def test_blocked_pair_one_way_vs_bidirectional() -> None:
    one_way = DrawRules(participants=[1, 2, 3], blocked_pairs=[BlockedPair(1, 2)])
    # Com 3 pessoas só existem os ciclos 1→2→3→1 e 1→3→2→1.
    assert draw(one_way, rng=random.Random(1)) == {1: 3, 3: 2, 2: 1}

    both = DrawRules(participants=[1, 2, 3], blocked_pairs=[BlockedPair(1, 2, bidirectional=True)])
    assert not check_feasibility(both).possible


def test_minimum_participants() -> None:
    with pytest.raises(NotEnoughParticipantsError):
        draw(DrawRules(participants=[1, 2]))
    assert not check_feasibility(DrawRules(participants=[1, 2])).possible


def test_falls_back_to_general_matching_when_no_single_cycle() -> None:
    # Dois casais em 4 pessoas, com 1→3 bloqueado: só existe solução com dois ciclos.
    rules = DrawRules(
        participants=[1, 2, 3, 4],
        blocked_pairs=[
            BlockedPair(1, 3),
            BlockedPair(2, 4),
            BlockedPair(3, 2),
            BlockedPair(4, 1),
        ],
    )
    assert check_feasibility(rules).possible
    result = draw(rules, prefer_single_cycle=True, rng=random.Random(0))
    assert_respects_rules(rules, result)


def test_cycle_budget_exhaustion_still_returns_valid_draw() -> None:
    rules = DrawRules(participants=list(range(30)), circles=[set(range(0, 10))])
    result = draw(rules, rng=random.Random(3), cycle_step_budget=1)
    assert_respects_rules(rules, result)


def test_rules_ignore_unknown_people_and_duplicates() -> None:
    rules = DrawRules(
        participants=[1, 2, 3, 3],
        circles=[{1, 99}],
        blocked_pairs=[BlockedPair(1, 42), BlockedPair(77, 2)],
    )
    edges = allowed_edges(rules)
    assert edges == {1: {2, 3}, 2: {1, 3}, 3: {1, 2}}


def test_draw_is_random() -> None:
    rules = DrawRules(participants=list(range(6)))
    results = {tuple(sorted(draw(rules).items())) for _ in range(50)}
    assert len(results) > 10


def test_hopcroft_karp_maximum_matching() -> None:
    adjacency: dict[str, Sequence[str]] = {"a": ["x"], "b": ["x", "y"], "c": ["y"]}
    assert len(hopcroft_karp(["a", "b", "c"], adjacency)) == 2


def test_large_group_is_fast() -> None:
    n = 200
    rules = DrawRules(
        participants=list(range(n)),
        circles=[set(range(i, i + 2)) for i in range(0, n, 2)],  # 100 casais
    )
    result = draw(rules)
    assert_respects_rules(rules, result)
