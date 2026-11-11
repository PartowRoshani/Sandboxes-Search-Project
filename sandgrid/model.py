"""Sand-only grid with persistent, continuous-flow gates.

Display values: 1=full, 0.5=half full, 0=empty.
Internal half-unit values: 2=full, 1=half full, 0=empty.

Opening an internal downward gate costs 1+2*(source_before+source_after),
where source values are internal half-units and AFTER means after full settling.
A bottom exit follows the same rule; its opening stays active for the entire
cascade triggered by that paid action and drains repeatedly without new costs.
Horizontal directed gates cost 1 and transfer at most one half unit per opening.

A blocked gate remains open while it has sand upstream. When capacity appears,
it transfers automatically. An internal downward gate remains open while its
source still has sand (even if blocked by a full destination); it closes when
its source is empty after the cascade. A horizontal gate closes after its one
half-unit transfer. The exact goal is normalized to state 0.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterator


@dataclass(frozen=True, slots=True)
class Action:
    id: int
    kind: str
    src: int
    dst: int | None
    label: str


class SandGrid:
    MODEL_VERSION = 'continuous-flow-v2-full-is-1'

    def __init__(self, rows: int, cols: int):
        if rows < 1 or cols < 1 or rows * cols > 15:
            raise ValueError('rows and cols must be positive and rows*cols <= 15')
        self.rows, self.cols = rows, cols
        self.n = rows * cols
        self.base = 3 ** self.n
        self.powers = tuple(3 ** i for i in range(self.n))
        self.vertical_edges = (rows - 1) * cols
        self.actions: list[Action] = []
        self.down_ids: dict[int, int] = {}
        self.side_ids: dict[tuple[int, int], int] = {}
        for i in range(self.n):
            row, col = divmod(i, cols)
            dst = i + cols if row + 1 < rows else None
            ai = len(self.actions)
            self.down_ids[i] = ai
            self.actions.append(Action(ai, 'down', i, dst, f'Gate ({row+1},{col+1}) ↓'))
        for i in range(self.n):
            row, col = divmod(i, cols)
            for delta in (-1, 1):
                nc = col + delta
                if 0 <= nc < cols:
                    dst = row * cols + nc
                    ai = len(self.actions)
                    self.side_ids[(i, dst)] = ai
                    self.actions.append(Action(ai, 'side', i, dst,
                                               f'Side ({row+1},{col+1}) → ({row+1},{nc+1})'))
        self.horizontal_edges = len(self.actions) - self.n
        self.gate_count = self.vertical_edges + self.horizontal_edges
        self.vertical_gate_mask = (1 << self.vertical_edges) - 1
        self.open_gate_limit = 1 << self.gate_count
        self.side_gate_bits = {
            (action.src, action.dst): self.vertical_edges + action.id - self.n
            for action in self.actions[self.n:]
        }

    def gate_bit(self, action_id: int) -> int | None:
        if not 0 <= action_id < len(self.actions):
            raise ValueError('invalid action ID')
        action = self.actions[action_id]
        if action.kind == 'down':
            return action.src if action.dst is not None else None
        return self.vertical_edges + action_id - self.n

    def encode(self, occupancies: list[int] | tuple[int, ...], mask: int = 0) -> int:
        if len(occupancies) != self.n or any(v not in (0, 1, 2) for v in occupancies):
            raise ValueError('occupancies must contain exactly n entries in {0,1,2}')
        if not self.valid_mask(occupancies, mask):
            raise ValueError('gate mask is not physically settled')
        if not any(occupancies):
            mask = 0
        return sum(v * p for v, p in zip(occupancies, self.powers)) + self.base * mask

    def decode(self, state: int) -> tuple[list[int], int]:
        if state < 0:
            raise ValueError('negative state')
        code, mask = state % self.base, state // self.base
        if mask >= self.open_gate_limit:
            raise ValueError('state exceeds gate-mask limit')
        occ = []
        for _ in range(self.n):
            code, digit = divmod(code, 3)
            occ.append(digit)
        return occ, mask

    def valid_mask(self, occ: list[int] | tuple[int, ...], mask: int) -> bool:
        if len(occ) != self.n or any(v not in (0, 1, 2) for v in occ):
            return False
        if mask < 0 or mask >= self.open_gate_limit:
            return False
        # An open internal gate has sand behind it but cannot currently flow.
        for bit in range(self.vertical_edges):
            if mask & (1 << bit) and not (occ[bit] > 0 and occ[bit + self.cols] == 2):
                return False
        for action in self.actions[self.n:]:
            bit = self.gate_bit(action.id)
            assert bit is not None and action.dst is not None
            if mask & (1 << bit) and not (occ[action.src] > 0 and occ[action.dst] == 2):
                return False
        return True

    def from_display(self, grid: list[list[float]], convention: str = 'full-is-1') -> int:
        if len(grid) != self.rows or any(len(row) != self.cols for row in grid):
            raise ValueError('grid shape mismatch')
        if convention not in ('full-is-1', 'empty-is-1'):
            raise ValueError('unknown display convention')
        flat = [v for row in grid for v in row]
        if any(v not in (0, 0.5, 1) for v in flat):
            raise ValueError('display cells must be 0, 0.5, or 1')
        return self.encode([int(round(2 * (v if convention == 'full-is-1' else 1-v)))
                            for v in flat])

    def to_display(self, state: int, convention: str = 'full-is-1') -> list[list[float]]:
        if convention not in ('full-is-1', 'empty-is-1'):
            raise ValueError('unknown display convention')
        occ, _ = self.decode(state)
        return [[(occ[row*self.cols+col] / 2 if convention == 'full-is-1'
                  else 1 - occ[row*self.cols+col] / 2)
                 for col in range(self.cols)] for row in range(self.rows)]

    def random_state(self, seed: int | None = None) -> int:
        rnd = random.Random(seed)
        return self.encode(rnd.choices((0, 1, 2), weights=(2, 1, 1), k=self.n))

    def is_goal(self, state: int) -> bool:
        return state == 0

    def _step_with_events(self, state: int, action_id: int,
                          record_events: bool = True) -> tuple[int, int, list[dict], list[int]] | None:
        if not 0 <= action_id < len(self.actions):
            raise ValueError('invalid action ID')
        action = self.actions[action_id]
        occ, mask = self.decode(state)
        src = action.src
        before = occ[src]
        bit = self.gate_bit(action_id)
        if action.kind == 'down' and before == 0:
            return None
        if action.kind == 'side' and before != 2:
            return None  # opening a horizontal gate requires a full source
        if bit is not None:
            if mask & (1 << bit):
                return None
            mask |= 1 << bit

        # A bottom exit does not persist to the next *paid* action, but while
        # this action settles it can keep draining any sand arriving from above.
        exit_src = src if action.kind == 'down' and action.dst is None else None
        events: list[dict] = []
        # Every vertical transfer strictly lowers sand; every side gate can pass
        # at most once per action; every exit removes sand. Hence termination.
        while True:
            moved = False
            if exit_src is not None and occ[exit_src] > 0:
                units = occ[exit_src]
                occ[exit_src] = 0
                if record_events:
                    events.append(dict(kind='exit', src=exit_src, dst=None,
                                       amount=units / 2, gate_bit=None,
                                       gate_closed=False, automatic=(len(events) > 0)))
                moved = True
            else:
                # Bottom-up gravity makes newly freed space propagate back up.
                for g in range(self.vertical_edges - 1, -1, -1):
                    if not mask & (1 << g):
                        continue
                    dst = g + self.cols
                    units = min(occ[g], 2 - occ[dst])
                    if units <= 0:
                        continue
                    occ[g] -= units
                    occ[dst] += units
                    if record_events:
                        events.append(dict(kind='down', src=g, dst=dst,
                                           amount=units / 2, gate_bit=g,
                                           gate_closed=False,
                                           automatic=(g != bit)))
                    moved = True
                    break
                if not moved:
                    for g in range(self.vertical_edges, self.gate_count):
                        if not mask & (1 << g):
                            continue
                        a = self.actions[self.n + g - self.vertical_edges]
                        assert a.dst is not None
                        if occ[a.src] <= 0 or occ[a.dst] == 2:
                            continue
                        occ[a.src] -= 1
                        occ[a.dst] += 1
                        mask &= ~(1 << g)  # one half-unit per opening
                        if record_events:
                            events.append(dict(kind='side', src=a.src, dst=a.dst,
                                               amount=0.5, gate_bit=g,
                                               gate_closed=True,
                                               automatic=(g != bit)))
                        moved = True
                        break
            if not moved:
                break

        # Close gates whose upstream supply is exhausted. Any other open gate
        # is blocked by a full destination and waits for a future action.
        closed: list[int] = []
        for g in range(self.gate_count):
            if not (mask & (1 << g)):
                continue
            if g < self.vertical_edges:
                source = g
            else:
                source = self.actions[self.n + g - self.vertical_edges].src
            if occ[source] == 0:
                mask &= ~(1 << g)
                if record_events:
                    closed.append(g)
        if not any(occ):
            if record_events:
                closed.extend(g for g in range(self.gate_count) if mask & (1 << g))
            mask = 0
        result = self.encode(occ, mask)
        cost = 1 + 2*(before + occ[src]) if action.kind == 'down' else 1
        return result, cost, events, closed

    def step(self, state: int, action_id: int) -> tuple[int, int] | None:
        result = self._step_with_events(state, action_id, record_events=False)
        return None if result is None else (result[0], result[1])

    def successors(self, state: int) -> Iterator[tuple[int, int, int]]:
        occ, mask = self.decode(state)
        for i, v in enumerate(occ):
            if v and (i >= self.vertical_edges or not (mask & (1 << i))):
                result = self.step(state, self.down_ids[i])
                if result is not None:
                    nxt, cost = result
                    yield nxt, self.down_ids[i], cost
        for action in self.actions[self.n:]:
            bit = self.gate_bit(action.id)
            assert bit is not None
            if occ[action.src] == 2 and not (mask & (1 << bit)):
                result = self.step(state, action.id)
                if result is not None:
                    nxt, cost = result
                    yield nxt, action.id, cost

    def trace(self, initial: int, actions: list[int] | tuple[int, ...]) -> list[dict]:
        output = [dict(state=initial, action=None, step_cost=0,
                       total_cost=0, flow_events=[], closed_gate_bits=[])]
        state, total = initial, 0
        for action_id in actions:
            result = self._step_with_events(state, action_id)
            if result is None:
                raise ValueError(f'invalid action {action_id} at state {state}')
            state, cost, events, closed = result
            total += cost
            output.append(dict(state=state, action=action_id, step_cost=cost,
                               total_cost=total, flow_events=events,
                               closed_gate_bits=closed))
        return output

    def cell_string(self, state: int, full_is_one: bool = True) -> str:
        grid = self.to_display(state, 'full-is-1' if full_is_one else 'empty-is-1')
        return '\n'.join(' '.join(f'{v:g}' for v in row) for row in grid)
