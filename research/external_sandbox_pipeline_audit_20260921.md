# 沙盒人格矩阵短剧管线外部清单审计（2026-09-21）

## 结论

这份清单有参考价值，但不能按“8 个节点直接拉取并接入”执行。它混合了真实仓库、研究模型、整套工作台、提示词集合和无法核验的名称，并把若干许可证/能力写得过于乐观。

当前只吸收三类方法：

1. Story Claw 的阶段化资产、角色音色映射和 VLM 首尾帧复核思路；映射到现有 Identity/State/Scene State/Shot State、voice registry 和 QC，不接管 Agnes 入口。
2. awesome-seedance 的镜头提示词组织和反例素材；仅作为导演参考矿，不引入 Seedance Provider。
3. ArcReel 的可恢复任务、版本回滚、费用/供应商可观察性；只提取字段和测试思路，不复制 AGPL 代码。

## 逐项核验

| 清单名称 | 实际核验 | 决策 |
| --- | --- | --- |
| Toonflow.NET | GitHub API 未找到同名可核验仓库；不能确认来源、代码或 MIT 许可 | `REJECTED_UNVERIFIED`，不接入 |
| AMAP-ML/DreamX-World | Apache-2.0，真实项目是交互世界模型；官方说明 5B 推理约需 38GB 显存，长时版本约 40–72GB，非“场景全景图模块” | `RESEARCH_ONLY`，不进入 RTX 3050/Agnes 主链 |
| ZeroLu/awesome-seedance | MIT 的提示词/资源汇编，不是渲染 SDK；外链提示词和素材不因仓库 MIT 自动获得再许可 | 吸收导演提示词结构，保持 Seedance 参考矿 |
| Tencent-Hunyuan/HY-Motion-1.0 | 文本生成 3D 骨骼动作，模型表列最低约 26GB 显存；仓库未声明标准 MIT/Apache 许可 | `RESEARCH_ONLY`，不作为真人视频动作 Provider |
| ZC89757/story-claw | MIT；Windows + ComfyUI/LTX 工作台，包含阶段化角色/场景资产、角色 voice map、VLM 首尾帧评分和失败重生 | 吸收方法与字段，不替换统一入口 |
| AI168（清单所称渲染管线） | 未找到“AI168 漫剧渲染管线”对应仓库；可找到的 `1213912309/ai168-comic-react` 是低活跃度 Apache-2.0 漫剧前端，不足以证明清单能力 | `REJECTED_MISNAMED`，不接入 |
| chatfire-AI/huobao-drama | README 标注 CC BY-NC-SA 4.0，不是 MIT；依赖 Huobao API/平台配置 | 只参考 UI/任务分层，禁止进入商用生产代码 |
| yihao-meng/CausalCine | 仓库无可核验开源许可，README/项目页偏研究展示 | `RESEARCH_ONLY`，不复制代码或模型 |
| ArcReel/ArcReel | AGPL-3.0 的完整自托管工作台，不是可拆的“调度模块”；网络提供也可能触发 AGPL 合规义务 | 只吸收可恢复队列、版本/成本收据思想，不接入源码 |
| Mixamo | 清单标为 CC0 不正确；应按 Adobe/Mixamo 条款和具体资产授权处理 | 不登记为 CC0 动作库 |

## 与现有视频王国的接口边界

- 不新增第二套“结构化叙事 JSON”。现有剧本、资产、镜头、音频和收据合同已经承担接口职责；外部字段只做映射。
- 不新增 Story Claw/ArcReel/Huobao 旁路入口。统一入口仍是 `video_kingdom_entry.py → production_shot_gate → Agnes`。
- 不把“角色四视图”“每镜首尾帧”“预制场景图库”升级为全局开拍门票；它们只能按项目/镜头风险启用。
- 不把外部仓库声称的 90% 良品率、日产 10/50 集等宣传数字写入验收标准，必须用本地 baseline/change/test/evaluation 证明。
- 不把 DreamX/HY-Motion 当作本地 GPU 可用能力；若未来做远程实验，必须单独登记运行资源、模型许可和结果收据。

## 可落地的最小吸收

下一次视频流程可直接复用的不是外部代码，而是四个字段/检查点：

1. `character_stage_id` / `scene_stage_id`：只有服装、道具、时间光线等确实变化时才开新 Stage，避免每镜重画或身份漂移。
2. `voice_map[character_id]`：整剧锁定角色音色，换音色必须产生新版本和原因。
3. `vlm_readback`：首帧/尾帧检查主体一致、额外人物、残字/幻字和场景连续性；只作为 QC 证据，不替代创作审片。
4. `retry_reason` / `rollback_to` / `provider_cost`：失败重做、回滚和成本可追踪，接入既有生成收据，不新建调度系统。

上述字段先以现有合同的可选字段/收据扩展实现，经过本地验证后再考虑升为默认；不直接安装外部项目。

