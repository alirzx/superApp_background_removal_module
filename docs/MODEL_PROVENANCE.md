# Model provenance and license notes

**Original model:** https://huggingface.co/ZhengPeng7/BiRefNet_lite

**Original project:** https://github.com/ZhengPeng7/BiRefNet (MIT license)

**ONNX conversion:** https://huggingface.co/onnx-community/BiRefNet_lite-ONNX (model card indicates `license: mit` and `base_model: ZhengPeng7/BiRefNet_lite`)

**Pinned deployment artifact:** `onnx/model.onnx`, SHA256 `5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333`, weight size ~224 MB on Hub, conversion revision `de15b22` (short commit prefix shown by HF main tree at research time).

**Conversion trust boundary:** the official upstream model currently provides Safetensors weights plus custom model code; the ONNX repository is a separately published conversion. The downloaded graph is loaded by ONNX Runtime without executing Hugging Face `trust_remote_code`.

**License review:** Copyright/license for source code and the ONNX conversion are described as MIT by their upstream repos. This project is also MIT licensed, but project license does not override upstream weight rights. Check both model cards, upstream LICENSE, any third-party dependencies, and your use case before commercial deployment. This is a technical inventory, not legal advice.

**No pretrained model file is bundled in ZIP.** Run `make model` on a machine with Internet. If pinned revision stops resolving, check the upstream Hub git history and update to a full immutable commit ID, then reverify model SHA256 (never suppress validation).

**ONNX image contract** documented by the converted model card: fixed resolution 1024×1024 RGB ImageNet mean/std; logits from output `output_image`; sigmoid then resize mask.
