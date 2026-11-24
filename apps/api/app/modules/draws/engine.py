"""Motor de regras e sorteio. Módulo puro: sem I/O, sem banco, sem logs.

Modelo: grafo bipartido givers → receivers com as arestas permitidas. Um sorteio válido
é um emparelhamento perfeito nesse grafo, ou seja, uma permutação em que ninguém tira a
si mesmo nem alguém proibido pelas regras.
"""

import random
import secrets
from collections import deque
from collections.abc import Collection, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

MIN_PARTICIPANTS = 3
DEFAULT_CYCLE_STEP_BUDGET = 50_000


@dataclass(frozen=True)
class BlockedPair[K: Hashable]:
    giver: K
    receiver: K
    bidirectional: bool = False


@dataclass(frozen=True)
class DrawRules[K: Hashable]:
    participants: Sequence[K]
    circles: Sequence[Collection[K]] = ()
    blocked_pairs: Sequence[BlockedPair[K]] = ()


@dataclass(frozen=True)
class Feasibility[K: Hashable]:
    possible: bool
    # Participantes com menos opções (como quem dá ou quem recebe), do mais restrito ao menos.
    most_constrained: list[tuple[K, int]] = field(default_factory=list)


class DrawError(Exception):
    pass


class NotEnoughParticipantsError(DrawError):
    pass


class ImpossibleDrawError[K: Hashable](DrawError):
    def __init__(self, most_constrained: list[tuple[K, int]]) -> None:
        super().__init__("no perfect matching")
        self.most_constrained = most_constrained


def allowed_edges[K: Hashable](rules: DrawRules[K]) -> dict[K, set[K]]:
    people = list(dict.fromkeys(rules.participants))
    present = set(people)
    forbidden: dict[K, set[K]] = {p: {p} for p in people}
    for circle in rules.circles:
        members = [m for m in circle if m in present]
        for m in members:
            forbidden[m].update(members)
    for pair in rules.blocked_pairs:
        if pair.giver in present and pair.receiver in present:
            forbidden[pair.giver].add(pair.receiver)
            if pair.bidirectional:
                forbidden[pair.receiver].add(pair.giver)
    return {p: present - forbidden[p] for p in people}


def hopcroft_karp[K: Hashable](
    givers: Sequence[K], adjacency: Mapping[K, Sequence[K]]
) -> dict[K, K]:
    """Emparelhamento máximo em O(E·√V). Retorna giver → receiver."""
    inf = float("inf")
    match_giver: dict[K, K | None] = {g: None for g in givers}
    match_receiver: dict[K, K] = {}
    dist: dict[K | None, float] = {}

    def bfs() -> bool:
        queue: deque[K] = deque()
        for g in givers:
            if match_giver[g] is None:
                dist[g] = 0
                queue.append(g)
            else:
                dist[g] = inf
        dist[None] = inf
        while queue:
            g = queue.popleft()
            if dist[g] < dist[None]:
                for r in adjacency[g]:
                    nxt = match_receiver.get(r)
                    if dist.get(nxt, inf) == inf:
                        dist[nxt] = dist[g] + 1
                        if nxt is not None:
                            queue.append(nxt)
        return dist[None] != inf

    def dfs(g: K) -> bool:
        # Iterativo seria mais longo; a profundidade é limitada pelo nº de participantes.
        for r in adjacency[g]:
            nxt = match_receiver.get(r)
            if dist.get(nxt, inf) == dist[g] + 1 and (nxt is None or dfs(nxt)):
                match_giver[g] = r
                match_receiver[r] = g
                return True
        dist[g] = inf
        return False

    while bfs():
        for g in givers:
            if match_giver[g] is None:
                dfs(g)
    return {g: r for g, r in match_giver.items() if r is not None}


def check_feasibility[K: Hashable](rules: DrawRules[K]) -> Feasibility[K]:
    edges = allowed_edges(rules)
    people = list(edges)
    if len(people) < MIN_PARTICIPANTS:
        return Feasibility(possible=False, most_constrained=[])
    adjacency = {g: sorted(edges[g], key=people.index) for g in people}
    matching = hopcroft_karp(people, adjacency)
    possible = len(matching) == len(people)
    return Feasibility(possible=possible, most_constrained=[] if possible else _tightest(edges))


def draw[K: Hashable](
    rules: DrawRules[K],
    *,
    prefer_single_cycle: bool = True,
    rng: random.Random | None = None,
    cycle_step_budget: int = DEFAULT_CYCLE_STEP_BUDGET,
) -> dict[K, K]:
    """Sorteia giver → receiver respeitando as regras.

    Com prefer_single_cycle, tenta primeiro um único ciclo (A→B→C→…→A); se não achar
    dentro do orçamento de passos, cai no emparelhamento aleatório geral.
    """
    rng = rng or secrets.SystemRandom()
    edges = allowed_edges(rules)
    people = list(edges)
    if len(people) < MIN_PARTICIPANTS:
        raise NotEnoughParticipantsError()

    if prefer_single_cycle:
        cycle = _random_hamiltonian_cycle(edges, rng, cycle_step_budget)
        if cycle is not None:
            return cycle

    givers = people[:]
    rng.shuffle(givers)
    adjacency: dict[K, list[K]] = {}
    for g in givers:
        options = list(edges[g])
        rng.shuffle(options)
        adjacency[g] = options
    matching = hopcroft_karp(givers, adjacency)
    if len(matching) != len(people):
        raise ImpossibleDrawError(_tightest(edges))
    return matching


def is_valid_assignment[K: Hashable](rules: DrawRules[K], assignment: Mapping[K, K]) -> bool:
    edges = allowed_edges(rules)
    people = set(edges)
    return (
        set(assignment) == people
        and set(assignment.values()) == people
        and all(r in edges[g] for g, r in assignment.items())
    )


def cycle_count[K: Hashable](assignment: Mapping[K, K]) -> int:
    seen: set[K] = set()
    cycles = 0
    for start in assignment:
        if start in seen:
            continue
        cycles += 1
        node = start
        while node not in seen:
            seen.add(node)
            node = assignment[node]
    return cycles


def _random_hamiltonian_cycle[K: Hashable](
    edges: Mapping[K, set[K]], rng: random.Random, budget: int
) -> dict[K, K] | None:
    people = list(edges)
    if any(not edges[p] for p in people):
        return None
    incoming: dict[K, int] = {p: 0 for p in people}
    for targets in edges.values():
        for t in targets:
            incoming[t] += 1
    if any(n == 0 for n in incoming.values()):
        return None

    start = rng.choice(people)
    path = [start]
    visited = {start}
    options: list[list[K]] = [_shuffled(edges[start], rng)]
    steps = 0
    while options and steps < budget:
        steps += 1
        if len(path) == len(people):
            if start in edges[path[-1]]:
                return {path[i]: path[(i + 1) % len(path)] for i in range(len(path))}
            options.pop()
            visited.discard(path.pop())
            continue
        candidates = options[-1]
        while candidates and candidates[-1] in visited:
            candidates.pop()
        if not candidates:
            options.pop()
            visited.discard(path.pop())
            continue
        nxt = candidates.pop()
        path.append(nxt)
        visited.add(nxt)
        options.append(_shuffled(edges[nxt], rng))
    return None


def _shuffled[K: Hashable](items: Iterable[K], rng: random.Random) -> list[K]:
    result = list(items)
    rng.shuffle(result)
    return result


def _tightest[K: Hashable](edges: Mapping[K, set[K]], limit: int = 3) -> list[tuple[K, int]]:
    incoming: dict[K, int] = {p: 0 for p in edges}
    for targets in edges.values():
        for t in targets:
            incoming[t] += 1
    scores = [(p, min(len(edges[p]), incoming[p])) for p in edges]
    order = list(edges)
    scores.sort(key=lambda item: (item[1], order.index(item[0])))
    return scores[:limit]
