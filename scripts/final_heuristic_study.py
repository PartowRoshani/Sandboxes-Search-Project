#!/usr/bin/env python3
"""Repeat the 3x2 ML + search experiment across independent train/test splits.

Each seed retrains the model with its own occupancy-group holdout. Search
results are benchmarked on closed-gate initial codes from THAT held-out split.
A separate final CSV and Persian report are generated after all seeds finish.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean, median, pstdev
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from scripts.compare_heuristics import METHODS, run_benchmark
from sandgrid.model import SandGrid


def csv_write(path: Path, records: list[dict]):
    if not records:
        raise ValueError(f'No records for {path}')
    with path.open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def fmt(value, digits=3):
    return '—' if value is None else f'{value:.{digits}f}'


def generate_report(output: Path, args, training: list[dict],
                    aggregated: list[dict], seed_summaries: list[dict]):
    model = SandGrid(3, 2)
    text = [
        '# گزارش آزمایش Heuristic و Machine Learning — مسئله شن', '',
        '## ۱. مبنای مسئله',
        '',
        f'- نسخه مدل: `{model.MODEL_VERSION}`.',
        '- قرارداد خانه‌ها: `1=پر`، `0.5=نیمه‌پر` و `0=خالی`.',
        '- هدف: تخلیه کامل شبکه با کمینه کردن مجموع هزینه اعمال.',
        '- Greedy استاد، تخلیه ستون‌به‌ستون و فقط با دریچه‌های عمودی است؛ '
        'Greedy Best-First Search نیست.',
        '- مثال استاد: هزینه Greedy برابر ۴۷ با ۷ عمل و هزینه بهینه UCS/A* برابر ۳۴.',
        '',
        '## ۲. طراحی Heuristic مبتنی بر Relaxation', '',
        r'\[ h_{\mathrm{relax}}(s)=E(s)+\sum_{r=1}^{R-1}L_r(s) \]', '',
        r'در این تعریف، \(E(s)\) حداقل هزینه خروج شن از پایین شبکه است: '
        'برای نیم‌واحد باقی‌مانده ۳، برای مقدار بیشتر ۵ و برای هدف صفر. '
        'هر مرز ردیفی با شن بالای آن، اگر هیچ دریچه عمودی بازی نداشته باشد '
        'حداقل سهم ۳ (نیم‌واحد) یا ۵ (حداقل یک واحد) دارد. در غیر این صورت سهمش صفر است.',
        '',
        '**دلیل مجاز بودن:** برای تخلیه کامل، شن بالای هر مرز ناچار است از آن عبور کند. '
        'اگر آن مرز دریچه عمودی باز ندارد، دست‌کم یک باز کردن دریچه لازم است؛ '
        'در تخمین، ارزان‌ترین هزینه اجتناب‌ناپذیر آن عمل را در نظر می‌گیریم. '
        'عمل باز کردن دریچه هر مرز از اعمال مرزهای دیگر و اعمال خروجی جداست. '
        'هزینه حرکت افقی و باز کردن‌های اضافه را حذف می‌کنیم. '
        'ازاین‌رو، طبق قوانین هزینه نسخه فعلی مدل، مجموع این کران‌ها از هزینه بهینه '
        'بیشتر نمی‌شود. این استدلال باید با فرض جریان پیوسته همین مدل خوانده شود.',
        '',
        'روی مدل ۳×۲، Admissibility و Consistency با آزمون جامع وضعیت‌های پایدار '
        'بررسی می‌شوند. آزمون محدود، جای اثبات برای همه ابعاد شبکه نیست.',
        '',
        '## ۳. آموزش یادگیری ماشین', '',
        r'هدف رگرسیون، پیش‌بینی \(h^*(s)\) یعنی هزینه بهینه باقی‌مانده است. '
        'برچسب‌ها از Reverse Dijkstra روی تمام وضعیت‌های پایدار ۳×۲ استخراج شدند. '
        'ویژگی‌ها عبارت‌اند از: اشغال هر خانه، بیت دریچه‌های باز، مجموع شن هر ردیف '
        'و مجموع شن شبکه. مدل RandomForestRegressor استفاده شد.',
        '',
        'آرایش‌های شن با GroupShuffleSplit به آموزش و آزمون تقسیم شدند؛ '
        'همه ماسک‌های دریچه متعلق به یک آرایش شن در یک گروه هستند.',
        '',
        '| Seed آموزش | Train states | Test states | MAE | RMSE | R² | درصد بیش‌برآورد |',
        '|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for r in training:
        text.append(f"| {r['seed']} | {r['train_states']} | {r['test_states']} | "
                    f"{r['mae']:.4f} | {r['rmse']:.4f} | {r['r2']:.4f} | "
                    f"{100*r['overestimate_fraction']:.2f}٪ |")
    text += [
        '',
        '**محدودیت داده:** وضعیت اولیه هر آزمایش از آرایش‌های آزمون انتخاب شده، '
        'اما حالت‌های میانی که طی جست‌وجو ایجاد می‌شوند ممکن است از آرایش‌های '
        'موجود در آموزش باشند. پس این آزمایش تعمیم روی ورودی اولیه ندیده را '
        'می‌سنجد، نه لزوماً روی تک‌تک حالت‌های میانی ندیده.',
        '',
        '## ۴. طراحی مقایسه جست‌وجو', '',
        f'- Seedهای مستقل آموزش/تقسیم: `{", ".join(str(s) for s in args.seeds)}`.',
        f'- حداکثر {args.count} شبکه اولیه آزمون برای هر Seed، '
        f'{args.repeats} تکرار برای هر شبکه و روش.',
        f'- محدودیت اجرا: {args.seconds:g} ثانیه و {args.expansions:,} گسترش.',
        '- بارگذاری مدل و زمان آموزش خارج از زمان جست‌وجو هستند؛ '
        'پیش‌بینی ML در زمان جست‌وجو حساب می‌شود.',
        '- پیش‌بینی‌های تکراری در یک جست‌وجو کش و پیش‌بینی وضعیت‌های جدید '
        'در هر گسترش دسته‌ای محاسبه می‌شود. کش بین اجراهای مستقل منتقل نمی‌شود.',
        '- UCS مرجع هزینه بهینه است؛ برای مسئله‌های Timeout شکاف هزینه ثبت نمی‌شود.',
        '- ML Direct بهینگی تضمین‌شده ندارد؛ ML Safe Tie از g+h_relax به‌عنوان '
        'کلید اصلی و ML فقط برای شکستن تساوی استفاده می‌کند.',
        '',
        '## ۵. نتایج تجمیعی', '',
        '| روش | اجرا | حل‌شده | بهینه / قابل‌مقایسه | میانگین Expanded | '
        'میانگین زمان (ثانیه) | میانگین شکاف هزینه |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for r in aggregated:
        text.append(f"| {r['method']} | {r['attempts']} | {r['solved']} | "
                    f"{r['optimal_count']}/{r['comparable']} | "
                    f"{fmt(r['mean_expanded'],2)} | {fmt(r['mean_seconds'],6)} | "
                    f"{fmt(r['mean_gap'],3)} |")
    text += [
        '',
        'برای تفسیر میانگین زمان، علاوه بر `summary_all_seeds.csv` '
        'می‌توان نتایج هر Seed را در `summary_by_seed.csv` مشاهده کرد. '
        'زمان اجرا تحت تأثیر سخت‌افزار، بار سیستم و سربار استنتاج ML است.',
        '',
        '![مقایسه حالت‌های گسترش‌یافته](expanded_all_seeds.png)',
        '',
        '![مقایسه زمان](runtime_all_seeds.png)',
        '',
        '![سهم جواب‌های بهینه](optimality_all_seeds.png)',
        '',
        '## ۶. تحلیل و نتیجه', '',
    ]
    relax = next(r for r in aggregated if r['method'] == 'A* relax')
    basic = next(r for r in aggregated if r['method'] == 'A* basic')
    ml = next(r for r in aggregated if r['method'] == 'A* ML direct')
    tie = next(r for r in aggregated if r['method'] == 'A* ML safe tie')
    if basic['mean_expanded'] > 0:
        reduction = 100 * (basic['mean_expanded'] - relax['mean_expanded']) / basic['mean_expanded']
        text.append(f'- Relaxation نسبت به Basic در این مجموعه آزمایش '
                    f'{reduction:.1f}٪ حالت کمتر گسترش داده است.')
    text.append(f"- ML Direct در {ml['optimal_count']} مورد از {ml['comparable']} "
                'اجرای قابل‌مقایسه هزینه بهینه را پیدا کرده است؛ '
                'این نسبت یک تضمین نظری برای مدل یادگیری نیست.')
    text.append(f"- ML Safe Tie در {tie['optimal_count']} مورد از {tie['comparable']} "
                'اجرای قابل‌مقایسه به هزینه UCS رسیده است؛ '
                'تضمین نظری آن از Heuristic Relaxation و استفاده از ML صرفاً '
                'در شکستن تساوی‌ها ناشی می‌شود.')
    text += [
        '- نتایج شبکه ۳×۲، برای شبکه‌های بزرگ‌تر بدون آموزش و آزمون جدا '
        'قابل تعمیم قطعی نیستند.',
        '- اگر حافظه اندازه‌گیری نشده باشد، نباید برای آن عدد در گزارش نوشت.',
        *(['- این اجرا با tracemalloc انجام شد؛ زمان جست‌وجو شامل سربار '
           'اندازه‌گیری حافظه است. نمودار memory_all_seeds.png نیز تولید شد.']
          if args.measure_memory else []),
        '',
        '## ۷. فایل‌های بازتولید آزمایش', '',
        '- `training_metrics.csv`: کیفیت رگرسیون برای Seedهای مختلف.',
        '- `comparison_all_seeds.csv`: تمام اجراهای جست‌وجو.',
        '- `summary_all_seeds.csv` و `summary_by_seed.csv`: خلاصه نتایج.',
        '- `seed_*/training/dataset_split.json`: فهرست گروه‌های آموزش و آزمون.',
        '- `seed_*/comparison/experiment.json`: تنظیمات هر مقایسه.',
        '',
    ]
    (output / 'REPORT_FA.md').write_text('\n'.join(text), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Reproducible multi-seed heuristic experiment')
    parser.add_argument('--seeds', default='42,43,44', help='Comma-separated train/test split seeds')
    parser.add_argument('--count', type=int, default=20)
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--trees', type=int, default=30)
    parser.add_argument('--seconds', type=float, default=20)
    parser.add_argument('--expansions', type=int, default=100_000)
    parser.add_argument('--output', type=Path, default=Path('results/final_heuristics'))
    parser.add_argument('--measure-memory', action='store_true',
                        help='Enable tracemalloc; timing then includes its profiling overhead')
    args = parser.parse_args()
    try:
        args.seeds = list(dict.fromkeys(int(s.strip()) for s in args.seeds.split(',')))
    except ValueError:
        parser.error('seeds must be comma-separated integers')
    if not args.seeds or min(args.count, args.repeats, args.trees, args.expansions) < 1 \
            or args.seconds <= 0:
        parser.error('seeds required, positive count/repeats/trees/expansions/seconds')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    all_rows, seed_summaries, training = [], [], []
    for seed in args.seeds:
        directory = output / f'seed_{seed}'
        train_dir = directory / 'training'
        compare_dir = directory / 'comparison'
        train_dir.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, str(ROOT / 'scripts' / 'train_ml_heuristic.py'),
                   '--rows', '3', '--cols', '2', '--seed', str(seed),
                   '--trees', str(args.trees), '--output', str(train_dir)]
        print(f'\n=== Training ML (split seed={seed}) ===', flush=True)
        # Never silently reuse a model trained under different settings.
        subprocess.run(command, cwd=ROOT, check=True)
        metrics = json.loads((train_dir / 'metrics.json').read_text(encoding='utf-8'))
        training.append(metrics)
        print(f'=== Benchmark held-out initial states (seed={seed}) ===', flush=True)
        summary, rows = run_benchmark(train_dir / 'heuristic_ml.joblib', compare_dir,
                                     args.count, seed + 1000, args.seconds,
                                     args.expansions, args.repeats, args.measure_memory)
        for row in rows:
            all_rows.append({'split_seed': seed, 'selection_seed': seed + 1000, **row})
        for row in summary:
            seed_summaries.append({'split_seed': seed, **row})
    csv_write(output / 'training_metrics.csv', training)
    csv_write(output / 'comparison_all_seeds.csv', all_rows)
    csv_write(output / 'summary_by_seed.csv', seed_summaries)
    aggregated = []
    for label, _, _ in METHODS:
        subset = [r for r in all_rows if r['method'] == label]
        solved = [r for r in subset if r['status'] == 'found']
        comparable = [r for r in solved if r['optimality_gap'] != '']
        by_seed = [r for r in seed_summaries if r['method'] == label]
        aggregated.append({
            'method': label, 'attempts': len(subset), 'solved': len(solved),
            'comparable': len(comparable),
            'optimal_count': sum(r['optimality_gap'] == 0 for r in comparable),
            'mean_expanded': round(mean(r['expanded'] for r in subset), 3),
            'mean_seconds': round(mean(r['elapsed_sec'] for r in subset), 7),
            'std_seed_mean_seconds': round(pstdev(r['mean_seconds_all_runs'] for r in by_seed), 7),
            'mean_gap': (round(mean(r['optimality_gap'] for r in comparable), 4)
                         if comparable else None),
            'median_python_peak_kib': (
                round(median(r['peak_python_bytes'] for r in subset) / 1024, 2)
                if args.measure_memory else None),
        })
    csv_write(output / 'summary_all_seeds.csv', aggregated)
    for filename, key, title, ylabel in [
        ('expanded_all_seeds.png', 'mean_expanded', 'Expanded states', 'Mean expanded states'),
        ('runtime_all_seeds.png', 'mean_seconds', 'Search duration', 'Mean seconds'),
        ('optimality_all_seeds.png', None, 'Optimal answers among comparable runs', 'Fraction'),
        *([('memory_all_seeds.png', 'median_python_peak_kib',
             'Python memory (tracemalloc)', 'Median peak KiB')]
          if args.measure_memory else []),
    ]:
        values = ([r[key] for r in aggregated] if key else
                  [r['optimal_count']/r['comparable'] if r['comparable'] else 0
                   for r in aggregated])
        fig, ax = plt.subplots(figsize=(10, 4.8))
        ax.bar([r['method'] for r in aggregated], values)
        ax.set(title=title, ylabel=ylabel)
        if key is None:
            ax.set_ylim(0, 1.03)
        ax.tick_params(axis='x', rotation=20)
        fig.tight_layout()
        fig.savefig(output / filename, dpi=170)
        plt.close(fig)
    generate_report(output, args, training, aggregated, seed_summaries)
    (output / 'configuration.json').write_text(json.dumps({
        'seeds': args.seeds, 'count': args.count, 'repeats': args.repeats,
        'trees': args.trees, 'seconds': args.seconds,
        'expansions': args.expansions, 'measure_memory': args.measure_memory,
        'model_version': SandGrid.MODEL_VERSION,
    }, indent=2), encoding='utf-8')
    print('\n=== FINAL RESULTS ===')
    print(json.dumps(aggregated, indent=2, ensure_ascii=False))
    print('Persian report:', output / 'REPORT_FA.md')


if __name__ == '__main__':
    main()
