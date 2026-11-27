import json
import tempfile
import unittest
from pathlib import Path
from genetic_alg.benchmark_100 import add_metrics, summarize, sample_codes, export, verify_route, run_ga
from genetic_alg.core import GAConfig


def case(i, ga, ucs):
    return add_metrics(dict(case_id=i,initial_code=i,ga_found=ga is not None,ga_cost=ga,
        ucs_found=ucs is not None,optimum_cost=ucs,ga_seconds=.1,ucs_seconds=.2,
        ga_status='found' if ga is not None else 'not_found',ucs_status='found' if ucs is not None else 'timeout',
        ga_min_conflict=0 if ga is not None else 1,ga_cost_at_min_conflict=ga or 3))


class TestBenchmark100(unittest.TestCase):
    def test_sampling(self):
        class Model:
            base=6561
            def is_goal(self,x): return x==0
        codes=sample_codes(Model(),100,42)
        self.assertEqual(len(set(codes)),100)
        self.assertNotIn(0,codes)
        self.assertEqual(codes,sample_codes(Model(),100,42))

    def test_all_success(self):
        s=summarize([case(1,10,10),case(2,15,10)],2)
        self.assertEqual(s['ga_optimal_pct_of_ga_successes'],50)
        self.assertEqual(s['mean_ratio_all_cases'],1.25)
        self.assertEqual(s['mean_ratio_ga_successes'],1.25)

    def test_failure(self):
        s=summarize([case(1,10,10),case(2,None,10)],2)
        self.assertEqual(s['mean_ratio_all_cases_status'],'infinity')
        self.assertIsNone(s['mean_ratio_all_cases'])
        self.assertEqual(s['mean_ratio_ga_successes'],1)
        self.assertEqual(s['ga_optimal_pct_of_all_cases'],50)
        self.assertEqual(s['ga_optimal_pct_of_ga_successes'],100)

    def test_missing_reference(self):
        s=summarize([case(1,10,10),case(2,12,None)],2)
        self.assertEqual(s['mean_ratio_all_cases_status'],'reference_unresolved')
        self.assertIsNone(s['mean_ratio_ga_successes'])
        self.assertIsNone(s['ga_optimal_pct_of_ga_successes'])
        self.assertEqual(s['observed_paired_mean_ratio'],1)

    def test_no_success(self):
        s=summarize([case(1,None,10)],1)
        self.assertEqual(s['mean_ratio_ga_successes_status'],'no_ga_success')
        self.assertIsNone(s['mean_ratio_ga_successes'])
        self.assertIsNone(s['ga_optimal_pct_of_ga_successes'])

    def test_incomplete(self):
        s=summarize([case(1,10,10)],100)
        self.assertFalse(s['benchmark_complete'])
        self.assertEqual(s['mean_ratio_all_cases_status'],'incomplete_run')

    def test_impossible_cost(self):
        with self.assertRaises(RuntimeError): case(1,9,10)

    def test_export(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            export(out,[case(1,10,10),case(2,None,10)],2)
            self.assertEqual(json.loads((out/'summary.json').read_text())['mean_ratio_all_cases_status'],'infinity')
            self.assertIn('infinite_ga_failure',(out/'comparison.csv').read_text(encoding='utf-8-sig'))
            self.assertIn('GA failed',(out/'dashboard.html').read_text())

    def test_reference_adapter(self):
        import sys
        from types import ModuleType, SimpleNamespace
        from unittest.mock import patch
        from test_genetic import TinyGrid
        from genetic_alg.benchmark_100 import run_reference
        package=ModuleType('sandgrid'); package.__path__=[]
        search_module=ModuleType('sandgrid.search')
        calls=[]
        def search(model, initial, algorithm, **kwargs):
            calls.append((initial,algorithm,kwargs))
            return SimpleNamespace(found=True,status='found',cost=6,actions=[0,1],
                 elapsed_sec=.1,expanded=3,generated=4,max_frontier=2)
        search_module.search=search
        with patch.dict(sys.modules,{'sandgrid':package,'sandgrid.search':search_module}):
            row=run_reference(TinyGrid(),3,seconds=10,expansions=100)
        self.assertEqual(row['optimum_cost'],6)
        self.assertEqual(calls[0][1],'ucs')
        self.assertEqual(calls[0][2]['max_seconds'],10)

    def test_actual_ga_on_toy(self):
        from test_genetic import TinyGrid
        cfg=GAConfig(population_size=10,chromosome_length=10,generations=3)
        row=run_ga(TinyGrid(),3,cfg,1)
        self.assertTrue(row['ga_found'])
        self.assertEqual(row['ga_cost'],6)
        self.assertTrue(0<=row['ga_mean_valid_fraction']<=1)

if __name__=='__main__': unittest.main()
