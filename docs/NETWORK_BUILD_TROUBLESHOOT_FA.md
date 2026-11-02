# رفع مشکل DNS در Docker Build بدون تغییر سایر پروژه‌ها

**نشانه واقعی:** مرحله نصب FastAPI در `backend/Dockerfile` با `Temporary failure in name resolution` برای `files.pythonhosted.org` متوقف می‌شود؛ این خطا از کد FastAPI نیست. دانلود Image پایه Python ممکن است موفق باشد درحالی‌که DNS کانتینر Build خراب است.

## مشاهده وضعیت بدون هیچ تغییری
```bash
cd /mnt/X/hami_system_sharif/superApp_background_removal_module
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
docker image ls --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}'
docker compose -p birefnet-lite ps -a
docker volume ls --filter name=birefnet-lite
docker network ls --filter name=birefnet-lite
getent ahostsv4 files.pythonhosted.org
docker run --rm --pull=never --network bridge python:3.11-slim-bookworm python -c 'import socket; print(socket.getaddrinfo("files.pythonhosted.org", 443))'
docker run --rm --pull=never --network host python:3.11-slim-bookworm python -c 'import socket; print(socket.getaddrinfo("files.pythonhosted.org", 443))'
```
`docker run --rm` فقط کانتینر موقت خودش را حذف می‌کند؛ به هیچ سرویس دیگری دست نمی‌زند.

اگر Host DNS موفق ولی Bridge DNS ناموفق باشد، مشکل احتمالاً در تنظیمات DNS یا VPN مربوط به Docker است. **Docker daemon را restart نکنید** و تنظیمات عمومی DNS را بدون ارزیابی اثر روی کانتینرهای دیگر تغییر ندهید.

## تغییر برای استفاده از Cache
از اصلاحات جدید این مخزن استفاده کنید: `pip install` دیگر `--no-cache-dir` ندارد و BuildKit cache mount اختصاصی دارد. npm نیز یک BuildKit cache اختصاصی دریافت کرده است. این Cacheها برای دفعات بعد هستند؛ پس از قطع شبکه، نصب‌های دانلودنشده را از هوا ایجاد نمی‌کنند.

## Build محدود به پروژه
```bash
git fetch personal
git merge --ff-only personal/main
docker compose -p birefnet-lite config --quiet
# ابتدا فقط Backend که شکست خورده است
DOCKER_BUILDKIT=1 docker compose -p birefnet-lite --progress plain build api
# UI قبلاً موفق ساخته شده و نیاز به rebuild فوری ندارد.
docker image inspect birefnet-lite-api:local >/dev/null
docker image inspect birefnet-lite-ui:local >/dev/null
make model
make model-verify
make up
make ps
make health
```
از `--no-cache`، `docker builder prune`، `docker system prune`، `docker volume prune`، `docker compose down -v` استفاده نکنید.

## راه جایگزین فقط برای Build هنگام خرابی شبکه Bridge
فقط اگر تست DNS با `--network host` موفق باشد و Host یک ماشین مورداعتماد Linux باشد:
```bash
DOCKER_BUILDKIT=1 docker build --network=host \
  -f backend/Dockerfile -t birefnet-lite-api:local .
```
این گزینه فقط برای مرحله Build است و سرویس‌های درحال اجرا یا شبکه آن‌ها را تغییر نمی‌دهد. بسته به Builder ممکن است entitlement موردنیاز باشد. پس از Build، دانلود Model با شبکه Bridge به‌صورت مستقل باید تست شود.

## پاک‌سازی اختیاری بسیار محدود
اگر واقعاً می‌خواهید Imageهای فقط این پروژه حذف شوند، ابتدا مطمئن شوید این دو Image به مصرف‌کننده دیگری داده نشده‌اند:
```bash
docker compose -p birefnet-lite rm --stop --force api ui
docker image rm birefnet-lite-api:local birefnet-lite-ui:local
```
بدون `-f` روی `docker image rm` اگر Image به کانتینر دیگری متصل باشد Docker حذف را رد می‌کند. مدل ذخیره‌شده در `birefnet-lite_model_cache` را حذف نکنید. پاک کردن Imageها از نظر فنی ضروری نیست و باعث تکرار بخشی از دانلودها می‌شود.

## میرورهای رسمی و مکانیزم Build (به‌روزرسانی ۳۱ اکتبر ۲۰۲۶)

طبق مستندات رسمی [لیارا](https://docs.liara.ir/mirrors/pypi/) و [چابکان](https://iran.chabokan.net/)، اکنون نصب پکیج‌های Python به‌ترتیب از این منابع انجام می‌شود:

1. لیارا: `https://package-mirror.liara.ir/repository/pypi/simple` (اولویت اول)
2. چابکان: `https://mirror2.chabokan.net/pypi/simple/` (تلاش مجدد اگر نصب اول شکست بخورد)

پاسخ HTTP 405 در `curl -I` برای چابکان فقط نشان می‌دهد HEAD مجاز نیست. برای تست واقعی باید GET به کار رود:

```bash
curl -fsS --max-time 15 -o /dev/null -w 'Liara HTTP %{http_code}\n' 'https://package-mirror.liara.ir/repository/pypi/simple/fastapi/'
curl -fsS --max-time 15 -o /dev/null -w 'Chabokan HTTP %{http_code}\n' 'https://mirror2.chabokan.net/pypi/simple/fastapi/'
```

`pip --extra-index-url` ترتیب fallback قابل‌اعتماد نمی‌دهد؛ Dockerfile ابتدا نصب را فقط با لیارا امتحان می‌کند و اگر شکست خورد، با چابکان مجدداً اجرا می‌کند. اگر هر دو مخزن خطای DNS/شبکه داشته باشند Build همچنان شکست می‌خورد. Cache پروژه در BuildKit حفظ می‌شود. در `docker-compose.yml` بخش `api.build.args` برای تغییر Mirrorها از `.env` وجود دارد.

### دستورات امن پس از Pull

```bash
cd /mnt/X/hami_system_sharif/superApp_background_removal_module
git fetch personal
git merge --ff-only personal/main
# فایل .env قبلی تغییر خودکار نمی‌کند؛ مطابق Compose فعلی API_PORT=8001 و UI_PORT=8082 تنظیم کنید.
docker compose config --quiet
DOCKER_BUILDKIT=1 docker compose --progress plain build api
# UI قبلاً build شده است؛ در صورت نیاز جداگانه بسازید.
docker image inspect birefnet-lite-api:local
make model
make model-verify
make up
make ps
make health
```

**توجه:** مدل ONNX از Hugging Face دریافت می‌شود، نه PyPI. این Mirrorها مشکل دانلود مدل را به‌طور خودکار حل نمی‌کنند. دستورات آزمایشی قبلی که `python:3.11-slim-bookworm` را با `--pull=never` اجرا می‌کردند ممکن است به دلیل نبود تگ محلی، اصلاً به مرحله آزمایش DNS نرسیده باشند؛ همچنین برخی درخواست‌های شبکه ممکن است معلق بمانند. در این نسخه ابتدا دو URL بالا با HTTP GET آزمایش شوند.
