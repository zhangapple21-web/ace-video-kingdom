# 角色一致性渲染器就绪度（2026-09-01）

这是一次只读环境普查，不是安装记录、能力声明或生产接入。

## 已确认

- GPU：NVIDIA GeForce RTX 3050，6 GiB 显存；普查时约 4.1 GiB 空闲。
- Python：3.11.9；`torch 2.6.0+cu124`；`torch.cuda.is_available()` 为真。
- 驱动报告 CUDA 12.4；本机未检测到 `nvcc` 或 Conda。
- C: 可用磁盘约 46 GiB；`ffmpeg 9.0.1` 已存在。

## 未检测到

- ComfyUI、ComfyUI_IPAdapter_plus、IPAdapter 权重或已配置工作流；
- IAMFlow、Wan、Qwen-VL/LLM 依赖、模型权重或可复现环境；
- `diffusers`、`transformers`、`safetensors`、`xformers` 等目标栈基础包。

## 结论

`PyTorch + CUDA` 可用，**不等于** ComfyUI/IPAdapter 或 IAMFlow 可以运行。

- IAMFlow 保持 `RESEARCH_CANDIDATE_PENDING_ENVIRONMENT_PROBE`：6 GiB 显存与未安装目标栈不足以支持其长叙事身份记忆路线；本轮不下载权重或安装依赖。
- ComfyUI/IPAdapter 若未来验证，必须在隔离目录做静态图 A/B；只使用项目生成的虚构角色参考资产，测量显存、耗时与身份一致性，再决定是否保留。
- Agnes 仍是已验证的约 5 秒叶片镜头渲染器；它的参考图输入、锁脸、图生视频、首尾帧与音画同步仍是 `UNVERIFIED`。

## 未来最小验证

1. 在隔离目录安装固定版本，而不是向 ACE 或本仓库应用代码嵌入 GPL 组件。
2. 对 `CHAR_001` 的已批准参考图生成两组静态关键帧：有/无参考约束。
3. 记录模型版本、输入参考 SHA-256、显存峰值、耗时、输出 SHA-256 与人工连续性结论。
4. 只有一致性改善且可重现，才把该路线升级为可用的主线候选。
