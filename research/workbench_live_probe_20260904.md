# DramaAI / FastMovieAI 工作台 live probe（2026-09-04）

## 结果

### DramaAI

- 源码：`C:\tmp\dramai-source`
- `npm run build`：通过（TypeScript + Vite，2148 modules transformed）。
- 当前定位：可作为轻量工作台/导出端；导出仍必须通过 `tools/import_workbench_package.py` 进入 Video Kingdom 的 manifest、TTS、连续性和交付门禁。

### FastMovieAI

- 用户拉取源码：`C:\tmp\fastmovieai-latest-20260904`
- 本次 `npm run build`：未通过，原因是本地工作区缺少 `fastmovie-vue/node_modules/.bin/vue-tsc`；构建脚本还更新了该工作区的版本元数据，未对其做回滚，避免覆盖用户已有改动。
- 已有独立副本 `research/external_repos/FastMovieAI` 曾完成前端构建，但该副本与用户拉取目录不是同一工作树，不能把两者结果混写。
- 后端仍需要 PHP 8.1+、Composer、MySQL、Redis、WebSocket；当前不把 FastMovieAI 当作本机生产运行时。

## 连动验证

- `tests/test_workbench_import.py`：DramaAI 备份和 FastMovieAI 结构化导出均能进入 hash-bound `workbench_intake.v1.json`。
- 导入包固定 `production_integration=false`、`RESEARCH_ONLY/INTAKE_PENDING` 边界，未创建第二套 scheduler/router/provider runtime。
- Provider 调用、`video_id`、产物 SHA-256、pacing/连续性审计和 ACE 回流仍只由 Video Kingdom 现有控制面负责。

## 结论

工作台与 Video Kingdom 已有一个可测试的 intake 连接，但“工作台实时后端接管生产”尚未成立。DramaAI 当前适合作为可运行的前端/导出工作台；FastMovieAI 继续作为流程参考，待依赖和后端环境可复现、并完成一次真实端到端 receipt 后再评估升级。
