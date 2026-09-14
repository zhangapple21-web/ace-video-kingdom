# imagegen → Shenwen 图像模型

视频王国的图像能力已接入 `imagegen` 的标准 CLI 入口。适配器不会改动
`imagegen` 技能自带的 `scripts/image_gen.py`，只在进程内把本机的
`SHENWEN_IMAGE_API_KEY` 映射为 OpenAI SDK 所需的 `OPENAI_API_KEY`，并把
`SHENWEN_IMAGE_BASE_URL`（默认 `https://api.shenwenai.com/v1`）映射为
`OPENAI_BASE_URL`。

默认模型为 `gpt-image-2`，不会回退到旧模型。当前文档登记的可选模型为 `gpt-image-2.5-flare` 和 `gpt-image-2.5-sunburst`；它们必须通过 `--model` 显式选择，不会静默切换。密钥只从进程或用户级环境变量读取，
不写入仓库、命令参数或生成收据。

## 使用

在仓库根目录执行：

```powershell
.\tools\imagegen_shenwen.ps1 generate `
  --prompt "中国审美写实短剧的清晨街巷，柔和侧光，竖屏构图" `
  --size 1024x1024 `
  --quality low `
  --out output\imagegen\sample.png
```

如需编辑，使用 `edit` 并传入 `--image`；批量生成使用 `generate-batch`。
可以通过 `SHENWEN_IMAGE_BASE_URL` 覆盖兼容端点，但应保持其包含 `/v1` 的 API 根路径。

## 依赖

适配器调用 `imagegen` 技能附带的 CLI，因此当前 Python 环境需要 `openai` 包：

```powershell
py -m pip install openai
```

先做无网络检查：

```powershell
.\tools\imagegen_shenwen.ps1 generate `
  --prompt "connection smoke test" `
  --dry-run
```
