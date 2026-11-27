"""Paired GA/UCS benchmark for the third AI exercise.
Run from the repository root: python -m genetic_alg.benchmark_100
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, replace
from html import escape
import json
from pathlib import Path
from random import Random
from statistics import fmean, median

from .core import GAConfig
from .experiments import ga_run
from .fitness import evaluate_sequence


def sample_codes(model, count: int, seed: int) -> list[int]:
    # As in the existing benchmark, codes below base represent closed-gate grids.
    candidates = [code for code in range(model.base) if not model.is_goal(code)]
    if not 1 <= count <= len(candidates):
        raise ValueError(f"count must be between 1 and {len(candidates)}")
    return Random(seed).sample(candidates, count)


def verify_route(model, code, actions, cost):
    ev = evaluate_sequence(model, code, actions)
    if not ev.valid or not ev.solved or ev.path_cost != cost:
        raise RuntimeError(f"Invalid goal route or mismatched cost for grid {code}")
    if cost <= 0:
        raise RuntimeError(f"Nonpositive goal cost for non-goal grid {code}")


def run_reference(model, code, *, seconds, expansions):
    # Reuse the original UCS, with a deliberately nonbinding depth ceiling.
    # A time/expansion-limited unsuccessful search is never an optimum.
    from sandgrid.search import search
    depth = 1_000_000_000
    result = search(model, code, "ucs", max_seconds=seconds,
                    max_expansions=expansions, max_depth=depth,
                    random_seed=0, measure_memory=False)
    found = bool(result.found)
    cost = result.cost if found else None
    actions = list(result.actions) if found else []
    if found:
        verify_route(model, code, actions, cost)
    return dict(ucs_found=found, ucs_status=result.status, optimum_cost=cost,
                ucs_actions=actions, ucs_action_count=len(actions) if found else None,
                ucs_seconds=result.elapsed_sec, ucs_expanded=result.expanded,
                ucs_generated=result.generated, ucs_max_frontier=result.max_frontier,
                ucs_limit_seconds=seconds, ucs_limit_expansions=expansions,
                ucs_max_depth=depth)


def run_ga(model, code, cfg, case_id):
    row, history, result = ga_run(model, code, cfg, run_id=case_id)
    if result.found:
        verify_route(model, code, result.actions, result.cost)
    return dict(ga_found=bool(result.found), ga_status=result.status,
                ga_cost=result.cost if result.found else None,
                ga_actions=list(result.actions), ga_action_count=result.action_count if result.found else None,
                ga_min_conflict=result.best_min_conflict,
                ga_cost_at_min_conflict=result.best_cost_at_min_conflict,
                ga_fitness=result.fitness, ga_seconds=result.elapsed_sec,
                ga_generations=result.generations_completed,
                ga_evaluations=result.evaluations, ga_unique_evaluations=result.unique_evaluations,
                mutation_trials=row.get('mutation_trials'), lethal_mutations=row.get('lethal_mutations'),
                mutation_fallbacks=row.get('mutation_fallbacks'),
                ga_mean_valid_fraction=fmean(h['valid_count'] / cfg.population_size for h in history),
                ga_seed=cfg.seed)


def add_metrics(row):
    row = dict(row)
    row['ratio'] = None
    row['ga_optimal'] = None
    if row['ucs_found']:
        if row['optimum_cost'] is None or row['optimum_cost'] <= 0:
            raise ValueError('UCS optimum must be positive')
        if row['ga_found']:
            if row['ga_cost'] < row['optimum_cost']:
                raise RuntimeError(f"GA cost below UCS cost: grid {row['initial_code']}; inspect reference implementation")
            row['ratio'] = row['ga_cost'] / row['optimum_cost']
            row['ga_optimal'] = row['ga_cost'] == row['optimum_cost']
            row['ratio_status'] = 'finite'
        else:
            row['ga_optimal'] = False
            row['ratio_status'] = 'infinite_ga_failure'
    else:
        row['ratio_status'] = 'reference_unresolved'
    return row


def summarize(rows, target):
    n = len(rows)
    solved = sum(r['ga_found'] for r in rows)
    refs = sum(r['ucs_found'] for r in rows)
    pairs = [r for r in rows if r['ratio'] is not None]
    optimal = sum(r['ga_optimal'] is True for r in rows)
    ratios = [r['ratio'] for r in pairs]
    all_done = n == target
    ref_complete = refs == target and all_done
    solved_refs_complete = len(pairs) == solved
    # The successful-only mean is exact only once every GA success has a reference.
    mean_solved = fmean(ratios) if all_done and solved_refs_complete and ratios else None
    mean_all = None
    if not all_done:
        all_status = 'incomplete_run'
    elif not ref_complete:
        all_status = 'reference_unresolved'
    elif solved < target:
        all_status = 'infinity'
    else:
        all_status = 'finite'
        mean_all = fmean(ratios)
    def pct(a,b): return 100*a/b if b else None
    return dict(target_cases=target, completed_cases=n, benchmark_complete=all_done,
                ga_solved=solved, ga_failed=n-solved, ga_success_pct=pct(solved,n),
                ucs_solved=refs, ucs_unresolved=n-refs, paired_solved=len(pairs),
                ga_optimal_count=optimal, ga_optimal_pct_of_ga_successes=pct(optimal,solved) if all_done and solved_refs_complete else None,
                ga_optimal_pct_of_all_cases=pct(optimal,target) if all_done and solved_refs_complete else None,
                mean_ratio_all_cases=mean_all, mean_ratio_all_cases_status=all_status,
                mean_ratio_ga_successes=mean_solved,
                mean_ratio_ga_successes_status=('incomplete_run' if not all_done else 'no_ga_success' if not solved else 'reference_unresolved' if not solved_refs_complete else 'finite'),
                observed_paired_mean_ratio=fmean(ratios) if ratios else None,
                observed_paired_optimal_pct=pct(optimal,len(pairs)),
                ga_median_seconds=median([r['ga_seconds'] for r in rows]) if rows else None,
                ucs_median_seconds=median([r['ucs_seconds'] for r in rows]) if rows else None,
                failure_convention='A GA failure has +infinity goal cost; missing UCS optimum is unresolved, never zero. JSON null accompanied by status.',
                sampling='Uniform without replacement over non-goal initial codes in range(model.base); initial gates closed.')


def atomic_text(path, text):
    temp = path.with_name(path.name+'.tmp')
    temp.write_text(text, encoding='utf-8')
    temp.replace(path)


def dump_json(path, obj):
    atomic_text(path, json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False))


def write_csv(path, rows):
    if not rows:
        return
    temp = path.with_name(path.name+'.tmp')
    with temp.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    temp.replace(path)


def dashboard(path, rows, s):
    # Self-contained HTML: no network, JavaScript libraries or extra dependencies.
    def val(v):
        if v is None: return 'N/A'
        if isinstance(v,float): return f'{v:.4f}'
        return str(v)
    def ratio_text(key):
        status=s[key+'_status']
        return '∞ (GA failed)' if status=='infinity' else val(s[key]) if status=='finite' else status.replace('_',' ')
    tiles=[('GA solved',f"{s['ga_solved']} / {s['completed_cases']}"),('UCS solved',f"{s['ucs_solved']} / {s['completed_cases']}"),
           ('GA optimal / GA solved',val(s['ga_optimal_pct_of_ga_successes'])+'%'),('Mean ratio: all cases',ratio_text('mean_ratio_all_cases')),
           ('Mean ratio: GA solved',ratio_text('mean_ratio_ga_successes'))]
    tile_html=''.join(f'<div class="tile"><b>{escape(v)}</b><small>{escape(k)}</small></div>' for k,v in tiles)
    known_opt=s['ga_optimal_count']; known_nonopt=s['paired_solved']-known_opt
    groups=[('Optimal GA',known_opt,'#26856b'),('Solved, nonoptimal',known_nonopt,'#4676a9'),('Solved, reference unknown',s['ga_solved']-s['paired_solved'],'#c98b3c'),('GA failed',s['ga_failed'],'#aa5960')]
    bars=''.join(f'<div class="barrow"><span>{escape(label)}</span><div class="track"><div style="width:{100*count/max(1,s["target_cases"]):.3f}%;background:{color}"></div></div><b>{count}</b></div>' for label,count,color in groups)
    pts=[r for r in rows if r['ratio'] is not None]
    max_y=max([1.1]+[r['ratio'] for r in pts]); width=900; height=260
    circles=''.join(f'<circle cx="{55+800*(r["case_id"]-1)/max(1,s["target_cases"]-1):.2f}" cy="{215-180*(r["ratio"]-1)/(max_y-1):.2f}" r="4" fill="#4676a9"><title>Case {r["case_id"]}, grid {r["initial_code"]}, ratio {r["ratio"]:.4f}</title></circle>' for r in pts)
    plot=f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Cost ratio per solved paired case"><path d="M55 30V215H855" fill="none" stroke="#64748b"/><text x="12" y="40">{max_y:.2f}</text><text x="22" y="219">1.0</text><text x="55" y="240">1</text><text x="830" y="240">{s["target_cases"]}</text>{circles}</svg>'
    keys=['case_id','initial_code','ga_status','ga_cost','ucs_status','optimum_cost','ratio','ratio_status','ga_min_conflict','ga_cost_at_min_conflict','ga_seconds','ucs_seconds']
    th=''.join(f'<th>{escape(k)}</th>' for k in keys)
    tr=''.join('<tr>'+''.join(f'<td>{escape(val(r[k]))}</td>' for k in keys)+'</tr>' for r in rows)
    atomic_text(path,f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>SandGrid · 100-case GA vs UCS benchmark</title><style>body{{font:15px system-ui;color:#24364a;background:#f6f8fb;margin:30px auto;max-width:1200px;padding:0 20px}}.tiles{{display:flex;flex-wrap:wrap;gap:12px}}.tile,section{{background:white;border:1px solid #d9e1eb;border-radius:10px;padding:18px;margin:12px 0}}.tile{{flex:1;min-width:150px}}.tile b{{font-size:24px;display:block}}small{{color:#526579}}.barrow{{display:grid;grid-template-columns:220px 1fr 40px;gap:12px;align-items:center;margin:10px 0}}.track{{background:#eaf0f6;height:18px}}.track div{{height:18px}}svg{{width:100%;max-width:900px}}table{{border-collapse:collapse;width:100%;white-space:nowrap}}th,td{{padding:8px;border-bottom:1px solid #e1e8ef;text-align:left}}.scroll{{overflow:auto}}</style><h1>GA vs UCS · {s['completed_cases']}/{s['target_cases']} distinct initial grids</h1><div class="tiles">{tile_html}</div><section><h2>Solution outcomes</h2>{bars}<p>Only successful UCS references are treated as optimal. GA failure has infinite goal cost; unresolved references remain unknown.</p></section><section><h2>GA / optimum cost for paired successes</h2>{plot}<p>Each point is a solved GA case with a confirmed UCS reference. A ratio of 1 is optimal.</p></section><section class="scroll"><h2>Per-case results</h2><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></section></html>''')


def export(out, rows, target):
    rows = sorted((add_metrics(r) for r in rows), key=lambda r:r['case_id'])
    summary = summarize(rows,target)
    write_csv(out/'comparison.csv', rows)
    dump_json(out/'summary.json',summary)
    dashboard(out/'dashboard.html',rows,summary)
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rows',type=int,default=4); p.add_argument('--cols',type=int,default=2)
    p.add_argument('--count',type=int,default=100); p.add_argument('--seed',type=int,default=42)
    p.add_argument('--population',type=int,default=50); p.add_argument('--length',type=int,default=18)
    p.add_argument('--generations',type=int,default=100); p.add_argument('--cost-transform',choices=['log','linear','sqrt'],default='log')
    p.add_argument('--ucs-seconds',type=float,default=120); p.add_argument('--ucs-expansions',type=int,default=2_000_000)
    p.add_argument('--output',default='genetic_alg/results/benchmark_100')
    p.add_argument('--resume',action='store_true',help='Resume exactly the same sampled grids and GA configuration')
    p.add_argument('--retry-reference',action='store_true',help='With --resume, retry unresolved UCS references with the supplied limits; do not rerun GA')
    a=p.parse_args(argv)
    if a.ucs_seconds<=0 or a.ucs_expansions<1: p.error('UCS limits must be positive')
    if a.retry_reference and not a.resume: p.error('--retry-reference requires --resume')
    from sandgrid.model import SandGrid
    model=SandGrid(a.rows,a.cols)
    cfg=GAConfig(population_size=a.population,chromosome_length=a.length,generations=a.generations,
                 seed=a.seed,cost_transform=a.cost_transform,evolution_mode='classroom',mutation_attempts=10)
    codes=sample_codes(model,a.count,a.seed)
    settings=dict(model_version=model.MODEL_VERSION,rows=a.rows,cols=a.cols,count=a.count,
                  sampling_seed=a.seed,initial_codes=codes,ga_config=asdict(cfg),
                  ga_seed_rule='sampling_seed + 1000 * case_id',reference='original sandgrid UCS')
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    checkpoint=out/'checkpoint.json'
    if checkpoint.exists():
        if not a.resume: p.error('Output already contains a benchmark; use --resume or another --output')
        saved=json.loads(checkpoint.read_text(encoding='utf-8'))
        if saved['settings']!=settings: p.error('Sampling/model/GA config differs from checkpoint; choose another --output')
        records={r['case_id']:r for r in saved['records']}
    else:
        if a.resume: p.error('No checkpoint found in output folder')
        records={}
    dump_json(out/'experiment_config.json',settings)
    def save():
        dump_json(checkpoint,dict(settings=settings,records=list(records.values())))
        return export(out,list(records.values()),a.count)
    save()
    for case_id,code in enumerate(codes,1):
        if case_id in records:
            row=records[case_id]
            if not a.retry_reference or row['ucs_found']: continue
            row={**row,**run_reference(model,code,seconds=a.ucs_seconds,expansions=a.ucs_expansions)}
        else:
            # Fixed GA budget, no access to the UCS optimum or target cost.
            ga=run_ga(model,code,replace(cfg,seed=a.seed+1000*case_id),case_id)
            ref=run_reference(model,code,seconds=a.ucs_seconds,expansions=a.ucs_expansions)
            row=dict(case_id=case_id,initial_code=code,initial_grid=model.to_display(code),**ga,**ref)
        add_metrics(row) # detect contradictions before checkpointing
        records[case_id]=row
        save()
        print(f"{case_id:3}/{a.count} grid={code:5} GA={row['ga_status']} cost={row['ga_cost']} conflict={row['ga_min_conflict']} UCS={row['ucs_status']} optimum={row['optimum_cost']}",flush=True)
    summary=save()
    print(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False))
    print('Results:',out.resolve())
    if summary['ucs_unresolved']:
        print('WARNING: some UCS references are unresolved; retry using --resume --retry-reference with higher limits.')


if __name__=='__main__':
    main()
