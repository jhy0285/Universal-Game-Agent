# Upstream verification (2026-10-20–21)

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

Additional primary checks:

- [Laya 0.4.12 PyPI metadata](https://pypi.org/pypi/laya/0.4.12/json): published wheel/sdist,
  Python >=3.10, torch>=2.0, transformers>=4.48. Model-card access was denied by the
  current proxy policy, so checkpoint availability/license/integrity remain unverified.
- [MSS license](https://github.com/BoboTiG/python-mss/blob/main/LICENSE.txt): MIT.
- [Ghidra license](https://github.com/NationalSecurityAgency/ghidra/blob/master/LICENSE): Apache-2.0.
- [Ghidra AnalyzeHeadless parser](https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/Features/Base/src/main/java/ghidra/app/util/headless/AnalyzeHeadless.java):
  verified flags `-import`, `-scriptPath`, `-postScript`, `-analysisTimeoutPerFile`, `-deleteProject`.
- [MCP 2025-06-18 schema](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/schema/2025-06-18/schema.ts):
  initialize and tools/list/call wire contracts.
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), its MIT LICENSE and
  [PyPI 2.3.0 metadata](https://pypi.org/pypi/mcp/2.3.0/json): local SDK initialize/discovery/Player/cancel
  was tested against the UGA stdio server. No external AI provider was connected.
- [Godot 4.6.3 official checksums](https://github.com/godotengine/godot/releases/download/4.6.3-stable/SHA512-SUMS.txt):
  the complete export-template archive matched SHA-512 before extracting release templates.
- Official release archives for [JADX 1.5.6](https://github.com/skylot/jadx/releases/tag/v1.5.6),
  [Ghidra 12.1.4](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build) and
  Temurin JDK 21.0.12.1+1 matched their published SHA-256 before extraction/execution. Own class,
  DEX-APK and ELF fixtures were actually analyzed. Digests and limits: [Reverse validation](reverse-validation.md).
- [REA 6.7.0 npm metadata](https://registry.npmjs.org/rea-agents/6.7.0) and upstream offline pwntools
  wrapper were read. npm integrity was verified; local MCP discovery and one read-only ELF layout
  call succeeded. 207 discovered tools does not mean 207 tested tools. Target host execution was not used.
- [R8 9.5.28 Google Maven](https://dl.google.com/dl/android/maven2/com/android/tools/r8/9.5.28/r8-9.5.28.jar):
  published SHA-1 checked, local SHA-256 retained. BSD-3-Clause authored code plus included library notices.
  D8 generated the own DEX fixture; the ZIP is not an installable Android application.
- [Debian trixie metadata](https://deb.debian.org/debian/dists/trixie/InRelease): sqv verified the
  signed InRelease with the installed Debian archive keyring, then Packages.xz and DEB SHA-256.
  Xvfb and libXfont were extracted under .uga/tools without changing system packages or permissions.
  MSS 10.2.0 captured a real Godot X11 window using Mesa software rendering.
- Chromium 154.0.8037.57 and Playwright core exercised the actual dashboard with Chromium sandbox
  enabled. This does not establish Windows runtime, GPU, or general OCR/VLM support.
