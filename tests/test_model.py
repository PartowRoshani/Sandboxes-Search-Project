"""Regression tests for continuous sand flow and persistent blocked gates."""
from collections import deque

from sandgrid.model import SandGrid
from sandgrid.search import greedy


def test_default_display_convention_full_is_one():
    m = SandGrid(2, 2)
    source = [[1, 0], [0.5, 1]]
    state = m.from_display(source)
    assert m.decode(state) == ([2, 0, 1, 2], 0)
    assert m.to_display(state) == source
    assert m.from_display([[0,1],[0.5,0]], 'empty-is-1') == state


def test_professor_columnwise_greedy_47_cost_7_openings():
    m = SandGrid(4, 2)
    initial = m.from_display([[1,0],[0,1],[0,1],[1,0]])
    result = greedy(m, initial)
    assert result.found
    assert result.cost == 47
    assert result.actions == [m.down_ids[i] for i in (0,2,4,6,3,5,7)]
    assert [t['step_cost'] for t in m.trace(initial, result.actions)[1:]] == [5,5,9,5,9,9,5]
    assert all(m.actions[a].kind == 'down' for a in result.actions)
    assert m.trace(initial, result.actions)[-1]['state'] == 0


def test_blocked_vertical_gate_waits_and_exit_drains_continuously():
    m = SandGrid(2, 1)
    state = m.encode([2, 2])
    blocked, cost = m.step(state, m.down_ids[0])
    assert cost == 9
    assert m.decode(blocked) == ([2,2],1)
    assert m.step(blocked,m.down_ids[0]) is None
    trace = m.trace(blocked, [m.down_ids[1]])
    assert trace[-1]['state'] == 0
    assert trace[-1]['step_cost'] == 5
    assert [(e['kind'],e['amount']) for e in trace[-1]['flow_events']] == [
        ('exit',1.0),('down',1.0),('exit',1.0)]


def test_vertical_gate_stays_open_while_blocked_with_sand_upstream():
    m = SandGrid(2,1)
    result, cost = m.step(m.encode([2,1]),m.down_ids[0])
    assert cost == 7
    assert m.decode(result) == ([1,2],1)
    trace = m.trace(result,[m.down_ids[1]])
    assert trace[-1]['state'] == 0
    assert trace[-1]['step_cost'] == 5
    assert sum(e['kind']=='exit' for e in trace[-1]['flow_events']) == 2


def test_vertical_gate_closes_only_when_upstream_sand_exhausted():
    m = SandGrid(2,1)
    result, cost = m.step(m.encode([2,0]),m.down_ids[0])
    assert (m.decode(result),cost) == (([0,2],0),5)


def test_horizontal_passage_one_half_then_closes():
    m = SandGrid(1,2)
    result,cost = m.step(m.encode([2,0]),m.side_ids[(0,1)])
    assert cost==1 and m.decode(result)==([1,1],0)


def test_horizontal_gate_blocked_then_automatically_passes_half_unit():
    m = SandGrid(1,2)
    blocked,cost=m.step(m.encode([2,2]),m.side_ids[(0,1)])
    assert cost==1
    assert m.decode(blocked)[1]==(1 << m.gate_bit(m.side_ids[(0,1)]))
    trace=m.trace(blocked,[m.down_ids[1]])[-1]
    assert m.decode(trace['state'])==([1,0],0)
    assert trace['step_cost']==5
    assert [(e['kind'],e['amount']) for e in trace['flow_events']]==[
        ('exit',1.0),('side',0.5),('exit',0.5)]
    assert trace['flow_events'][1]['automatic'] is True


def test_horizontal_opens_only_from_full_source():
    m=SandGrid(1,2)
    assert m.step(m.encode([1,0]),m.side_ids[(0,1)]) is None
    assert m.step(m.encode([0,0]),m.side_ids[(0,1)]) is None


def test_cascade_carries_sand_to_exit_through_two_vertical_gates():
    m=SandGrid(3,1)
    state=m.encode([2,2,2])
    state,_=m.step(state,m.down_ids[0])
    state,_=m.step(state,m.down_ids[1])
    assert m.decode(state)==([2,2,2],3)
    action=m.trace(state,[m.down_ids[2]])[-1]
    assert action['state']==0 and action['step_cost']==5
    assert len([e for e in action['flow_events'] if e['kind']=='exit'])==3
    assert len([e for e in action['flow_events'] if e['kind']=='down'])==3


def test_horizontal_half_full_destination_moves_half():
    m=SandGrid(1,2)
    state,cost=m.step(m.encode([2,1]),m.side_ids[(0,1)])
    assert cost==1 and m.decode(state)==([1,2],0)


def test_gate_mask_validity_and_open_status():
    m=SandGrid(2,1)
    assert m.valid_mask([2,2],1)
    assert not m.valid_mask([1,1],1)
    assert not m.valid_mask([0,2],1)
    assert m.encode([0,0],0)==0


def test_all_initial_2x2_states_reach_goal_and_costs_valid():
    m=SandGrid(2,2)
    seen_all=set()
    for initial in range(m.base):
        seen={initial};q=deque([initial]);reached=initial==0
        while q:
            state=q.popleft()
            old,_=m.decode(state)
            for nxt,action,cost in m.successors(state):
                new,mask=m.decode(nxt)
                assert m.valid_mask(new,mask)
                assert 1 <= cost <= 9
                assert sum(new) <= sum(old)
                assert m.step(state,action)==(nxt,cost)
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
                reached |= nxt==0
        assert reached, f'goal not reachable from initial {initial}'
        seen_all.update(seen)
    assert len(seen_all)>200


def test_greedy_never_uses_horizontal_gate_for_all_2x2_grids():
    m=SandGrid(2,2)
    for initial in range(m.base):
        result=greedy(m,initial)
        assert result.found
        assert all(m.actions[a].kind == 'down' for a in result.actions)
        assert m.trace(initial,result.actions)[-1]['total_cost']==result.cost
