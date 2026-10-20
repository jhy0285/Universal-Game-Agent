# Upstream verification (2026-10-20)

Primary sources were read, not assumed from package names. Documentation sites denied
the current egress policy (HTTP CONNECT 403); their official GitHub source documents
were used instead. Moving `main`/`master` documentation is observation on this date,
not a promise that future APIs stay compatible. `uv.lock` fixes our installed versions.

| Component | Primary source read | API/platform/license observation |
|---|---|---|
| Python | [3.11 subprocess docs](https://github.com/python/cpython/blob/3.11/Doc/library/subprocess.rst) | `Popen`, timeout, no shell by default; Windows support. PSF license. |
| Pydantic | [models](https://github.com/pydantic/pydantic/blob/main/docs/concepts/models.md), LICENSE | v2 `model_validate_json`, `model_dump_json`, `model_json_schema`; MIT. |
| FastAPI | [first steps](https://github.com/fastapi/fastapi/blob/master/docs/en/docs/tutorial/first-steps.md), LICENSE | ASGI app, typed routes; MIT. |
| Pillow | [Image API](https://github.com/python-pillow/Pillow/blob/main/docs/reference/Image.rst), LICENSE | Portable pixel/PNG operations; HPND-family Pillow license, retain upstream notices. |
| psutil | [README](https://github.com/giampaolo/psutil), LICENSE | Cross-platform process/resource monitoring; BSD-3-Clause. |
| MSS | [README](https://github.com/BoboTiG/python-mss) | Python >=3.10, thread-safe desktop capture; optional, requires graphical session. |
| Godot | [command-line docs](https://github.com/godotengine/godot-docs/blob/master/tutorials/editor/command_line_tutorial.rst), [license](https://github.com/godotengine/godot/blob/master/LICENSE.txt) | `--headless --path`, `--script`, `--check-only`; native Windows/Linux; MIT. Export requires export templates. |
| JADX | [upstream README](https://github.com/skylot/jadx) | `jadx -d OUTPUT INPUT`; 64-bit Java >=11; Windows launcher `.bat`; Apache-2.0. |
| REA | [morluto/rea](https://github.com/morluto/rea), [installation](https://github.com/morluto/rea/blob/main/docs/installation.md), [MCP contracts](https://github.com/morluto/rea/blob/main/docs/mcp-contracts.md) | MIT-authored code, third-party licenses separate; `rea-agents@6.7.0`, stdio MCP default; HTTP opt-in. Windows Ghidra is experimental/read-only with scope limitations. No blanket Windows support claim. |
| Laya | [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya) | Public upstream identifies `Router().predict(state, questions)` → `answers[key].choice`, **text decisions, no image input**. Apache-2.0 repository; checkpoint licenses must be checked individually. |

Laya upstream describes Python >=3.10, English ModernBERT-large 421M parameters,
multilingual mmBERT-base 322M, and typed-decisions 421M. CPU PyTorch is supported;
Windows PowerShell installation is documented. Upstream speed/accuracy claims are
not UGA measurements. First Router use downloads checkpoints. We do not silently
download weights, run remote model code, or treat upstream benchmark numbers as ours.
Real inference needs separate dependency/model installation, checkpoint license/integrity
verification, resource checks and a same-machine benchmark.

Unity requires an installed licensed Editor. It is an extension boundary, not a tested
engine here. No external AI service is connected.
