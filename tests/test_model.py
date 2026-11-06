from sandgrid import SandGrid, greedy, search, heuristic
from sandgrid.batch import compute_all_optimal, reconstruct_optimal
from sandgrid.visualize import save_html, save_gif


def test_display_conventions():
    m = SandGrid(2, 2)
    s = m.from_display([[0, .5], [1, 0]], 'empty-is-1')
    assert m.decode(s)[0] == [2, 1, 0, 2]
    assert m.to_display(s) == [[0, .5], [1, 0]]
    t = m.from_display([[1, .5], [0, 1]], 'full-is-1')
    assert s == t
    assert m.to_display(t, 'full-is-1') == [[1, .5], [0, 1]]


def test_costs_and_persistent_gates():
    m = SandGrid(2, 1)
    a = m.down_ids[0]
    b = m.down_ids[1]
    # Full upper into empty lower: empties upper, cost 5.
    state = m.encode([2, 0])
    nxt, cost = m.step(state, a)
    assert (cost, m.decode(nxt)) == (5, ([0, 2], 0))
    # Half into empty lower: cost 3.
    nxt, cost = m.step(m.encode([1, 0]), a)
    assert (cost, m.decode(nxt)) == (3, ([0, 1], 0))
    # Full into half: upper half / lower full, cost 7, gate remains open.
    nxt, cost = m.step(m.encode([2, 1]), a)
    assert (cost, m.decode(nxt)) == (7, ([1, 2], 1))
    assert m.step(nxt, a) is None
    # Opening a jammed gate is useful: full/full costs 9 and connects cells.
    jammed, cost = m.step(m.encode([2, 2]), a)
    assert (cost, m.decode(jammed)) == (9, ([2, 2], 1))
    # Drain both connected cells in ONE opening.
    drained, cost = m.step(jammed, b)
    assert (drained, cost) == (0, 5)


def test_professor_example_baseline():
    m = SandGrid(4, 2)
    initial = m.from_display([[1, 0], [0, 1], [0, 1], [1, 0]], 'full-is-1')
    g = greedy(m, initial)
    assert g.found and g.cost == 47
    assert len(g.actions) == 7
    assert all(m.actions[a].kind == 'down' for a in g.actions)
    assert [x['step_cost'] for x in m.trace(initial, g.actions)[1:]] == [5, 5, 9, 5, 9, 9, 5]
    u = search(m, initial, 'ucs')
    a = search(m, initial, 'astar')
    assert (u.cost, a.cost) == (34, 34)
    assert all(m.is_goal(m.trace(initial, path.actions)[-1]['state'])
               for path in (g, u, a))


def test_successors_invariants_and_costs():
    m = SandGrid(2, 2)
    for initial in range(m.base):
        assert m.valid_mask(*m.decode(initial))
        for nxt, a, cost in m.successors(initial):
            assert 1 <= cost <= 9
            assert m.valid_mask(*m.decode(nxt))
            assert (nxt, cost) == m.step(initial, a)


def test_exhaustive_2x2_and_admissible_heuristic():
    m = SandGrid(2, 2)
    batch = compute_all_optimal(m, progress=False)
    for state in batch['states']:
        idx = batch['state_index'][state]
        assert heuristic(m, state) <= int(batch['distances'][idx])
    for initial in range(m.base):
        opt = int(batch['distances'][batch['state_index'][initial]])
        u = search(m, initial, 'ucs')
        a = search(m, initial, 'astar')
        assert u.found and a.found
        assert u.cost == a.cost == opt
        if initial % 13 == 0:
            path = reconstruct_optimal(batch, initial)
            assert m.trace(initial, path)[-1]['total_cost'] == opt


def test_bfs_min_actions_2x2():
    m = SandGrid(2, 2)
    # On this small grid, IDS and BFS must find equal minimum action counts.
    for initial in (0, 7, 25, 36, 59, 80):
        bfs = search(m, initial, 'bfs')
        ids = search(m, initial, 'ids', max_depth=12)
        assert bfs.found and ids.found
        assert bfs.action_count == ids.action_count


def test_random_grid_distribution():
    m = SandGrid(5, 2)
    values = [cell for seed in range(200) for cell in m.decode(m.random_state(seed))[0]]
    frac_empty = values.count(0) / len(values)
    assert 0.45 <= frac_empty <= 0.55


def test_html_animation(tmp_path):
    m = SandGrid(2, 2)
    initial = m.encode([2, 0, 0, 2])
    path = save_html(m, initial, greedy(m, initial).actions, tmp_path/'demo.html')
    text = path.read_text(encoding='utf-8')
    assert '<canvas' in text and 'Gate (1,1)' in text
    assert 'Number(' in text and 'Remaining sand' in text


def test_gif_animation(tmp_path):
    from PIL import Image
    m = SandGrid(2, 2)
    initial = m.encode([2, 0, 0, 2])
    result = greedy(m, initial)
    path = save_gif(m, initial, result.actions, tmp_path/'demo.gif', 150)
    with Image.open(path) as gif:
        assert gif.n_frames == len(result.actions)+1
