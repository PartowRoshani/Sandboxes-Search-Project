# Genetic Algorithm experiment results

خروجی‌های واقعی بعد از اجرای `python -m genetic_alg compare`، `study` یا `benchmark` در زیرپوشه‌های این مسیر ایجاد می‌شوند. گزارش‌ها و HTML داشبوردها عمداً در `.gitignore` قرار نگرفته‌اند تا بتوان آن‌ها را همراه با کد همین تکلیف در GitHub ثبت کرد.

برای اجرای آزمایش اصلی استاد از ریشهٔ پروژه:

```bash
python -m genetic_alg compare --example professor --population 50 --length 50 --generations 1000 --repeats 5 --ga-seconds 5 --baseline-seconds 5 --seed 42 --output genetic_alg/results/professor_compare
```

سپس فایل `professor_compare/dashboard.html` را در مرورگر باز کنید. اینجا تا زمانی که آزمایش روی مدل اصلی انجام نشده، هیچ نتیجهٔ عددی ساختگی قرار داده نشده است.
