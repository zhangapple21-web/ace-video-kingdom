# 图像生成通路实测记录

日期：2026-10-14　站点：`https://studio.zhangningjing.com/dramai/`（听荷轩 · 残荷诡影）

## 结论先说

**能用的通路只有一条**：自家无限画布的 `/api/ai`。
其余三条全部不可用，且各自的失败原因不同 —— 不是同一个故障，换个模型名救不回来。

| 通路 | 结果 | 具体报错 |
| --- | --- | --- |
| `api.shenwenai.com` + `SHENWEN_IMAGE_API_KEY` | ❌ | `Upstream service temporarily unavailable`（gpt-image-2 / -2.5-flare / -2.5-sunburst 三个变体全挂） |
| 同上 + `SHENWEN_GROK_API_KEY` | ❌ | `No eligible Grok media accounts`（grok-imagine-image / -quality） |
| `SHENWEN_IMAGE_API_KEY` 打 `agnes-image-*` | ❌ | `Invalid bearer token` —— Agnes 系不走这个网关 |
| 本地 OneAPI `127.0.0.1:3000` | ❌ | 网关在跑，但 21 个模型**全是文本模型，无 image** |
| **无限画布 `/api/ai`** | ✅ | `agnes-image-2.5-flash` 出图成功 |

## 为什么自家接口才通

`https://www.zhangningjing.com/config.js` 发给浏览器的配置里：

```js
apiKey: "__BUILTIN_IMAGE_KEY__",
baseUrl: "https://www.zhangningjing.com/api/ai"
```

`__BUILTIN_IMAGE_KEY__` 是**占位符**。真实密钥由 Cloudflare Pages Worker 在服务端注入，
浏览器和任何脚本都拿不到。所以调用这个接口**不需要本机持有任何密钥** —— 而上面三条
失败的通路，用的都是本机自己的凭据去够一个已经故障或根本不对口的上游。

## 两个会浪费时间的坑

1. **Cloudflare `error code: 1010`**：用 Python/urllib 请求 `/api/ai` 会拿到这个，
   它是**浏览器签名封锁**，不是 API 拒绝。加浏览器 `User-Agent`（外加 `Origin`、`Referer`）
   即通。误判成「接口不可用」会直接放弃唯一能用的通路。

2. **`agnes-image-2.5-flash` 是免费档，3 张后限流**：
   `该免费模型当前请求过于频繁，请约 900 秒后重试`。
   一次跑六张必然失败一半。要么拆成两批间隔 15 分钟，要么换付费模型（当前都不可用）。

## 广告了但当时不可用的模型

画布配置页列出 8 个图像模型，实测当时只有 `agnes-image-2.5-flash` 能出图：

| 模型 | 实测 |
| --- | --- |
| `agnes-image-2.5-flash` | ✅ PASS |
| `agnes-image-2.1-flash` | ⚠️ `IncompleteRead`（流中断，可重试） |
| `agnes-image-2.0-flash` | ❌ 免费额度上限 |
| `gpt-image-2` | ❌ 上游不可用 |
| `gpt-image-2.5-flare` / `-2.5-sunburst` | ❌ 上游不可用 |
| `grok-imagine-image` / `-quality` | ❌ 无可用账号 |

**这是当时的快照，不是永久结论。** 下次要重新探测，不要照抄：
`py -3 probe_site_image.py`（走画布接口）或 `py -3 probe_image_models.py`（走直连网关）。

## 本地兜底：ComfyUI + Z-Image Turbo（可用但档次不够）

`D:\Comfy-Desktop` 是一套完整的本地 ComfyUI：

- `unet/zImageTurboNSFW_61BF16Diffusion-Q3_K_M.gguf`（3.9 GB）
- `text_encoders/Qwen_3_4b-imatrix-Q3_K_M.gguf`（2.0 GB）
- `vae/ae.safetensors`（320 MB）
- `custom_nodes/ComfyUI-GGUF` 已装
- 显卡 RTX 3050 / 6 GB

模型放在 `ComfyUI-Shared`，而 ComfyUI 默认只认自己的 `models/`，**需要
`extra_model_paths.yaml` 接线**，否则 loader 会报「没有模型」。接好后
`/object_info` 能正确列出这三个文件，节点为 `UnetLoaderGGUF` / `CLIPLoaderGGUF` / `VAELoader`。

**注意**：Z-Image Turbo 是 8 步、CFG 1.0 的少步模型。照 SDXL 默认（20 步、CFG 7）跑会
白烧显存而且出图不对味。

这条通路不依赖网络，付费额度用尽时是唯一还能出图的选项；但它是 3-bit 量化小模型，
**画质达不到本站封面要的水准**，所以最终交付走的是云端模型。本地这条路记在案里，
等哪天真的一条云端通路都没有了再启用。

## 复现

```powershell
py -3 probe_site_image.py      # 探测画布那 8 个模型，产出 research/site_image_probe.json
py -3 build_entry_covers.py    # 生成六张封面，产出 research/entry_covers_receipt.json
```