# DramaAI / FastMovieAI → Video Kingdom 连动桥（v1）

本桥已经落到 `tools/import_workbench_package.py`，是现有 Video Kingdom 控制面的 intake adapter，不是第二套 Scheduler、Router 或 Provider runtime。

## 使用方式

```powershell
python tools/import_workbench_package.py --source <DramaAI 导出的 dramai-backup.json> --output episodes/imported/<project>
python tools/import_workbench_package.py --source <FastMovieAI 结构化导出.json> --kind fastmovieai --output episodes/imported/<project>
```

每次导入会生成：

- `workbench_intake.v1.json`：来源类型、源文件 SHA-256、数量和缺口；
- `episode_plan.json`：进入现有 `preflight_episode.py` 的计划入口；
- `six_module_contract.json`：脚本、镜头、表演、资产、编辑、恢复六模块旁路合同；
- `assets/`：仅 materialize 导出中明确提供的本地/base64 资产。

## 关键边界

- `production_integration=false` 固定保留；导入成功不是生产成功。
- TTS 未实测、对白未锁定、角色/场景锚图未审核时，状态保持 `INTAKE_PENDING` 或在预检中失败。
- FastMovieAI 的 PHP/MySQL/Redis/WebSocket 后端不被复制；只有显式导出的结构化数据进入该桥。
- Provider 任务必须继续经 Video Kingdom 现有 adapter、manifest、receipt、pacing/连续性审计和 ACE 回流。

## 当前判断

此前已经完成的是“流程参考”和 ACE/Video Kingdom 受控闭环；缺的是外部工作台产物的统一、可哈希、可预检入口。本桥补上了这个入口，但尚未证明任何外部工作台的实时后端已经接管生产，也没有伪造这种证明。
