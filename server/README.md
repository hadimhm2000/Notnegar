# سرور نت‌نگار

نسخه‌ی کامل نت‌نگار برای اجرا روی VPS. آهنگ را به **شش لایه** جدا می‌کند (آواز، بیس، ضرب و درامز، گیتار، پیانو و کیبورد، سازهای دیگر)، دستگاه، نت پایه، کوک، ربع‌پرده و تمپو را تشخیص می‌دهد، برای هر لایه نت می‌نویسد و یک پارتیتور چندخطی PDF با علامت‌های کرن و سری می‌سازد.

## خروجی‌ها

- **PDF** حرفه‌ای با LilyPond: صفحه‌ی اول تحلیل و جدول کوک، بعد پارتیتور همه‌ی لایه‌ها
- **MusicXML** برای باز کردن و ویرایش در MuseScore، Sibelius، Finale و Dorico
- **MIDI** که ربع‌پرده‌ها را با pitch bend پخش می‌کند
- **فایل جدای هر لایه** (MP3) برای شنیدن و دانلود، و همه با هم در ZIP
- ارسال نتیجه به **ایمیل** (اگر SMTP تنظیم شود)

بعد از پایان پردازش، کاربر می‌تواند دستگاه، نت پایه، لایه‌های داخل پارتیتور، عنوان و ساز جدول کوک را عوض کند و پارتیتور در چند ثانیه دوباره ساخته می‌شود؛ جداسازی دوباره انجام نمی‌شود.

## سخت‌افزار لازم

| | حداقل | پیشنهادی |
| --- | --- | --- |
| پردازنده | ۲ هسته | ۴ هسته یا بیشتر |
| حافظه (RAM) | ۴ گیگابایت | ۸ گیگابایت |
| دیسک | ۱۵ گیگابایت | ۲۵ گیگابایت |
| کارت گرافیک | لازم نیست | با GPU انویدیا چند برابر سریع‌تر |

بیشترین زمان را جداسازی لایه‌ها می‌گیرد. روی پردازنده‌ی معمولی برای یک آهنگ چنددقیقه‌ای چند دقیقه طول می‌کشد. اولین آزمایش روی سرور خودتان زمان دقیق را نشان می‌دهد.

## نصب با Docker (پیشنهادی)

روی یک سرور Ubuntu تازه:

```bash
# ۱. نصب Docker
curl -fsSL https://get.docker.com | sh

# ۲. دریافت کد
git clone https://github.com/hadimhm2000/Notnegar.git
cd Notnegar/server

# ۳. تنظیمات
cp .env.example .env
nano .env            # در صورت نیاز: رمز، ایمیل، نشانی سایت

# ۴. ساخت و اجرا (ساخت اول ۱۰ تا ۲۰ دقیقه طول می‌کشد)
docker compose up -d --build

# ۵. بررسی
curl http://127.0.0.1:8000/api/health
```

خروجی مرحله‌ی ۵ نشان می‌دهد کدام اجزا فعال‌اند. باید `demucs`، `crepe` و `lilypond` همه `true` باشند.

### دسترسی از بیرون

**الف) سریع، بدون دامنه:** در `.env` مقدار `NOTNEGAR_BIND=0.0.0.0` بگذارید و `docker compose up -d` را دوباره اجرا کنید. سایت روی `http://IP-سرور:8000` باز می‌شود. در این حالت حتماً `NOTNEGAR_BASIC_AUTH` را برای رمز گذاشتن تنظیم کنید.

**ب) با دامنه و HTTPS (پیشنهادی):**

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/notnegar
sudo nano /etc/nginx/sites-available/notnegar      # notnegar.example.com را با دامنه‌ی خودتان عوض کنید
sudo ln -s /etc/nginx/sites-available/notnegar /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d notnegar.example.com
```

### به‌روزرسانی

```bash
cd Notnegar && git pull
cd server && docker compose up -d --build
```

## نصب بدون Docker

روی Ubuntu 22.04 یا 24.04 یا Debian 12:

```bash
git clone https://github.com/hadimhm2000/Notnegar.git
cd Notnegar
sudo bash server/deploy/install.sh
```

این اسکریپت همه‌چیز را در `/opt/notnegar` نصب می‌کند، سرویس systemd می‌سازد و nginx را تنظیم می‌کند. لاگ‌ها: `journalctl -u notnegar -f`

## سرور در ایران

دو نکته برای VPS داخل ایران:

1. **دانلود بسته‌ها.** بسته‌های PyTorch از `download.pytorch.org` و وزن مدل Demucs از `dl.fbaipublicfiles.com` دانلود می‌شوند. ممکن است این نشانی‌ها از ایران در دسترس نباشند. راه ساده این است که image را روی یک سرور خارج از ایران (یا با GitHub Actions) بسازید و منتقل کنید:
   ```bash
   # روی سرور خارج
   docker build -t notnegar:latest server && docker save notnegar:latest | gzip > notnegar.tar.gz
   # روی سرور ایران
   gunzip -c notnegar.tar.gz | docker load
   docker compose up -d          # بدون --build
   ```
   وزن مدل‌ها هنگام ساخت داخل image ذخیره می‌شوند، پس سرور بعد از آن به اینترنت خارجی نیازی ندارد.
2. **فونت صفحه‌ی وب** از Google Fonts بارگذاری می‌شود. اگر در دسترس نباشد، صفحه با فونت Tahoma نمایش داده می‌شود و کار می‌کند.

## تنظیمات مهم (`.env`)

| متغیر | کاربرد |
| --- | --- |
| `NOTNEGAR_BASIC_AUTH` | رمز برای سایت خصوصی، به شکل `user:password` |
| `NOTNEGAR_PUBLIC_URL` | نشانی سایت، برای لینک داخل ایمیل |
| `NOTNEGAR_WORKERS` | چند آهنگ هم‌زمان پردازش شود (هرکدام ۳ تا ۴ گیگ حافظه) |
| `NOTNEGAR_CREPE_MODEL` | `full` دقیق‌تر، `tiny` بسیار سریع‌تر روی سرور ضعیف |
| `NOTNEGAR_MAX_SECONDS` | حداکثر طول قابل تحلیل هر آهنگ (ثانیه) |
| `NOTNEGAR_TTL_HOURS` | فایل‌های هر کار بعد از این مدت پاک می‌شوند |
| `NOTNEGAR_SMTP_*` | تنظیمات ارسال ایمیل |

## API

| مسیر | کار |
| --- | --- |
| `POST /api/jobs` | ارسال فایل (فرم: `file`، `title`، `artist`، `instrument`، `detail`، `names`، `email`) |
| `GET /api/jobs/{id}` | وضعیت و نتیجه |
| `POST /api/jobs/{id}/render` | ساخت دوباره با `scale`، `tonic`، `layers`، `instrument`، `title`، `names` |
| `GET /api/jobs/{id}/file/score.pdf` | پارتیتور (همچنین `score.musicxml`، `score.mid`، `stems/vocals.mp3` و...) |
| `GET /api/jobs/{id}/stems.zip` | همه‌ی لایه‌ها |
| `GET /api/health` | اجزای فعال روی سرور |

## ساختار کد

| فایل | نقش |
| --- | --- |
| `notnegar/separate.py` | جداسازی لایه‌ها با Demucs (`htdemucs_6s`) |
| `notnegar/transcribe.py` | آواز و بیس با CREPE؛ پیانو، گیتار و سازهای دیگر با Basic Pitch؛ ضرب با تشخیص ضربه |
| `notnegar/analysis.py` | تقسیم ملودی به نت، کوک، تشخیص ربع‌پرده، رتبه‌بندی دستگاه‌ها و گام‌ها |
| `notnegar/theory.py` | دستگاه‌ها، املای نت با کرن و سری، نام فارسی نت‌ها، جدول کوک |
| `notnegar/dsp.py` | پردازش سیگنال بدون وابستگی (جایگزین مدل‌ها وقتی نصب نیستند) |
| `notnegar/score.py` | چیدن نت‌ها روی شبکه‌ی ضرب |
| `notnegar/lilypond.py`، `musicxml.py`، `midi.py` | ساخت خروجی‌ها |
| `notnegar/pipeline.py` | ترتیب کل مراحل |
| `notnegar/app.py`، `jobs.py`، `mailer.py` | وب‌سرور، صف کارها، ایمیل |
| `static/index.html` | صفحه‌ی وب |
| `tests/` | آزمون سرتاسری با آهنگ‌های ساختگی که جواب درستشان معلوم است |

اگر Demucs، CREPE یا Basic Pitch نصب نباشند، سرور با روش‌های جایگزین داخلی کار می‌کند و صفحه‌ی وب نشان می‌دهد کدام اجزا فعال نیستند. نتیجه در این حالت تقریبی‌تر است.

## محدودیت‌های شناخته‌شده

- جداسازی Demucs برای سازهای غربی آموزش دیده است. تار، سنتور و کمانچه معمولاً در لایه‌ی «سازهای دیگر» یا گیتار و پیانو قرار می‌گیرند.
- نت‌نویسی ریتم ساده‌سازی‌شده است: خط میزان از ضرب اول تشخیص‌داده‌شده شروع می‌شود و ممکن است با ضرب قوی واقعی آهنگ هم‌خوان نباشد.
- آوازهای هم‌خانواده‌ی شور (ابوعطا، دشتی، بیات ترک، افشاری) و راست‌پنجگاه هنوز از دستگاه مادرشان جدا نمی‌شوند؛ برای این کار به داده‌ی آموزشی برچسب‌خورده نیاز است.
