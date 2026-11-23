# Genetic Algorithm — Sandboxes Search Project

## هدف تکلیف

در این بخش الگوریتم ژنتیک (Genetic Algorithm) را برای **نسخهٔ sand-only** پروژه پیاده‌سازی کرده‌ام. هدف، پیدا کردن **دنباله‌ای از اکشن‌های مجاز برای خالی کردن کامل شبکه** و سپس کاهش هزینهٔ وزنی این مسیر است. بر خلاف الگوریتم‌های Graph Search، کروموزوم ژنتیک یک وضعیت نهایی نیست؛ هر کروموزوم نمایندهٔ مسیر طی‌شده از یک وضعیت اولیهٔ ثابت است.

تمام کدهای این تکلیف در پوشهٔ `genetic_alg/` قرار دارند. فایل‌های `sandgrid/`، `main.py` و `run_project.py` تغییر نمی‌کنند. برای رعایت قوانین مسئله، فقط از API مدل اصلی (`SandGrid.step`, `successors`, `decode`, `is_goal` و `trace`) استفاده کرده‌ام. مدل اصلی نسخهٔ `continuous-flow-v2-full-is-1` است. به‌خصوص، هزینهٔ دروازه‌ها، جریان پیوسته و وضعیت دروازه‌های باز دوباره پیاده‌سازی نشده‌اند.

## ساختار فایل‌ها

```text
genetic_alg/
├── __init__.py           # توابع قابل import
├── __main__.py           # python -m genetic_alg
├── core.py               # Population، حلقهٔ نسل‌ها، Elitism، ثبت تاریخچه
├── fitness.py            # Goal test، Conflict، Fitness، هزینهٔ هر دنباله
├── operators.py          # Roulette selection، Crossover، Mutation
├── experiments.py        # اجرای آزمایش روی مدل قبلی، CSV و ذخیرهٔ مسیر
├── dashboard.py          # داشبورد HTML تعاملی و آفلاین
├── cli.py                # دستورات solve / compare / benchmark / study / dashboard
├── tests/
│   ├── test_genetic.py   # تست واحد با مدل کوچک مستقل
│   └── test_repository.py # تست یکپارچه روی مدل اصلی، در صورت دسترسی
├── requirements.txt      # Plotly برای داشبورد
├── run_all.sh            # اجرای سریع آزمایش‌ها در Git Bash
├── run_all.ps1           # اجرای سریع آزمایش‌ها در PowerShell
└── results/              # خروجی‌های واقعی قابل ثبت در Git همراه با داشبورد
```

**پوشه باید در ریشهٔ ریپازیتوری قرار بگیرد**، کنار `sandgrid/` و `main.py`. اجرای آن از ریشهٔ ریپازیتوری انجام می‌شود. این جداسازی در سطح کد برقرار است، اما برای استفاده از *قوانین یکسان مسئله* به پکیج `sandgrid` موجود وابسته است.

## نصب و تست

دستورات زیر را از ریشهٔ ریپازیتوری اجرا می‌کنم:

```bash
python -m pip install -r requirements.txt
python -m pip install -r genetic_alg/requirements.txt
python -m unittest discover -s genetic_alg/tests -v
```

تست‌های `test_genetic.py` بدون وابستگی به مدل قبلی قابل اجرا هستند. تست `test_repository.py` وقتی مدل اصلی در دسترس باشد، سناریوی معروف استاد (۴×۲) را با همان منطق پروژه بررسی می‌کند.

## نمایش جواب روی جدول استاد

جدول مورد آزمایش:

```text
1 0
0 1
0 1
1 0
```

طبق نسخهٔ فعلی README پروژه، **هزینهٔ Greedy برابر ۴۷ و هزینهٔ بهینهٔ UCS/A* برابر ۳۴** است. هدف GA پیدا کردن مسیر معتبر و کاهش هزینه است؛ رسیدن به مقدار ۳۴ در هر Seed تضمین نمی‌شود.

فقط Genetic Algorithm:

```bash
python -m genetic_alg solve --example professor --population 50 --length 50 --generations 1000 --seed 42 --output genetic_alg/results/professor_ga
```

مقایسهٔ Genetic و هشت الگوریتم قبلی، با محدودیت زمانی یکسان ۵ ثانیه برای الگوریتم‌های دارای محدودیت زمان و برای GA (Greedy بدون محدودیت است):

```bash
python -m genetic_alg compare --example professor --population 50 --length 50 --generations 1000 --repeats 5 --ga-seconds 5 --baseline-seconds 5 --seed 42 --output genetic_alg/results/professor_compare
```

برای توقف زودهنگام با رسیدن به مسیر دارای هزینهٔ حداکثر ۳۴ (فقط برای همین جدول، با ارجاع به هزینهٔ بهینهٔ شناخته‌شده):

```bash
python -m genetic_alg solve --example professor --target-cost 34 --generations 1000 --output genetic_alg/results/professor_target
```

اگر هدف بررسی همهٔ ۱۰۰۰ نسل باشد، از `--target-cost` استفاده نمی‌کنم. `--ga-seconds` نیز اگر تعیین نشود، محدودیت زمانی وجود ندارد.

## تعریف کروموزوم و ارزیابی

طول هر کروموزوم به‌صورت پیش‌فرض `n=50` است و می‌توان آن را با `--length 100` تغییر داد:

```text
chromosome = (action_id_1, action_id_2, ..., action_id_n)
```

هر `action_id` به یکی از اکشن‌های واقعی `SandGrid.actions` اشاره دارد. ابتدا برای تولید جمعیت اولیه، **Random Rollout** انجام می‌شود؛ یعنی اکشن‌های مجاز از `successors` با نمونه‌گیری تصادفی انتخاب می‌شوند. در صورت رسیدن به Goal پیش از پایان طول کروموزوم، بقیهٔ ژن‌ها صرفاً Padding هستند و **اجرا یا محاسبه نمی‌شوند**.

برای هر کروموزوم، مدل از **همان initial state** شروع می‌کند. اگر قبل از Goal به اکشن غیرمجاز برسیم، `fitness=0` می‌شود. اگر کروموزوم به Goal برسد، همان Prefix واقعی مسیر، هزینه و تعداد اکشن آن ثبت می‌شود. هیچ اکشن اضافی بعد از Goal اجرا نمی‌شود.

`goal_test(model, initial_state, sequence)` مستقیماً دنبالهٔ اکشن‌ها را بررسی می‌کند. `conflict_number` نیز دو حالت دارد:

- `occupied` (پیش‌فرض): تعداد خانه‌های دارای شن، با مقدار اشغال ۰٫۵ یا ۱.
- `half_units`: مجموع واحدهای نیمه‌شن باقی‌مانده، برای آزمایش فرمول جایگزین.

برای کروموزومی که به Goal نرسیده است، کمترین Conflict در **تمام حالات مسیر، از جمله Initial State** محاسبه می‌شود. `C*` هزینهٔ مسیر تا همان اولین نقطه با کمترین Conflict است (با هزینه‌های مثبت، همین اولین نقطه کمترین هزینه را هم دارد). بنابراین هزینهٔ مسیر پس از آن نقطه اشتباهاً به آن نسبت داده نمی‌شود.

تابع جریمهٔ هزینه `p(C)` به طور پیش‌فرض `log(1+C)` است. امتیازها به این شکل تعریف شده‌اند:

```text
Invalid sequence:  fitness = 0
Not solved:        fitness = 1000 / ((1 + min_conflict) * (1 + p(C*)))
Solved:            fitness = 100000 + 1000 / (1 + p(goal_path_cost))
```

این فرمول همیشه **غیرمنفی** است و هر مسیر حل‌شده از هر مسیر حل‌نشده Fitness بیشتری دارد. در بین مسیرهای حل‌شده نیز مسیر ارزان‌تر Fitness بالاتری می‌گیرد. این تابع تضمین بهینه بودن GA نیست؛ صرفاً یک معیار برای هدایت انتخاب نسل‌هاست. برای مقایسهٔ `log`، `linear` و `sqrt` باید از آزمایش‌های چند Seed استفاده کرد.

## Evolution و نگرش داروین

در هر نسل این مراحل اجرا می‌شود:

1. ارزیابی Fitness همهٔ کروموزوم‌ها، با Start State یکسان.
2. انتقال بدون تغییر بهترین **دو** کروموزوم به نسل بعد (`elitism=2`).
3. محاسبهٔ وزن‌های Selection بر اساس Fitness **مقیاس‌بندی‌شده**؛ مقیاس‌بندی رتبهٔ افراد را حفظ می‌کند و باعث می‌شود عدد ثابت بزرگ Goal تفاوت هزینهٔ مسیرهای حل‌شده را پنهان نکند. انتخاب والدین Roulette Wheel و **با جایگذاری** است؛ هر والد می‌تواند چند بار انتخاب شود.
4. ساخت دو فرزند از والدین با `one_point` (پیش‌فرض) یا `two_point` Crossover.
5. انجام Mutation تصادفی با `replace` (تغییر یک ژن، پیش‌فرض) یا `swap` (جابه‌جایی دو ژن). Mutation بر اساس یادگیری یا اصلاح محلی انجام نمی‌شود.
6. اضافه کردن درصد کمی کروموزوم تصادفی جدید (`immigrants=0.10`) برای کاهش ازبین‌رفتن تنوع.

کروموزوم‌های فرزند **Repair نمی‌شوند**؛ اگر ترتیب اکشن‌های جدید نامعتبر باشد، هنگام ارزیابی Fitness آن‌ها صفر خواهد بود. در این پیاده‌سازی از بهبود محلی یا یادگیری اکتسابی کروموزوم‌ها (نگرش لامارکی) استفاده نشده است.

پارامترها:

```bash
python -m genetic_alg solve --example professor --population 100 --length 100 --generations 1000 --elitism 2 --crossover two_point --mutation swap --mutation-rate 0.25 --immigrants 0.10 --seed 7 --output genetic_alg/results/variant_100
```

## آزمایش مقایسه‌ای روی چند جدول

برای جلوگیری از مقایسهٔ نتایج مدل‌های مختلف، همهٔ الگوریتم‌ها در این دستور روی **همان مدل و همان `initial_code`** اجرا می‌شوند. GA و Random با چند Seed اجرا می‌شوند؛ الگوریتم‌های قطعی روی هر جدول یک اجرا دارند.

```bash
python -m genetic_alg benchmark --rows 3 --cols 2 --count 10 --repeats 5 --generations 1000 --population 50 --length 50 --ga-seconds 5 --baseline-seconds 5 --seed 42 --output genetic_alg/results/benchmark_3x2
```

برای `5×2` نیز همین دستور با `--rows 5 --cols 2` قابل استفاده است، ولی برخی الگوریتم‌های دقیق ممکن است به محدودیت زمان یا تعداد Expanded States برسند. Timeout به معنی نبود جواب نیست.

## آزمایش تبدیل هزینه در Fitness

سه تبدیل را با جدول اولیه و Seedهای **یکسان** بررسی می‌کنم:

```bash
python -m genetic_alg study --example professor --transforms linear log sqrt --population 50 --length 50 --generations 1000 --repeats 10 --ga-seconds 5 --seed 42 --output genetic_alg/results/fitness_study
```

در فایل `fitness_study.csv` وضعیت، هزینهٔ واقعی مسیر و تعداد اکشن‌ها برای هر تبدیل ثبت می‌شود. نتیجه باید با نرخ حل مسئله و هزینهٔ مسیر در چند Seed تفسیر شود؛ کمترین Fitness خام بین تبدیل‌های متفاوت مستقیماً قابل مقایسه نیست.

## خروجی‌ها و داشبورد

خروجی هر آزمایش در مسیر تعیین‌شده با `--output` ذخیره می‌شود:

| فایل | محتوا |
|---|---|
| `comparison.csv` | تلاش‌های واقعی همهٔ الگوریتم‌ها، وضعیت پیدا شدن جواب، هزینه، اکشن، زمان، حافظه و Seed |
| `ga_history.csv` | Best/Mean/Median Fitness، Minimum Conflict، تعداد کروموزوم معتبر و منحصربه‌فرد در هر نسل |
| `genetic_solution.json` | پارامترها، کروموزوم، Prefix واقعی اکشن‌ها و Trace در صورت پیدا شدن Goal |
| `genetic_route.html` | انیمیشن مسیر GA، با همان ابزار `sandgrid.visualize` موجود (فقط برای جواب کامل) |
| `dashboard.html` | داشبورد آفلاین و تعاملی شامل نمودارهای هزینه، زمان، موفقیت، روند Fitness، Conflict و تنوع جمعیت |
| `fitness_study.csv` | در اجرای `study`: داده‌های مقایسهٔ تبدیل‌های هزینه |
| `run_config.json` | تنظیمات اجرا و نسخهٔ مدل (در `benchmark` نام فایل `experiment_config.json` است) |

بعد از اجرا، کافی است `dashboard.html` را با مرورگر باز کنم. نمودارها از داده‌های واقعی CSV ساخته می‌شوند؛ برای Timeout، هزینهٔ صفر یا هزینهٔ فرضی وارد نمی‌شود. فایل HTML کتابخانهٔ Plotly را در خود نگه می‌دارد و برای نمایش به اینترنت نیاز ندارد.

برای ساخت مجدد داشبورد از CSVها:

```bash
python -m genetic_alg dashboard --comparison genetic_alg/results/professor_compare/comparison.csv --history genetic_alg/results/professor_compare/ga_history.csv --output genetic_alg/results/professor_compare/dashboard_updated.html
```

### استفاده از CSV آزمایش‌های قبلی

در صورت داشتن `results/project_with_random/professor/comparison.csv`، می‌توان آن را با خروجی ژنتیک تجمیع کرد؛ اما **فقط اگر مدل قدیمی همان نسخهٔ فعلی** باشد. چون فایل CSV قبلی ممکن است ستون `model_version` نداشته باشد، تأیید صریح لازم است:

```bash
python -m genetic_alg compare --example professor --no-baselines --baseline-csv results/project_with_random/professor/comparison.csv --confirm-same-model --repeats 5 --ga-seconds 5 --output genetic_alg/results/combined_existing
```

این دستور تنها ردیف‌های دارای `initial_code` برابر را وارد می‌کند. کدهای مدل‌های قبلی نباید با `continuous-flow-v2-full-is-1` مقایسه شوند.

## ملاحظات گزارش نهایی

- **Cost و Action Count** متفاوت‌اند: BFS می‌تواند کمترین تعداد اکشن داشته باشد، بدون اینکه کمترین هزینهٔ وزنی را بدهد.
- در GA، تعداد ارزیابی‌های کروموزوم با `expanded` در BFS/UCS/A* یکسان نیست؛ در CSV برای `expanded` ژنتیک مقدار خالی ثبت می‌شود.
- برای مقایسهٔ زمان، سقف زمانی، سخت‌افزار، اندازهٔ جدول و تنظیمات اندازه‌گیری حافظه باید یکسان باشند. `peak_python_bytes` تنها حافظهٔ ردگیری‌شده توسط Python است، نه کل RAM فرایند.
- در چند جدول، هزینهٔ خام بین جدول‌های با سختی متفاوت مقیاس یکسانی ندارد. بهتر است مقایسهٔ چندجدولی با نسبت هزینه به **بهترین هزینهٔ مشاهده‌شده برای همان Initial State** (که لزوماً بهینهٔ ریاضی نیست) و نرخ موفقیت انجام شود.
- نتیجهٔ GA تصادفی و به Seed وابسته است. برای گزارش قابل اتکا باید حداقل چند اجرای مستقل ثبت شود.

تمام فایل‌ها و داده‌های این بخش در پوشهٔ `genetic_alg/` نگهداری می‌شوند؛ تنها وابستگی به بخش‌های قبلی، استفادهٔ بدون تغییر از مدل و الگوریتم‌های اصلی پروژه است. خروجی‌های نهایی پوشهٔ `results/` را می‌توان پس از آزمایش با `git add genetic_alg/` همراه کد در ریپازیتوری ثبت کرد.
