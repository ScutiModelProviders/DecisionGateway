# Purpose

**Kind:** text + typed questions (+ optional images) → decisions with confidence

**Tags:** `cpu`, `http`, `streaming`

| | |
|---|---|
| Input | Gateway id, non-empty text (16000 characters by default), 1–8 typed choice/score/noul/box questions and optional referenced PNG/JPEG assets. |
| Output | Typed answers, confidence, `uncertain`, `answered_by`, input-token count and model identity; JSON or native/emulated NDJSON. |
| Needs | `DSC_Laya_Model` or `DSC_D3_Model`, or an Ollama decision model or TypeSafe Jev, configured as gateways on the admin page. These put the tool in the Decision model group. |
| Runs on | CPU. Holds no model; async HTTP adapters call upstream decision runtimes. |

**Use for:** giving callers one typed decision contract across several decision-model runtimes.
**Not for:** chat loops, free-form generation, routing strategies, escalation chains, model training or checkpoint management.
