# 《龙门战神》S01A 执行门只读核对

日期：2026-09-05（Asia/Shanghai）  
范围：只读核对现有 Provider/Agnes 入口、Shot Core、S01A 资产与 TTS 状态；未调用 Provider，未修改 runtime/pilot/manifest/旧 Take。

## 结论

**结论：阻塞（当前不可安全提交 Provider）。**

S01A 是无对白首镜，按导演包可不要求 TTS；它可以作为“单人、固定机位、久跪凝视、自然停留”的首镜候选。但现有 S01A contract 不能直接通过 Shot Core admission：

1. 现有 strict plan 将 `render.seconds` 设为 `3` 秒；`runtime/shot_core.py::preflight_shot()` 对 Agnes Flash 的硬范围是 `4–12` 秒，因此实测预检返回 `BLOCKED / render_seconds_must_be_4_to_12_for_agnes_flash`。
2. S01A 的本地场景/角色资产有 SHA-256，但现有 plan 只记录本地 `reference_path`，没有已验证的 Agnes 可消费公共 `provider_ref`。Shot Core pilot 的真实 reference 请求使用的是公共 URL；本地路径存在不等于 Provider 可读取。
3. strict plan 要求首态/末态可复核，但 S01A 没有 `last_frame_ref`；转换为 Shot Core 结构后预检给出 `last_frame_ref_absent_end_state_required` 警告。该项不是当前唯一硬错误，但在“自然停留、末态连续”要求下仍未闭环。
4. 旧 `novel-longmen-strict-30s-v3` 媒体/节奏通过不能替代新 S01A 的 admission、video_id、artifact hash 和逐帧/语义审计；导演包已将旧 v3 标为 `REWORK_REQUIRED / delivery_gate=BLOCKED`。

因此当前不能写“可执行”，也不能因 `AGNES_API_KEY` 存在就提交。准确标签是：**S01A 内容方向条件可执行；当前生产入口阻塞。**

## 已核对事实

### 导演约束

- `research/longmen_next_stage_director_packet_20260905.md`：S01A 主事件为“陆凡久跪凝视孤坟”；单人、荒山孤坟、自然停留；不得添加天气、季节、第三人物或内部切镜。
- 同一文件规定：对白镜必须有真实测量 TTS；无对白镜可先考虑环境/表演首镜；先只生成一镜并取得真实 `video_id`、原始回显、artifact hash、逐帧/语义审计。

### Shot Core / Agnes 入口

- `research/shot_core_production_pilot.v1.md`：真实链路为 Shot contract → hard preflight → Agnes Flash → video_id/poll → MP4/hash → machine QC → Vision/Director decision；Provider admission 只在 `CONTRACT_VALID` 后发生。
- `runtime/shot_core.py`：
  - 创建入口：`https://apihub.agnes-ai.com/v1/videos`
  - 轮询入口：`https://apihub.agnes-ai.com/agnesapi`
  - 模型常量：`agnes-video-2.5-flash`
  - API key 只通过环境变量 `AGNES_API_KEY` 读取；本次只做存在性检查，未读取或输出值。
- 当前环境存在 `AGNES_API_KEY`（存在性 FACT），但这不证明 S01A contract 合法、资产可传输或本次 Provider 可成功。
- `tools/run_shot_core_pilot.py` 会调用 `run_take()`；`run_take()` 在 preflight 不是 `CONTRACT_VALID` 时直接抛出 admission blocked，不应绕过该门。

### S01A 资产

来自 `episodes/generated/novel-longmen-strict-30s-v3/assets/` 的本地文件均存在并可哈希：

| 资产 | 文件 | bytes | SHA-256 |
|---|---|---:|---|
| CHAR_MAIN | `char_main_reference.png` | 1,984,649 | `29221a08d406df9ebbfd7c49e93dfceced7ba8eb27278f9e72abfb3d31fee085` |
| PROP_TOMB | `prop_tomb_anchor.png` | 2,369,371 | `a8ae90394e9ca02ebbf1f7e5cb8e8235044232e5ec17ea966ebe404ed0cf3138` |
| SC01 | `s01a_anchor.png` | 2,007,943 | `94accd3d7a4927a13ceb3161fa400398444624467b82731a9635b436f8e21894` |

注：文件存在和 SHA-256 绑定已证实，Agnes 公共 URL 消费能力未证实。strict plan 的 `required_asset_ids` 还列有 `CHAR_COUNTER`、`PROP_WINE`，但 S01A 屏幕允许人物仅陆凡；提交前应重新裁剪为当前镜头真正可见/必要的资产集合，不能把整集资产清单直接当作 S01A 绑定。

### TTS

- strict v3 的 `tts_measurements.json` 只对 S02A、S04A、S05A、S06A 记录 `MEASURED`；S01A 没有对白，`audio_status=NO_DIALOGUE`，没有“对白 TTS 未测量”的硬阻塞。
- 现有 Agnes 音频能力证据只证明已有视频存在 AAC 音轨；不证明对白可辨性或口型同步。S01A 应保持环境声/表演首镜边界，不虚构对白或 TTS 通过。

## 只读预检复现

以下命令只在内存中把现有 strict S01A 映射为 Shot Core 结构并调用纯函数 `preflight_shot()`，不调用网络、不写 manifest：

```powershell
cd C:\tmp\ace_video_kingdom_git
python -c "from runtime.shot_core import preflight_shot; ..."
```

复现结果：

```json
{
  "status": "BLOCKED",
  "errors": ["render_seconds_must_be_4_to_12_for_agnes_flash"],
  "warnings": ["last_frame_ref_absent_end_state_required"],
  "contract_render_seconds": 3.0
}
```

补充：仅把 `render_seconds` 改为 `4` 秒、补齐一个可复核 `last_frame_ref`，并在内存中绑定上述本地资产时，纯 `preflight_shot()` 可返回 `CONTRACT_VALID`。这只证明 schema/硬门可满足；由于 payload 会把 `provider_ref` 原样送入 Agnes，若这些引用仍是本地 Windows 路径，Provider 是否能读取仍是 `UNKNOWN`，不能据此提交。

## 补救条件（仍需新的明确生产授权）

要把 S01A 从“阻塞”提升到“条件可执行”，至少需要在不覆盖旧 Take/manifest 的前提下完成一个新的、版本化的 S01A contract：

1. 将静默表演时长改到 Agnes Flash 硬范围内（建议 4–5 秒，并明确自然停留/恢复预算；不是把旧 3 秒媒体冒充新证据）。
2. 为实际可见资产建立真实可传输的 `provider_ref`，同时保留本地路径、bytes、MIME、SHA-256；不能只写本地路径进 prompt。
3. 明确可复核的 `last_frame_ref` 或等价末态验证方案；固定机位、`internal_cuts=0`、单人 `visible_character_ids=[CHAR_MAIN]`，不得把黑雨、酒瓶等非屏幕对象误列为可见人物/动作。
4. 重新运行纯 preflight，只有得到 `CONTRACT_VALID` 才允许一次 Provider 提交；提交后必须保存真实 `video_id`、原始回显、artifact hash、媒体 QC、逐帧/语义/导演决定。
5. 任一 Provider 异常进入 `UNKNOWN_SUBMISSION`/`NOT_PROVEN`，先按 video_id/fingerprint 对账，禁止盲重发。

在上述条件满足前，S01A **不得提交 Provider**。旧 v3 的媒体通过、旧 `video_id` 或旧 artifact 均不能替代新镜证据。

## 证据路径

- `research/longmen_next_stage_director_packet_20260905.md`
- `research/shot_core_production_pilot.v1.md`
- `tools/run_shot_core_pilot.py`
- `runtime/shot_core.py`
- `research/shot_core_pilot_fixture.v1.json`
- `research/shot_core_pilot_manifest.v1.json`
- `episodes/generated/novel-longmen-strict-30s-v3/episode_plan.json`
- `episodes/generated/novel-longmen-strict-30s-v3/six_module_contract.json`
- `episodes/generated/novel-longmen-strict-30s-v3/tts_measurements.json`
- `episodes/generated/novel-longmen-strict-30s-v3/assets/`
- `C:\tmp\小说题材\龙门战神.txt`（SHA-256：`cc0eef87635f1fa5d93203d80ec4a7a4f52249eaea7dca9f1b8248677a7d132d`）
