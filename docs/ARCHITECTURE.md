# Architecture and inference contract

```
Browser -> UI container (Nginx + React SPA)
             | /api/* (same origin, inject X-API-Key server-side)
             v
           API container (FastAPI, one Uvicorn worker)
             | validation -> pixels+byte guard -> PIL EXIF correction
             | ImageNet normalized RGB tensor (1,3,1024,1024)
             v
           ONNX Runtime CPUExecutionProvider
             | output_image: logits (1,1,1024,1024)
             v
           sigmoid -> 8bit alpha -> resize to native size
             | respect existing alpha -> PNG (or grayscale mask)
             v
           Browser preview & download

Model acquisition: `make model` -> Hugging Face cache -> SHA256 verify -> /models/*.onnx
                   ^ persist named Docker volume; **not** inside Git or image.
```

## Choosing ONNX instead of remote PyTorch code

- Origin: `ZhengPeng7/BiRefNet_lite` (Safetensors, custom PyTorch code).
- Deployment graph: `onnx-community/BiRefNet_lite-ONNX` (`onnx/model.onnx`).
- The converted graph uses `input_image` / `output_image`, NCHW RGB, ImageNet mean/std, fixed 1024 square, floating-point logits requiring sigmoid.
- ONNX Runtime loads a local graph. No `trust_remote_code=True` and no user request performs external network I/O.
- Pinned revision and SHA256 protect against silently changed weights.
- The ONNX conversion is third-party (Hugging Face onnx-community), not the original PyTorch publisher's file. Check parity on representative images before production promotion.
- Do not swap to the fp16 graph without checking I/O schema, SHA256, CPU EP support, and accuracy; fp16 weights do not imply CPU speedup.

## Runtime process

- API starts only if validated model exists, then creates an `onnxruntime.InferenceSession` and performs an explicit dummy warm-up. Startup can take time on CPU.
- One Uvicorn worker prevents multiple copies of the model in process memory. Requests are dispatched to the thread pool and gated by a semaphore; saturation returns 503/Retry-After.
- Tests don't need weights: a fake engine is injected using `create_app`.
- No image is written to disk; incoming request bytes and output are kept in request memory.
- Limits: max upload bytes, max decompressed pixels, max inference jobs, max queue wait.
- Docker confines CPU and memory; tune based on p50/p95 plus RSS.

## Service API

| Method | Route | Input | Output |
|---|---|---|---|
| GET | `/health/live` | - | `{"status":"alive"}` |
| GET | `/health/ready` | - | 200 ready / 503 not-ready |
| GET | `/v1/models` | API key | model metadata |
| POST | `/v1/remove-background` | multipart `file`, optional `blur` | image/png (RGBA) |
| POST | `/v1/mask` | multipart `file`, optional `blur` | image/png (grayscale) |
| GET | `/metrics` | API key | Prometheus text |

Authentication: `X-API-Key` when `API_TOKEN` is set. In `APP_ENV=production`, startup fails if the token is missing or shorter than 24 characters. UI Nginx adds the key to internal `/api/` requests, without exposing it to JavaScript.

## Limitations

- Single-salient-subject segmentation; no point/box-guided selection of an arbitrary object.
- Fixed 1024x1024 input, stretched before inference. Narrow aspect ratios may degrade quality.
- Produces a soft alpha via sigmoid; fine hair/transparency may not match purpose-trained matting models.
- Does not process video; videos require separate frame handling and temporal consistency.
- CPU latency and memory are hardware-dependent; a 10-second target is **not guaranteed**.
- UI upload limit and API upload limit must be kept aligned.
- Vanilla React SPA uses Nginx; no Node.js process in runtime UI image.
