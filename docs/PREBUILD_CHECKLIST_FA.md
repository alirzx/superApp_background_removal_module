# راهنمای فارسی بررسی پیش از Build (CPU-only)

## وضعیت واقعی
این مخزن دو سرویس دائم دارد: `api` (FastAPI + ONNX Runtime CPU) و `ui` (React + Nginx). تست‌های واحد به کمک مدل شبیه‌سازی‌شده هستند و به معنی تأیید inference واقعی نیستند.

## مدل و زنجیره داده
- مدل مبدأ: `ZhengPeng7/BiRefNet_lite`، تبدیل ONNX: `onnx-community/BiRefNet_lite-ONNX`.
- Revision ثابت: `de15b22ba131738a16dff04aab8bdf8dc32e3ac1`، فایل `onnx/model.onnx`، SHA256 برابر `5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333`.
- `make model` فایل را با بررسی هش در Volume مشترک دانلود می‌کند؛ `make model-verify` بدون دانلود صحت کش را بررسی می‌کند.
- FastAPI در startup یک Session ایجاد و Warm-up می‌کند؛ برای هر request مدل دوباره دانلود یا load نمی‌شود.
- Input: JPEG/PNG/WebP، اصلاح EXIF، تبدیل RGBA به RGB، resize به 1024×1024، ImageNet normalize، NCHW float32.
- Output: `output_image` logits، Sigmoid، resize ماسک به اندازه اصلی، اعمال Alpha اولیه، خروجی PNG شفاف یا Mask خاکستری.
- مدل فقط سوژه برجسته را جدا می‌کند؛ جداسازی چند شیء با prompt و پردازش ویدئو در نسخه اول وجود ندارد.

## راه‌اندازی محلی Ubuntu
```bash
cd /mnt/X/hami_system_sharif/superApp_background_removal_module
cp -n .env.example .env
make doctor
make build
make model
make model-verify
make up
make ps
make health
docker compose logs --tail=100 api
docker compose logs --tail=100 ui
```

UI: `http://127.0.0.1:8082`، API: `http://127.0.0.1:8001/docs` در development. `make up` فقط اجرا می‌کند و Build مجدد انجام نمی‌دهد. `docker compose down` مدل را حفظ می‌کند؛ `down -v` وزن‌های ذخیره‌شده را حذف می‌کند.

## محیط سرور / GitLab
1. نمونه `.env.production.example` را روی سرور به `.env` کپی و `API_TOKEN` را با `openssl rand -hex 32` بسازید؛ فایل را Commit نکنید.
2. `APP_ENV=production` بدون توکن قوی راه‌اندازی نمی‌شود.
3. پورت‌های UI و API را روی loopback نگه دارید و با SSH Tunnel یا Ingress مجاز استفاده کنید.
4. **اخطار امنیتی:** Nginx توکن API را برای تمام درخواست‌های UI درج می‌کند، ولی احراز هویت کاربر ندارد. قبل از انتشار عمومی، HTTPS، احراز هویت (مثلاً OIDC/SSO) و Rate Limit در Ingress اجباری است.
5. CPU_THREADS=2 و MAX_CONCURRENT_INFERENCE=1 مقادیر اولیه هستند؛ RAM=3g، 4g و 5g در تست واقعی روی لپ‌تاپ به OOM منجر شده‌اند. API_MEMORY=8g در نمونه Production تنها پیشنهاد آزمایشی و بدون تضمین است.
6. CI فعلی فقط وجود فایل‌های Source را بررسی می‌کند و Job دستی SSH برای Build سرور دارد؛ تست‌های Mock به‌صورت خودکار در CI اجرا نمی‌شوند. RUN_SERVICES=0 مانع اجرای خودکار مدل می‌شود و مدل باید جداگانه در Volume دانلود و تأیید شود.

## چک‌لیست پذیرش
- [ ] `make doctor`, `make build`, `make model`, `make model-verify` موفق باشند.
- [ ] `docker compose ps` فقط دو سرویس دائم سالم نشان دهد.
- [ ] JPEG، PNG، WebP، تصویر EXIF، تصویر آسیب‌دیده و فایل خیلی بزرگ آزمایش شوند.
- [ ] کیفیت مرز مو/اشیا با نمونه مرجع PyTorch و چند تصویر واقعی بررسی شود.
- [ ] P50/P95 و RAM/CPU در هم‌زمانی ۱ و ۲ اندازه‌گیری شود؛ زیر ۱۰ ثانیه هنوز تضمین نشده.
- [ ] بارگذاری آفلاین بعد از دانلود اولیه و Cache پایدار بررسی شود.
- [ ] پیش از Production، مجوز وزن‌ها، امنیت Ingress و مدیریت لاگ تأیید شود.
