# راه‌اندازی Aqua Launch (پروفایل گیت‌هاب)

## ۱. ساخت ریپازیتوری پروفایل

اگر هنوز نساختی، یک ریپو **public** با نام دقیقاً برابر نام کاربری‌ات بساز:

```
github.com/amiiiirkamali/amiiiirkamali
```

## ۲. کپی فایل‌ها

ساختار نهایی ریپو باید این شکلی باشد:

```
amiiiirkamali/
├── README.md
├── config.json
├── .gitignore
├── assets/
│   ├── profile-source.png      ← عکس پروفایل خودت (اختیاری ولی توصیه می‌شود)
│   ├── identity.svg            ← این‌ها خودکار ساخته می‌شوند
│   ├── signal.svg
│   ├── contributions.svg
│   ├── arsenal.svg
│   ├── trajectory.svg
│   └── missions.svg
├── scripts/
│   ├── generate.py
│   └── requirements.txt
└── .github/workflows/
    └── aqua-launch.yml
```

> عکس پروفایل: یک PNG مربعی (مثلاً ۶۰۰×۶۰۰) با پس‌زمینه‌ی ساده و کنتراست بالا بگذار در
> `assets/profile-source.png`. اگر نگذاری، اسکریپت به‌جای پرتره‌ی ASCII یک **سیجیل انیمیشنی**
> با حروف اول اسمت می‌سازد و هیچ خطایی نمی‌دهد.

## ۳. توکن (برای تقویم مشارکت دقیق)

1. برو به **Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. توکن جدید با اسکوپ `read:user` بساز
3. در ریپو: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `PROFILE_TOKEN`
   - Value: توکنی که ساختی

بدون توکن هم کار می‌کند (از HTML عمومی گیت‌هاب می‌خواند)، ولی با توکن دقیق‌تر و پایدارتر است.

## ۴. اجرای اول

```bash
python -m pip install -r scripts/requirements.txt
python scripts/generate.py --demo     # پیش‌نمایش آفلاین با داده‌ی نمونه
python scripts/generate.py            # داده‌ی واقعی گیت‌هاب
git add . && git commit -m "feat: aqua launch profile" && git push
```

بعدش در تب **Actions** ریپو، ورک‌فلو `Aqua Launch` را یک‌بار دستی با **Run workflow** اجرا کن.
از آن به بعد هر روز ساعت ۵:۴۳ UTC (۹:۱۳ صبح به وقت تهران) خودکار آپدیت می‌شود.

## ۵. شخصی‌سازی

همه‌چیز از `config.json` می‌آید — نیازی به دست‌زدن به کد نیست:

| کلید | کاربرد |
| --- | --- |
| `wordmark` | متن ASCII بزرگ وسط پنل اول (حداکثر ۸ کاراکتر) |
| `skills` | چیپ‌های زیر اسم در پنل identity (۶ تا) |
| `stack` | گروه‌های تکنولوژی + درصد تسلط در پنل arsenal (۶ گروه × ۵ آیتم) |
| `experience` | تایم‌لاین شغلی در پنل trajectory (۵ ردیف) |
| `projects` | کارت‌های پروژه در پنل missions (۹ کارت) |
| `accent` | رنگ هر گروه/نقش/پروژه — هر کد HEX معتبری قبول است |

### تغییر پالت رنگی

بالای `scripts/generate.py` بخش `design tokens` را عوض کن. مثلاً برای تم بنفش:

```python
TEAL = "#a78bfa"
MINT = "#ddd6fe"
HAIR = "#6d28d9"
EDGE = "#7c3aed"
```

### رندر فقط یک پنل

```bash
python scripts/generate.py --only missions trajectory
```

## ۶. نکات مهم

- **کش تصاویر گیت‌هاب:** گیت‌هاب SVGها را از طریق camo کش می‌کند. اگر بعد از پوش تغییر را
  فوری ندیدی، چند دقیقه صبر کن یا `Ctrl+Shift+R` بزن.
- **انیمیشن:** انیمیشن‌های CSS و SMIL داخل `<img>` در گیت‌هاب اجرا می‌شوند؛ جاوااسکریپت نه.
  برای همین کل دیزاین بدون JS نوشته شده.
- **دسترس‌پذیری:** هر پنل `role="img"` و `aria-label` دارد و با
  `prefers-reduced-motion: reduce` همه‌ی انیمیشن‌ها خاموش می‌شوند.
- **تم روشن/تیره:** پنل‌ها پس‌زمینه‌ی خودشان را دارند، پس در هر دو تم گیت‌هاب درست دیده می‌شوند.
