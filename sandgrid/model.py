"""Discrete sand flow with persistent vertical connections.

Physical occupancy: 0=empty, 1=half, 2=full. This is intentionally the
reverse of the assignment's display code (1, 0.5, 0 respectively).

A state is represented by a single Python int:
    state = base3_occupancy + 3**(rows*cols) * open_vertical_mask
Open vertical connections persist only when their lower cell is full and
their upper cell is nonempty. All flow is resolved instantaneously.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterator


@dataclass(frozen=True, slots=True)
class Action:
    id: int
    kind: str  # 'down' or 'side'
    src: int
    dst: int | None
    label: str


class SandGrid:
    def __init__(self, rows: int, cols: int):
        if rows < 1 or cols < 1 or rows * cols > 15:
            raise ValueError('rows and cols must be positive and area <= 15')
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
            dst = i + cols if row < rows - 1 else None
            ai = len(self.actions)
            self.down_ids[i] = ai
            self.actions.append(Action(ai, 'down', i, dst, f'Gate ({row+1},{col+1}) ↓'))
        for i in range(self.n):
            row, col = divmod(i, cols)
            for delta in (-1, 1):
                nc = col + delta
                if nc < 0 or nc >= cols:
                    continue
                dst = row * cols + nc
                ai = len(self.actions)
                self.side_ids[(i, dst)] = ai
                self.actions.append(Action(ai, 'side', i, dst,
                                           f'Side ({row+1},{col+1}) → ({row+1},{nc+1})'))

    def encode(self, occupancies: list[int] | tuple[int, ...], mask: int = 0) -> int:
        if len(occupancies) != self.n or any(v not in (0, 1, 2) for v in occupancies):
            raise ValueError('occupancies must have rows*cols entries, each in 0,1,2')
        if mask < 0 or mask >= (1 << self.vertical_edges):
            raise ValueError('invalid open-gate mask')
        if not self.valid_mask(occupancies, mask):
            raise ValueError('open gates violate physical invariant')
        return sum(v * p for v, p in zip(occupancies, self.powers)) + self.base * mask

    def decode(self, state: int) -> tuple[list[int], int]:
        code, mask = state % self.base, state // self.base
        if mask >= 1 << self.vertical_edges or state < 0:
            raise ValueError('state is outside the modeled space')
        occ: list[int] = []
        for _ in range(self.n):
            code, digit = divmod(code, 3)
            occ.append(digit)
        return occ, mask

    def valid_mask(self, occ: list[int] | tuple[int, ...], mask: int) -> bool:
        if mask < 0 or mask >= 1 << self.vertical_edges:
            return False
        for i in range(self.vertical_edges):
            if (mask >> i) & 1 and not (occ[i] > 0 and occ[i + self.cols] == 2):
                return False
        return True

    def from_display(self, grid: list[list[float]], convention: str = 'empty-is-1') -> int:
        """Default follows the English statement: 0 full, 0.5 half, 1 empty.

        'full-is-1' instead treats 1 as full and 0 as empty, which is the
        convention apparently used in the teacher's worked example.
        """
        if len(grid) != self.rows or any(len(row) != self.cols for row in grid):
            raise ValueError('grid shape mismatch')
        if convention not in ('empty-is-1', 'full-is-1'):
            raise ValueError('unknown display convention')
        flat = [v for row in grid for v in row]
        if any(v not in (0, 0.5, 1) for v in flat):
            raise ValueError('display cells must be 0, 0.5, or 1')
        occ = [int(round((1 - v if convention == 'empty-is-1' else v) * 2)) for v in flat]
        return self.encode(occ)

    def to_display(self, state: int, convention: str = 'empty-is-1') -> list[list[float]]:
        occ, _ = self.decode(state)
        f = (lambda v: 1 - v / 2) if convention == 'empty-is-1' else (lambda v: v / 2)
        return [[f(occ[row * self.cols + col]) for col in range(self.cols)]
                for row in range(self.rows)]

    def random_state(self, seed: int | None = None) -> int:
        rnd = random.Random(seed)
        # Roughly 50% empty; of the other 50%, half half-filled, half full.
        return self.encode(rnd.choices((0, 1, 2), weights=(2, 1, 1), k=self.n))

    def is_goal(self, state: int) -> bool:
        return state == 0

    def _settle_column(self, occ: list[int], mask: int, col: int) -> int:
        """Settle connected vertical segments from bottom to top, then close dry edges."""
        start = 0
        while start < self.rows:
            end = start
            while end < self.rows - 1 and mask & (1 << (end * self.cols + col)):
                end += 1
            total = sum(occ[row * self.cols + col] for row in range(start, end + 1))
            for row in range(end, start - 1, -1):
                i = row * self.cols + col
                occ[i] = min(2, total)
                total -= occ[i]
            start = end + 1
        for row in range(self.rows - 1):
            i = row * self.cols + col
            if (mask >> i) & 1 and (occ[i] == 0 or occ[i + self.cols] != 2):
                mask &= ~(1 << i)
        return mask

    def step(self, state: int, action_id: int) -> tuple[int, int] | None:
        """Execute an applicable action, returning (successor, weighted cost).

        Inapplicable/redundant openings are omitted; all useful openings are
        modeled, including opening a blocked vertical gate to CONNECT sand.
        """
        if action_id < 0 or action_id >= len(self.actions):
            raise ValueError('invalid action ID')
        action = self.actions[action_id]
        occ, mask = self.decode(state)
        src = action.src
        if action.kind == 'down':
            if occ[src] == 0:
                return None
            if action.dst is None:
                before = occ[src]
                # Drain the entire connected vertical segment ending here.
                row, col = divmod(src, self.cols)
                while True:
                    occ[row * self.cols + col] = 0
                    if row == 0 or not (mask & (1 << ((row - 1) * self.cols + col))):
                        break
                    row -= 1
                for row2 in range(row, self.rows - 1):
                    mask &= ~(1 << (row2 * self.cols + col))
                return self.encode(occ, mask), 1 + 2 * before
            if mask & (1 << src):
                # The vertical connection is already open, so it can't be re-opened.
                return None
            before = occ[src]
            mask |= 1 << src
            mask = self._settle_column(occ, mask, src % self.cols)
            after = occ[src]
            return self.encode(occ, mask), 1 + 2 * (before + after)
        dst = action.dst
        assert dst is not None
        if occ[src] != 2 or occ[dst] == 2:
            return None
        occ[src] -= 1
        occ[dst] += 1
        mask = self._settle_column(occ, mask, src % self.cols)
        mask = self._settle_column(occ, mask, dst % self.cols)
        return self.encode(occ, mask), 1

    def successors(self, state: int) -> Iterator[tuple[int, int, int]]:
        """Yields (new_state, action_id, cost)."""
        occ, mask = self.decode(state)
        for i, v in enumerate(occ):
            if v and (i >= self.vertical_edges or not (mask & (1 << i))):
                out = self.step(state, self.down_ids[i])
                if out is not None:
                    nxt, cost = out
                    yield nxt, self.down_ids[i], cost
        for action in self.actions[self.n:]:
            if occ[action.src] == 2 and occ[action.dst] != 2:  # type: ignore[index]
                out = self.step(state, action.id)
                if out is not None:
                    nxt, cost = out
                    yield nxt, action.id, cost

    def trace(self, initial: int, actions: list[int] | tuple[int, ...]) -> list[dict]:
        out = [{'state': initial, 'action': None, 'step_cost': 0, 'total_cost': 0}]
        total = 0
        state = initial
        for action_id in actions:
            step = self.step(state, action_id)
            if step is None:
                raise ValueError(f'Action {action_id} invalid at state {state}')
            state, cost = step
            total += cost
            out.append({'state': state, 'action': action_id, 'step_cost': cost,
                        'total_cost': total})
        return out

    def cell_string(self, state: int, full_is_one: bool = False) -> str:
        g = self.to_display(state, 'full-is-1' if full_is_one else 'empty-is-1')
        return '\n'.join(' '.join(f'{v:g}' for v in row) for row in g)
