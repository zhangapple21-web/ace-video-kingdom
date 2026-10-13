# 听荷轩 · 部署记录

本目录是《残荷诡影》的公开阅读与世界百科静态投影，不覆盖原始推演 Markdown，也不进入 Agnes 生产链。

## 已发布

- Pages 项目：`tinghe-archive`
- Pages 地址：`https://tinghe-archive.pages.dev/`
- 对外阅读入口：`https://studio.zhangningjing.com/dramai/`
- 路由实现：`proxy/` 中的 Cloudflare Worker，仅匹配 `/dramai/*`，其余 `studio.zhangningjing.com` 路径原样放行。
- 验收：首页、CSS、JS、`data/book.json`、首章和 `data/snapshot.v1.json` 均已从对外地址返回 HTTP 200。
- 首页封面：`public/assets/cover.svg`，由本地静态资源加载，不依赖外链。
- 全面升级页：`/upgrade`，已验证 Pages 与 `studio.zhangningjing.com/dramai/upgrade` 均返回 HTTP 200。
- 作品现场：`public/data/story-state.v1.json`，由 `tools/publish_tinghe_story_state.py` 从正式章节指针刷新；不读取或发布沙盒实验内容。
- 界面版本：2026-10-04 archive-v15（重做首页版面、阅读器、顶栏搜索、世界档案与原创桌封面；首页 JSON 从 ~650KB 降到 ~150KB）。
- **章节可被收录**：`build_chapter_pages.py` 为 248 场各生成一张真实静态页 `public/read/<id>.html`，Pages 以无扩展名 `/read/<id>` 对外提供，另有 `/read/` 静态目录。`sitemap.xml` 收录全部 249 条 URL（最近 30 场权重更高）。阅读器工具条与目录页都有「静态页 / 静态目录」入口。
  - **必须用无扩展名 URL**：同域名的另一个应用（无限画布）会在代理 Worker 之前抢走任何**已存在的** `.html` 路径——`/dramai/upgrade.html` 早已被它吞掉，而 `/dramai/upgrade` 正常。静态页内部链接、canonical、og:url、sitemap 一律写无扩展名形式。
  - 静态页正文直接来自 `public/data/chapters/*.json`，与 SPA 同一份源，不存在第二份正文；首屏前用一段内联脚本复用阅读器存的夜间/字号偏好，不加载 app.js。
- **章节正文修复**：`repair_chapters.py` 对比已发布章节与源脚本，只有两条规则，都保证不会丢弃已发布文字：
  - `POLLUTED` 正文混入来自 `c999` 摘要页、源场景里根本不存在的整句 → 可自动修复（`c198` 曾被整段「演化走向摘要」顶替，已修复并上线）。
  - `TRUNCATED` 只报不修。已发布快照来自更早的源状态，而源脚本已长到 5605 场；发布正文比当前草稿短属于正常漂移，擅自用新草稿覆盖等于改写已发布故事，属人工决策。当前 29 场属此类。
- **每日门禁**：`verify_originals_batch.py` 改为从 `originals_source` 推导期望值（不再写死「10 部 / 4 集」，此前每天要手工改数字，否则任务必失败）；`daily_originals.py` 新增 Gate 2b（`build_chapter_pages` / `build_site_meta` / `check_site_integrity`），并修复 Windows 下子进程输出按 GBK 返回导致 `UnicodeDecodeError` 在读线程里抛出、日志被静默吞掉的问题。
- 原创桌封面：`build_covers.py` 用 shenwen 适配器（默认模型 `gpt-image-2`）为每部作品生成一张竖版封面，输出 `public/assets/originals/<work_id>/cover.jpg`（600x900 JPEG，全 10 张约 1MB）。走 `production_control.privacy_scan` 门禁，非 PASS 不发请求。**封面不含文字**——图像模型渲染中文字形不可靠，标题由站点叠加。
  - 公开路径声明为 `assets.cover`：有 `originals_source` 的作品写进源文件由 `build_originals.py` 传递；只有 `desk.json` 的旧作品直接改 `desk.json`（构建器不重写旧槽位）。
  - 封面用 `loading="lazy"`，但 `app.js` 的 `promoteCovers()` 会在空闲回调里把仍未开始的图提升为 eager：部分加载器（含 headless Chrome）不触发 lazy 观察器，否则封面会整片空白。
- 验收：Lighthouse accessibility / best-practices / SEO 在 `/`、`#/read/<id>`、`#/world`、`/upgrade`、`/404.html` 均为 1.00（线上首页 SEO 0.83 仅因根域 `studio.zhangningjing.com/robots.txt` 被另一个应用的 SPA 兜底吞掉，`/dramai/robots.txt` 本身正确）。
- 缺页处理：`public/404.html` 自带内联样式，Pages 对未匹配路径返回**真 404**。此前没有该文件时 Pages 会把 `index.html` 以 HTTP 200 返回，任何坏链接都伪装成成功；前端 `data()` 因此额外校验 `content-type`，避免把页面当 JSON 解析。
- 原创桌同步：首页展示**全部**作品并按集数降序（`desk.json` 没有时间戳，集数是唯一的新旧信号），所以每日增量更新的作品会排在最前。

## 原创桌每日批量（域外星际）

- 稿件真源：`originals_source/<work_id>/work.json`。人工只写这里，脚本不生成情节。
- 构建：`py -3 build_originals.py`（`--check-only` 只报漂移）。渲染 `blocks` 为阅读器 HTML，写 `public/data/originals/<work_id>/epNN.json`，并对账 `public/data/originals/desk.json`。
- 三条硬性：确定性（同样输入字节一致）、幂等只增（已登载作品保留目录位置，只增新集）、失败即拒（缺标题/演员/集号断档/缺钩子/未知块类型都在写入前拒绝）。
- 验收：`py -3 verify_originals_batch.py`，检查 UTF-8、身份字段、单一场景标题、钩子收尾、无脚本标签、旧作品未丢失未重排、二次构建无变化。
- 每日入口：`py -3 daily_originals.py`。2026-10-03 起它自动 build+verify+`wrangler pages deploy`；退出码 0=已上线，2=构建或上云失败（日志在 `daily_run.log`/`daily_log.md`）。
- 上线（本机已可用）：`cd sites/tinghe-archive && npx wrangler pages deploy public --project-name tinghe-archive`。2026-10-03 已成功推送（见下方首跑记录）。

### 定时唤醒

- 本机已装 `opencode` CLI（v2.0.6，`~/.local/bin`），用它自动「唤醒」。
- 定时任务：`tinghe-daily-origin`（Windows 任务计划程序），每日 `08:00`（+08:00）触发，`WakeToRun` 开启，StartBoundary 2026-10-04。
- 触发命令：`py -3 run_daily_task.py`（**注意**：计划任务里注册的是这个 Python 包装器，不是 `run_daily.cmd`；后者只是当初的手动等价写法）。
- **写作步骤（Gate 0.5）在 `run_daily_task.py` 里**，调用 `opencode run --auto --file DAILY_DIRECTIVE.md`。仓库中只有这一步会新增集数；下游全部只做「投影 + 发布」。加 `.writing.lock` 文件锁，防止同一窗口内重复触发时两个 writer 同时改 `work.json`。
- 每次运行要做：① `--check-only` 校验现有稿；② 只增量续写（继续既有作品各 +1 集，或新开一部）；③ `build_originals.py`；④ `verify_originals_batch.py`；⑤ `daily_originals.py` 并把摘要追加到 `daily_log.md`。
- 产物日志：`daily_run.log`、`daily_log.md`。
- 今天首跑已验证：5 部域外星际作品各新写 ep04（共 20 集），并修掉 `desk.json` 不重写的别名 bug，验收 OK，退出码 2。

### 写作模型池（不固定单一模型）

- **不钉死模型。** 写作步按池轮换：`WRITER_MODELS` 默认 6 个免费模型，按「能否吃下 5 份 ~20KB 上下文包」排序，而非综合排名。
  - `opencode/nemotron-3-ultra-free` → `opencode/fledge-alpha-free` → `opencode/longcat-2.5-preview-free` → `opencode/muse-spark-1.3-contributor-free` → `opencode/mimo-v2.6-flash-free` → `opencode/nemotron-3.5-lightning-free`
  - 极轻量模型（`ling-3.x-flash`）排在最后或直接不用：上下文装不下，产出只会被审核门拦下，纯浪费一轮。
- 覆盖顺序：`writer_models()` 读环境变量 `TINGHE_WRITER_MODELS`（逗号分隔），留空则回落到默认池。改池不用改代码。
- 限流识别：`looks_rate_limited()` 匹配 `rate limit / 429 / quota exceeded / overloaded / resource_exhausted / try again later` 等。命中即**换下一个模型**，不重试同一个被限流的模型。
- `WRITE_TIMEOUT = 1800`（**每模型**，不是整轮）。限流模型是秒失败的，只有卡死的模型才会吃满预算，所以 6 模型 × 1800s × 2 轮 = 6h 上界，落在任务 `ExecutionTimeLimit` 之内。
- 自检：`py -3 test_writer_pool.py` —— 校验池格式/去重/环境变量覆盖、限流语料识别，以及**池中每个模型 ID 在 `opencode models` 里真实存在**（写错 ID 会静默浪费一整天）。

### 自检判据两次错判"今天成功了"（2026-10-08，11:00 那档实测）

- **11:00 那一档在生产上真的错了**：`[sync-check] shipped (receipt no-write -> DEPLOYED, delivered 0)`。
  一条 **没有新内容的 reconcile** 覆盖掉了早上那次"跳过写作"的记录，判成成功。
- **第二个坑**：判据只读新加的 `delivered_episodes` 字段，而 08:00 那条收据是旧格式、根本没这个字段——
  "读不到"被当成"交付了"。**这正是收据机制本身要抓的错误，结果自己犯了。**
- **修法**（两处都要）：
  - `day_delivered()` **扫全天所有收据**，不是只看最后一条。全天任一次 full/catchup 交付 ≥1 集即算送达；
    这样"真的交付了但后面跟了 reconcile"不会被忘，"早班停摆但后面跟了 reconcile"不会被误判成成功。
  - `delivered_episodes()` 加**集数差值回退**（`eps_authored_after - before`），旧格式收据也能算出来；
    完全没有信号才读作 unknown，且 unknown ≠ 已交付。
- `test_day_delivered.py` 11 项，用的是 2026-10-08 真实收据形状。
- **教训**：判据自己也要被证伪。"没读到数据"和"数据说是 0"必须分开——否则门禁在最需要它的时候变成橡皮章。

### 写作池按实测洗牌：逻辑模型退出正文，延迟只做平局分（2026-10-08）

- **实测**（bench_models.py，同任务 10 模型）：muse-spark 1058字/40s；fledge 1154字/381s；
  ling-3.1 964字/292s；nemotron-3-ultra 450字/46s（腰斩）；longcat 420s 无合法 JSON。
- **决定**：
  - nemotron-3-ultra **退出正文池**，保留审核池（逻辑是它的活，写长文不是）。一句话：不让逻辑模型填肉。
  - muse-spark 第一顺位，但**不是唯一**——单点锁死刚在 10-06 吃过 6 小时教训，轮换保留。
  - longcat 降到最后，一次样本不够放逐，第二次失败再隔离出主流程。
- **不同意的地方**：90 秒延迟一票否决太狠。生产侧单模型预算是以小时计且有静默检测，
  292 秒的合格交付当备胎完全可用。延迟只做同分时的排名分，不做否决；否决项只有两条：
  字数<800、无合法 JSON。`rank_models()` 把三轴（字数30/结构15+延迟15/AI味40）算成一张表。
- **没做的事**：few-shot 范本。muse-spark 那 1058 字的原文在这轮实测里丢了（所有输出共用
  一个 out.txt 被覆盖）——**没读过的稿子不能当范本**。已加逐模型存档，下轮跑完先读再定。
  机械合格 ≠ 写得好，这句话对范本同样成立。
- **大纲与台词分离**：暂不拆。当前单提示词（大纲+正文+JSON 一次出）muse-spark 已交付，
  拆两轨是管线重构，要等"单轨真不够用"的证据，不为架构而架构。

### 写作池换头：Muse Spark 1.3 提到第一位（2026-10-08）

- **原因**：它一直在池子里，但排第 4——机制是前三个失败才轮到它，等于给最能写的设了最高门槛。
- **证据，不是感觉**：EQ-Bench 创意写作榜上 Muse 家族（Spark 1.1，1916 分）是同档最强；且 2026-10-08 在本项目自己的写作任务上实测 **40 秒交了 1058 字合格稿**（结构全对）。旧排序的 "heavy/long-context first" 只是未经测量的猜测。
- **改法**：只换顺序，不动轮换机制。限流自动换下一个，单点卡死不了整天。`bench_models.py` 正在对全部 10 个免费模型做同任务实测，跑完按结果再调。
- 环境变量 `TINGHE_WRITER_MODELS` 仍可覆盖，不用改代码。

### 影子函数：旧 `split_verdict` 盖掉了真实现（2026-10-08）

- **现象**：`test_style_voice.py` 里"present 的过、缺省的全挂"——新字段写了能读，没写就没缺省。
- **根因**：文件里有两个 `def split_verdict`（第 55 行完整版、第 186 行旧精简版），Python 以后定义的为准，所以真正跑的一直是旧版：无类型清洗、无缺省值。我的 §7a 编辑加进了死代码。
- **为什么之前没发现**：`test_verdict_extraction.py` 12 项全过——因为它是在影子版上过的，期望值按影子的行为写的。测试通过不等于测的是对的东西。
- **修法**：删第 186 行旧版（先证明所有下游只读 `clean` 契约内的键：`check_style_contract.py`），把 `test_verdict_extraction` 里按影子行为写的期望改成按真实现（`bool(style)` 恒为 True，改断言 style 内容）。
- **教训**：重复定义是 Python 不报错的静默事故。`test_style_voice` 这种"缺省值测试"正是抓影子的网——如果当初给每个解析函数都写了缺省测试，影子活不过一天。

### 审核模型单点故障 → 全线停发（2026-10-07）

- **现象**：部署被反复拦下，`fanguan/ep08` 的审核报 `Error from provider (Console): Upstream request failed`，**重试两次结果一致**，不是瞬时抖动。
- **根因**：`run_audit.py` 用 `opencode run --auto`，由 opencode 自己挑模型。它挑中的那个 endpoint 在挂。而按设计**基础设施错误一律算 FAIL**（这是对的，fail closed），于是**一个死 endpoint 就能让全部发布停摆**，持续多久停多久。
- **区分错了两件事**：基础设施故障不是对本集的判决，它只说明「这一轮没有审核员」。正确代价是**换一个模型**，不是让整条管线停。
- **修法**：审核也用模型池轮换（`AUDIT_MODELS`，可用 `TINGHE_AUDIT_MODELS` 覆盖），基础设施失败（exit≠0 / 超时 / 起不来）自动换下一个模型；**全部模型都因基础设施失败才判 FAIL**，此时含义是「没有可用审核员」而不是「这集坏了」。
- 内容级判词（真判词）不受影响，一次判定即采用，不重复采样。

### 修复器的两个时间漏洞（2026-10-07）

- **等进程退出**：模型 16:44 改完 `work.json`，进程 17:01 还在跑 → 一次尝试白等 17 分钟。改成盯产物：内容变化后**静默 150 秒**即判定完成并 `terminate()`。降到约 5 分钟/次。
- **无进展不设上限**：实测有模型跑 16.5 分钟**一个字没写**，唯一终止原因是 30 分钟总超时 → 6 模型 × 16 集 = 每集白等半小时。加 `NO_PROGRESS_SECONDS=480`。
- **整轮要有界**：`--max-models`（默认 2）。六个模型跑十六集是数小时，而且晚修的和早修的结果无法区分；宁可让某一集**保持可见的隔离状态**，也不在没有边界的时间上耗着。

### 2026-10-07 每日任务失败复盘（Gate 0 崩溃 + 单模型超时）

- **现象**：08:00 任务触发但退出码 1，当天零新集；`work.json` 修改时间停在 10-06 19:16。
- **直接原因**：`originals_source/liufang/facts.json` 中柳湄的角色记录写成双重嵌套 `{"entry": {"name":…, "pronoun":…, "role":…}}`，而 `build_context_bundle.py` 用 `c['name']` 硬取键 → `KeyError: 'name'`。Gate 0 抛 `RuntimeError`，任务在 Gate 0.5 写作步**之前**就死了。
- **修法（三层）**：
  1. 数据：柳湄平铺；顺带修 `props` 里同款嵌套、且缺 `holder` 的「柳湄的回执」——这个坏记录之前一直被崩溃挡着看不见。
  2. 代码：事实表渲染改为先 unwrap `entry`，再对缺键记录**跳过并告警**，且被跳过的约束写进上下文包头（硬约束被静默丢弃和崩溃一样糟）。
  3. 编排：Gate 0 失败改为非致命（记录并继续发布），工作列表改为从磁盘 `discover_work_ids()` 发现，不再硬编码 5 个 id。
- **顺带发现（10-06 的独立故障）**：`run()` 传了 `timeout` 却没捕获 `TimeoutExpired`。写作步实跑 **6h11m**（08:00→14:11），`WRITE_TIMEOUT=3600` 没兜住，异常掀翻整个进程，写好的 4 集没走完发布——最后靠独立的 `tinghe-stale-watch` 任务在 14:00 救回。已改为捕获超时 → 返回 `code=124` 的失败步骤，让发布门继续跑完。任务 `ExecutionTimeLimit` 同时由 `PT6H` 放宽到 `PT12H`。
- **用户可见缺陷**：`status` 元数据与实际集数脱节（`liufang` 标 `EP01–08` 实为 9 集）。已加 `sync_status.py` 从集数派生，不信任手工元数据。
- **验证**：`test_run_bounds.py`（超时→124 / 正常→0 / 失败→3 三用例）、坏记录注入回归（`exit=0` + 告警 + 包照建）、全链路跑通并上线，线上 `liufang` 已正确显示 `EP01–09 可读`。

### 2026-10-07 审核门失效复盘（比"没更新"更严重）

- **现象**：`fanguan/ep09` 于 `14:40:50` 拿到 `FAIL`（TIMELINE_CONFLICT + 2×CLUE_MISPLACED），`14:41:49` 却 `状态: DEPLOYED` 上线。失败判词与上线相隔 59 秒。
- **机制**：`.pub_before.json` 是**单个共享、"消费一次"**的文件。08:00 的运行与一次并发运行竞争该文件，后者写入的快照里 `ep09` 已在 `public/`，于是管线认为"没有新集要审" → 审核集为空 → 门形同虚设 → 直接部署。
- **修复（三道）**：
  1. "新集"改用**三个基线取交集**：部署收据 `.last_deploy.json`（由部署本身写入，即"线上有什么"的定义）、`Gate 1` 的 `public/` 快照、`.pub_before.json`。**取交集而非并集**——并集会让投毒的那份赢，反而复现要修的 bug（已实测）。
  2. 增加**独立硬门**：新集在 `audit_failures.json` 台账中若无 `PASS` 判词（`PASS` 覆盖早前 `FAIL`），一律 `AUDIT_UNVERIFIED` 阻断部署。这道门不依赖"是否被判定为新"。
  3. `run_daily_task.py` 依次写 08:00 / 14:00 两个任务，二者靠 `.writing.lock` 跨任务互斥。
- **存量问题（需人工决策，勿自动处理）**：台账显示当前**线上已有 8 集带 `FAIL` 判词**（`fanguan` ep05/ep06/ep09、`liufang` ep06、`tingjijia` ep05/ep06、`tuiqun` ep05/ep06），另有 **27 集从无判卷记录**。新门只拦新增，存量需单独决定：全量复审后撤回不合格集，还是保留并接受。
- **验证**：`test_audit_gate.py` 用"投毒快照 + 坏部署前的收据"复现 14:41:33 的场景，确认 `fanguan/ep09` 仍被判为新集且被 PASS 门拦下。

### 2026-10-07 writer 挂死根因（不是限流）

- **实测数据**：后台那次运行 19.5 分钟只写 1 集；`run_daily_task.py` 进程 CPU **0 秒**、`opencode` 子进程 CPU **5 秒**，而 `fanguan` 已从 8 涨到 9 集——**活干完了，进程不退出**。10-06 的 6h11m 是同一挂死的放大版。
- **修复**：`_run_writer_model()` 不再等进程退出，改为 **Popen + 轮询集数**。一旦检测到树增长，给 `WRITER_EXIT_GRACE`(180s) 让它自行收尾，超时即终止进程树；全程无产出则 `WRITE_TIMEOUT` 截止返回 `124` 以便轮换模型。
- **输出改用临时文件而非 PIPE**：用 PIPE 时终止被孙进程持有句柄的子进程会让 `communicate()` 阻塞到自身超时（实测 10s 预算变成 30s）。文件不存在"被子进程持有"的问题。
- **"干净退出但零产出"不再报成功**：返回 `3`，否则调用方会把静默空跑读成正常（10-05/06/07 三天就是这么"看起来正常"却没产出）。
- **验证**：`test_writer_completion.py` 三种真实形态（写完挂死 / 秒退不写 / 永不产出）全部按预期判定。

### 可见性：更新状态上页面

- 新增 `desk_status.py` → `public/data/desk-update.json`，`原创桌`页首渲染状态条（`is-ok` / `is-warn` / `is-stale` / `is-new`）。
- **状态只认集数变化，不认文件 mtime**。建它时第一版用 mtime，当场被自己证伪：`sync_status.py` 为修 `status` 字段重写了全部 5 个 `work.json`，mtime 全变成当天，于是谎报"今日已更新"。现改为对比 `.episode_history.json` 里的**每日集数基线**。
- 未写入 `data/counts.json`：该文件被刻意做成无时间戳、字节确定（`build_site_meta.py`），加时间戳会破坏漂移检测。
- 状态刷新已挪到**部署之前**：原在 `finally`（部署之后）跑，导致每次上线的是上一轮的旧状态。
- **验证**：`test_desk_status.py` 钉死上述误报（重写 work.json 不算更新、真增集才算、待发布优先于已更新）。

### 主站改名「无限画布 → 老张大区」：已经在线，不要动部署

- **查证方式**：源码不在 `zhangapple21-web` 的任何仓库里（11 个仓库全是 ACE 相关），本机 `package.json` 全盘无引用，`*.js.map` 请求返回的是 SPA 兜底页（`<!doctype html`，6 KB），不是真 source map。**没有源码可改**。
- **浏览器实测**：`document.title` = `老张大区`，`meta description` = `老张的专属研究与画图空间`，`<h1>` = `老张大区`，正文里「无限画布」**0 处**。应用运行时已把品牌换成新名。
- **残留**：只有静态 `index.html` 里的 `<title>无限画布</title>` 和 `<meta description>一个无限画布创作工具>` 还是旧的——JS 一加载就覆盖，**读者看不到**。
- **为什么不去改它**：`config.js` 显示主站有 `/api/ai` Pages Function（生图/视频都走它）。为改两行 HTML 而重建静态树并 `wrangler pages deploy`，有可能打掉这些 Function；而且探测时 `_headers` / `_redirects` / `manifest.json` / `sw.js` 全部返回 **FALLBACK**——SPA 对任何不存在的路径都回 index.html + HTTP 200，**我无法区分「不存在」和「存在但看不见」**。这个盲区排除了安全重建的可能。
- **判定**：**正确等于好看**。用户要的是网站叫「老张大区」，这件事已经成立。为一个读者看不见的 `<title>` 去赌生产环境的 API，不划算。
- **留给源码持有者的一句话**：下次从源码部署时，把 `index.html` 的 `<title>` 和 `<meta name="description">` 改成「老张大区」/「老张的专属研究与画图空间」即可。bundle 里另有 3 处显示用旧名（`canvas.defaultTitle` / `canvas.title` / `export.defaultProjectName`），第 4 处在更新日志里**不要改**——那是历史记录，不是品牌。

### 审核判词会翻转：解除隔离需要「连续 PASS」（2026-10-07）

- **现象**：`tingjijia/ep05` 16:25 修好后审出 **PASS**，16:35 对**同一份文本**再审变成 **FAIL**。审核器是模型，判词有方差。
- **所以**：单次 PASS 不能作为放行依据。新增 `verdict.py`：
  - 每次判词记录 `content_sha`（被判文本的哈希）
  - `pass_streak()` 只数**同一文本**上的连续 PASS；文本一变，计数归零（**新文本是新问题，不继承旧信心**）
  - `settled_pass()` 要求 `STABLE_PASSES=2` 次连续 PASS 才算**settled**
  - 哈希之前的旧记录无法证明是同一份文本，`pass_streak` 直接返回 0
- **关键的不对称：settled 只管放行，不管上锁。**
  - 隔离中 + settled PASS → **放行**
  - 隔离中 + 单次 PASS → **继续隔离**
  - 在线 + 单次 PASS → **不动**
  - 在线 + FAIL → **隔离**
- **我在这条上犯的错**：第一版把 settled 规则**双向**应用，结果 26 集在线合格内容被隔离——因为旧记录没有哈希、算不出 settled。撤回内容不是安全默认，那只是另一个 bug。`test_quarantine_rule.py` 5 项专门钉住这个方向，含"在线+单次PASS 不得被锁"。
- **审计不可复现？实测过了，结论相反**：`measure_audit_variance.py` 对 4 集各审 3 次 = **12 次全部一致，零翻转**。之前看到的那两次翻转（`fanguan/ep08` FAIL→PASS、`tingjijia/ep05` PASS→FAIL）真实原因都是**输入变了**：前者 ep04 从被隐藏变为可见（上下文变），后者文本刚被修复过（内容变）。**给定同一文本 + 同一上下文，判词可复现。**
- 我先前断定"审核器是模型所以判词会翻转"下得太快。这个测量放在动手修 16 集**之前**——如果 FAIL 大量是噪声，修复就是在追移动靶，该如实说明而不是烧预算。实测结果相反，所以修是对的。
- 保留 `STABLE_PASSES=2` 的理由也因此改了：不是"审核器抖"，而是**把内容放回读者面前需要比维持现状更多的证据**。单次 PASS 是一个样本，两次才是确认。

### `opencode run` 写完不退出：修复器踩了同一个坑（2026-10-07）

- 修复器原本用 `subprocess.run(..., timeout=1800)` 等进程退出。实测：模型 **16:44 就改完了 `work.json`，进程到 17:01 还在跑**——一次尝试白等 17 分钟。
- 改成盯产物：轮询 `work.json` 内容，内容变化后**静默 150 秒**即判定完成并 `terminate()`。日志写明 `model finished its edit but did not exit; terminated after 320s`。
- 一次尝试从 30 分钟降到约 5 分钟。顺带发现机器上有约 20 个 30~150 分钟的孤儿 `python.exe`，来自早期几次运行泄漏。

### Bundle 里的硬编码特例会静默丢集（2026-10-07）

- `build_context_bundle.py` 有一条 `if p.name == "ep04.json" and not ep03.exists(): continue`。
- ep03 被隔离后，`fanguan` 和 `tingjijia` 的 **ep04 从上下文包里消失**——该作品之后每一集审核、以及每次修复都**看不见 ep04，且没有任何报错**。
- 已删除该特例。新增 `test_bundle_completeness.py`：逐作品断言 bundle 必须列出 `public/` 里的每一集，缺一即失败。

### 隔离不是流放：修复管线（2026-10-07）

15 集被隔离后暴露一个结构缺陷：**`run_audit.py` 只从 `public/` 读被审集**，而隔离集的文件按设计不在 `public/`——于是**被隔离的集无法被审核，也就永远无法修好放回**。隔离从「暂停」变成了「永久流放」。
- 修法：`run_audit.py` 在 `public/` 找不到时，回落到 `originals_source/` 的 `blocks`，用 `build_originals.render_blocks` 渲染成同样的 HTML 再审。**审核的还是读者会看到的文本。**
- `liufang/ep06` 靠这条被重新审核，拿到了真实判词——之前它的 FAIL 是审核器输出 JSON 解析失败（`Extra data: line 1 column 588`），**工具坏了，不是内容坏了**，而按设计解析失败一律算 FAIL，所以它一直挂着一个假原因。

修复管线 `repair_episodes.py` + `REPAIR_DIRECTIVE.md`：
- **修复者只拿到严格早于本集的前情**（复用 `prior_context`）。原缺陷就是审核把后文当前文；如果修复者也能看到后文，它会靠「改前情」来让本集说得通，而指令第 0 节明确禁止。
- **改之前先备份 `work.json`**——那是 authored 正文的唯一副本。
- **写完重新校验 schema**：合法 JSON 但块结构错了，仍然算修复失败（`validate_work` 查 kind 白名单、必填字段、首块必须是 `scene`、末块必须是 `hook`）。
- **PASS 才算成功**：模型自己在末行声称修好了不算证据，以复审判词为准。
- 每集最多轮换 6 个模型；耗尽后保留当前最优稿并如实报 `STILL_FAILING`。
- **本脚本不发布、不解除隔离**，交由外层流程决定。

### 每天自动同步：为什么以前要靠人提醒（2026-10-07）

- **今天 08:00 真的失败了**：`tinghe-daily-origin` LastResult=1，Gate 0 崩在 `liufang` 上下文包，什么都没发布。`tinghe-daily-catchup`（14:00）当天的时刻已过、任务还没建，**从未运行**（LastResult 267011）。于是一整天没有任何自动更新。
- **看门狗还报了 OK**：09:00 输出 `[OK] grew 79 -> 80`——它量的是**线上总集数有没有涨**，而那个 +1 是前一天余量 trickle 进来的。**用累计量推断某一天有没有产出，原理上就分不清「今天的活」和「昨天的尾巴」。**
- **修复**：不再推断，改为**收据**。
  - `run_daily_task.py` 在 `finally` 里写 `daily_receipts.jsonl`（date / status / ok / mode / 集数）。写在 `finally` 是关键：早期异常也会落一条失败记录。
  - 「今天成功没有」从推断变成查表；同一天**最后一条收据为准**，所以下午的补救成功会覆盖上午的失败。
  - 新增 `verify_daily_sync.py`：查收据 → 有成功就退出；正在跑就等（不撞车）；没有就自己跑补救；补救也失败就**把失败写到网站** `desk-update.json`。
- **补救窗口从 1 个变成 4 个**：11:00 / 14:00 / 17:00 / 20:00 全部跑 `verify_daily_sync.py`，全部 `MultipleInstances=IgnoreNew`。原来的 `tinghe-daily-catchup` 已删除（它只是裸跑补救，没有收据判断、没有等待、失败不上网站）。
- **失败必须让用户看见**：用户只读网站，不读日志。所以失败状态写进 `desk-update.json`，横幅直接显示「今日自动更新失败，已自动重试仍未成功」。
- **现状**：5 部作品 42 集全部有判词（27 PASS / 15 FAIL），15 集已隔离，线上 27 集，全部经 `check_live_truth.py` 确认**按 URL 不可达**（不只是从列表里消失）。

### 审核上下文把「后面的集」当前文（2026-10-07，最严重的一次）

- **现象**：复审存量时大面积 FAIL，判词自相矛盾。最直接的证据是审 `fanguan/ep05` 却输出 `"episode": "ep09"`，理由写着「新集接在 ep09 之后，却退回 ep05 的进度」——**审 ep05，把 ep09 当成了前文**。
- **根因**：`build_context_bundle.py` 按**作品**构建**一份** bundle（最近 3 集给全文，更早的只给标题），`strip_episode()` 只删掉**被审集自己**那一段。于是审 ep05 时，ep06/ep07/ep08 完整地留在「前文」区。判词里引用的 `evidence_before` 全是后面几集的正文。
- **为什么没早发现**：审核日志不报错，脚本 exit code 正常，`TIMELINE_CONFLICT` / `CLUE_MISPLACED` 这些码看起来都「像真的连续性问题」。**工具坏了但输出看起来很专业**——这比工具直接报错危险得多。
- **代价**：42 集中 18 集误判 FAIL，其中 7 集已被隔离下线并从线上撤掉。这是基于坏证据做的破坏性动作。
- **修复**：新增 `prior_context(context, ep_id, ep_no)`——删掉**编号 ≥ 被审集**的所有内容（正文段、摘要表格行、声明集数范围的表头），并在开头写明「上文全部是本集之前的前情」。审核路径从 `strip_episode` 换成 `prior_context`。
- **原则**：**审核的前情必须严格早于本集**，这比写作更严——写手需要知道后面有什么，审核器需要假装不知道。
- **作废**：`audit_failures.voided-2026-10-07.json` 归档了全部 44 条旧判词。台账清零重审。
- **验证**：`test_prior_context.py` 16 项，全部断言「没有任何 ≥ 本集的编号残留」，正反两向都测。

### 隔离机制（quarantine.json）

- **用途**：把「已发布但带 FAIL 判词」的集从读者侧移出，同时**保留稿件本体**。2026-10-07 发现审核门可被绕过，线上遗留 8 集带 FAIL；新门只拦新增，无法撤回历史。
- **行为**：`build_originals.py` 读 `quarantine.json` 的 `held` 列表，命中的集**不渲染到 `public/`、不从 `desk.json` 列出**，但仍留在 `originals_source/*/work.json` 里——那是唯一副本，连续性缺陷通常可修，删了就只能重写。
- **可逆**：从 `held` 里删掉条目即恢复上线，无需手工改任何生成物。
- **失败关闭**：文件损坏或条目缺 `work`/`episode` → 直接 `SystemExit` 中止构建。宁可停更也不发布一份"读不到排除名单"的内容。
- **BOM 宽容**：用 `utf-8-sig` 读。PowerShell 的 `Set-Content -Encoding UTF8` 会写 BOM，手工编辑的 Windows 控件文件大概率带 BOM；真正损坏的 JSON 仍然失败关闭。
- **入口已连通**：`daily_originals.py` 的「新集」判定已把 `desk.json` 的可见集考虑在内，被隔离的集不会被当成新集反复触发审核。
- **验证**：`test_quarantine.py` 11 项，含"默认不隔离""移出 desk.json""删除 public 文件""source 仍保留""清除即恢复""损坏文件阻断构建"。

### 2026-10-05 每日任务失败复盘

现象：08:00 定时任务退出码 1，`daily_log.md` 记 `BUILD_FAILED`、作品 `0 新 / 0 总`。`daily_run.log` 里 `[FAIL] daily_originals.py (exit 1)` 后面跟的是**一个空行**——真正的原因被吞掉了。

三个独立缺陷叠加：

1. **写作步骤被删掉了（根因）。** 13:29 那次日志还有 `Gate 0.5: Write next episodes` / `opencode_write_next`；13:42 起就没了，`run_daily_task.py` 的 docstring 变成 "New episode writing is done separately"，任务从「写 + 发」退化成「只发」。于是**定时任务在结构上已经不可能产出新内容**，而 `authored:` 计数仍按子进程输出解析，输出为空就记成 `0 总`。
2. **子进程输出被解码错误吞掉。** `subprocess.run(..., encoding="utf-8")` 未设 `errors=`，Windows 上子进程按 GBK 回中文时，reader 线程抛 `UnicodeDecodeError`，整段捕获作废 → 日志里只剩空行，无法定位。已改为 `errors="replace"` + 给子进程固定 `PYTHONIOENCODING=utf-8`（`daily_originals.py` 早前已修，`run_daily_task.py` 漏了）。
3. **日志函数自己会崩。** `print(line)` 在计划任务无控制台、继承 OEM 代码页时，输出子进程带来的 emoji/CJK 会抛 `UnicodeEncodeError`，任务在**部署已经成功之后**才以异常收场。已把 `print` 包起来；文件日志本就是权威记录。

另外把总数统计改为**直接数 `originals_source`**（`snapshot_counts()`），不再从子进程文本里 `int(parts[3])` 猜；原写法遇到 `authored: 5 works / 30 episodes` 时 `parts[3]` 是 `/`，会抛 `invalid literal for int() with base 10: '/'`（10-04 13:42 那次 EXCEPTION 就是它）。

新增开关：`run_daily_task.py --no-write`（跳过写作，仅校验发布）、`daily_originals.py --no-deploy`（跑完全部 Gate 但不推送）。全门禁本地实测 0.68 秒。

### 2026-10-05 补写第 07 集 + 自动链路修复

**补写内容**：五部各 +1 集，`originals_source` 现为 30 → 35 集，线上 `desk.json` 共 74 集 / 10 部。

| 作品 | 第 07 集 | 承接的钩子 |
|------|----------|------------|
| `fanguan` | 开价 | ep06「让主审当庭买这块地」→ 当庭开价，木牌背面落下一行三十亩二级可耕的收地价 |
| `liufang` | 补签 | ep06「第三层你一个人守」→ 旧伤名册里描过两遍的补记行，他补上第二个签名 |
| `tingjijia` | 工龄证 | ep06「它要载第二个去」→ 生保口下压着的工龄证，背面坐标就是第八码 |
| `tuiqun` | 沫翻 | ep06「灯熄了，沫还在」→ 无灯哑带里沫到即出，她在船舱开了那只筒 |
| `zhenqianjin` | 第二把钥匙 | ep06「另一把在令仪母亲的遗物盒里」→ 十八年前的收据，父亲的名字第一次被念出来 |

**审核结果**：五集全部 PASS 后发布（fanguan 终审 PASS 带 1 MINOR，按门禁规则放行；其余四部干净 PASS）。
中途被拦下并修正的真实硬伤（不是格式问题）：

- `liufang` 沈砺前文是「他」且是 **F 级犯人、没有工牌**，却写成「她」并给了白鲛工牌；案发是**三年前**，写成十二年；铁算盘的算盘 ep06 已压在骨架上，却又从怀里掏出一次。
- `tingjijia` 把签退役单的人写成「裴上校」——前文是**采购主官**，裴冷是另一角色；复核官裁定「**三日后**」移地，却写成「提前到明天」。
- `tuiqun` 火漆筒封档人是**沈铭舟的父亲**（老审查官，私印航灯纹），却写成姜父/苏父；裴家 ep06 已声明「第十一航次底档全卷在裴家手里」，筒里那份是**航行原档**，两者必须区分。
- `zhenqianjin` 阿禾是**养母**且是九年前下井的成年人，却被说成十八年前医院那个孩子；底册 ep06 在铁柜名章底下，缺了「谁动的」交代。
- `fanguan` 铁管蜡封 ep06 已当众拆开，却写「蜡封完整」；取证时间与 ep05「今晚取出」对不上；结尾把三年前那行数字暗示成与主审同一只手，与正文「写数字的是我姐」冲突。

以上全部固化进 **`DAILY_WRITING_NOTES.md`**，写作步骤每次都会带上该文件。

**顺手修掉的工具缺陷**（都是这次真实踩到的）：

1. `build_originals.py` **没写 `no` 字段** → `build_context_bundle.py` 按 `no` 排序，摘要表里所有集号都显示成 `ep00`。已补写，并给 bundle 加了按文件名回退取集号。legacy 五部 39 集也一并补齐（共 74 集体检 0 缺失）。
2. `run_audit.py` 审的是 `public/.../ep*.json`（**构建产物**），改完 `work.json` 不 rebuild 就审的是上一版——本次因此白跑两轮。现在上下文包会先剔除本集（`strip_episode`），避免审核把新集当自己的前文。
3. `run_audit.py` 的 `--timeout` 默认 **180 秒**太短，超时按 `CRITICAL` 计分，导致内容健康的集被判 FAIL。已放宽到 600 秒。
4. `audit_failures.json` 只追加不清理，修好的集永远挂在失败列表里。改为 PASS 时把旧记录标记 `resolved`。
5. `run_audit.py` 的 `subprocess` 同样缺 `errors="replace"`。

**审核门本身的两个缺陷（本次真实踩到，已修）**：

1. **Gate 3 从没跑过。** `daily_originals.py` 在 build **之后**才对比 public 找新集——build 永远先把新集写进去，对比恒为空，审核恒跳过（10-04 日志里已有两次因此空转部署）。已改为在 Gate 1 之前快照已发布集号（`published_episode_ids()`），Gate 3 对快照找新集。
2. **审核 judge 是随机的，单次 FAIL 不收敛。** 同一份 fanguan/ep07 半小时内先 PASS（1 MINOR），改两个词后 FAIL（3 条与上一轮互相矛盾），原字节重试又 PASS。已给 `run_audits` 加规则：FAIL 必须在**相同字节上复现**才拦单，否则记为噪声放行、两次记录都保留。不要用内容修改去追单次 FAIL——会无限循环。

**部署命令必须带 `--branch main`（2026-10-05 真实事故）。** 当天的补写批次构建、校验、审核全绿，`wrangler pages deploy` 也报告成功，
但线上纹丝不动：仓库 HEAD 停在 `fix/second-round-audit` 分支，wrangler 按当前分支决定环境，把包发到了 Preview，
Production 还停在旧版。`daily_originals.py` 的部署命令已固定 `--branch main`，以后分支再漂也不会静默发错环境。
排查时认准：`wrangler pages deployment list` 里 Environment 列是 Preview 还是 Production，以及代理 Worker 的
`x-tinghe-route` 头在不在（在 = 走了代理，内容来自生产别名）。

**自动链路**：Gate 0.5（写作）恢复并加固——`.writing.lock` 防重复触发并发写；若首轮产出 0 集则自动重试一次；写作失败不再中断发布；产出 0 集会明确记 `[STALL]` 并在 `daily_log.md` 写「写作:」行，不再伪装成正常的一天。新增 `run_daily_task.py --no-write`、`daily_originals.py --no-deploy`。

### 2026-10-05 夜 · 试跑 + 六项加固（用户逐条安排）

**1. 写作步骤试跑（唯一没实战过的环节）。** `run_daily_task.py --works fanguan --no-deploy`：
写出 fanguan/ep08「第二灶」（20 blocks，741 字，beat 紧接 ep07 钩子），只落盘未发布（GATES_OK，+1/36）。
过程发现并修复：①调用处漏传 `before` 参数，首跑必 TypeError；②作战指令让写作者自己跑 `daily_originals.py`（含部署），试跑会被后门发布——`--no-deploy` 时已约束写作者止步于结构校验；
③`--no-deploy` 成功时状态误记 DEPLOYED，已改为 GATES_OK。
试跑结论：写→检→审→停全链路通。ep08 审了三轮才过：首轮 PASS 但漏检了甄荟一句“我姐”（复核人是卢茨姐姐，属人物混同，人工补改）；
改后 FAIL 2 条全是真问题（场景头正午撞正文天刚亮；二级土养菜当天不可能有收成→改苗盘+卖土）；
终轮 PASS 带 1 MINOR（木牌措辞压缩，读者不可见，按规则放行）。
教训：审核会漏检（盲区实锤），人工抽查不可省；但也不要追小问题进随机 judge 的循环。

**2. 线上增长哨兵（防静默成功）。** `check_staleness.py` + 计划任务 `tinghe-stale-watch`（每日 09:00，15 分钟限时）。
直读生产域名 desk.json，对昨日总数：增长→更新基线；持平→STALE 记 daily_log 并 exit 1；
减少→REGRESSION；顺带验 `x-tinghe-route` 头（代理被旁路就拒比）。
基线：2026-10-05 线上 74 集。看明早 09:00 第一次真比。

**3. 部署后线上校验 + 回滚。** Gate 4 后 `verify_live()`：按作品逐个对线上集数 + 新集文件逐个 200，
6×30 秒覆盖传播延迟；收据 URL 解析进 `.last_deploy.json`，并经 wrapper 记入 daily_log。
Gate 1 前 `snapshot_public()` 全量快照 public/（留 5 份），`rollback_public.py --list/--rollback` 一键回滚并重发
（同样 pin `--branch main`）。另：部署命令已 pin `--branch main`（当日 Preview 事故复盘见上）。

**4. 噪声留档 + 拦截链实证。** 重试翻盘（FAIL→同字节 PASS）写入 `audit_noise_log.jsonl`（fail_issues + pass_issues 对照），
定期抽查重试政策是否放过真问题。用假 ep09 探针做过端到端验证：Gate 3 报“1 集待审”→首审 FAIL→重试 FAIL→
“复现阻断”→干净 exit 2，全程无 Traceback。探针还附带炸出真 bug：`run_audits` 把子进程输出字符串当 dict
用，任何一次 FAIL 都会崩——之前从没走到过（Gate 3 从没开火）。已修（审核脚本吐 `AUDIT_JSON` 行，管线解析），
探针重跑后拦截链干净。注意：重试翻盘（噪声记账那条）路径尚未实战，明日首批是第一次 live fire。

**5. 事实表。** `originals_source/<work>/facts.json` ×5：人物代词（逐句原文核定，未确立的霍泾/裴冷/阿柯/
复核官/采购/老工只许用名字职务）、数字（价格倍数只许十倍等）、时间锚、道具位置持有者、未回收钩子、
铁律。已接入 `build_context_bundle.py`（事实表节）与 `AUDIT_PROMPT.md`（第 0 条，优先级最高）；
写作者每批只许加不许改（见 DAILY_WRITING_NOTES.md 第七节）。

**6. 细节。** 锁加 6 小时 TTL（崩溃残留不再卡死未来）；计划任务限时查到是 PT2H（writer 1h + 管线 1h
零余量，一次重试就被杀），已放宽到 PT4H，内部超时保持收紧；写作是单 writer 会话串行（有意为之：
并行写 work.json 会冲突，且避开模型限流）；钩子储备见各 facts.json `open_hooks`（每部 3–4 条未回收，
够 ep08–10 用；tuiqun 复审 + zhenqianjin 认亲是最近的大梗）。

**试跑暴露的最大问题（已修，含教训）：** 试跑时 Gate 3 仍显示 No new episodes。真正原因是双重的：
①当时进程加载的可能是修复前代码；②更根本的——`works` 在 main 入口加载一次，写作新增的 ep08
根本不在内存目录里，新旧两版 Gate 3 都会漏（已改为 Gate 3 前重读源 + 打日志自证）。
ep08 今晚已手工审过（PASS+1 MINOR），明日 Gate 3 会跳过它（已在 public），只审新写的 4 集。

### 2026-10-05 夜 · 写作指南接入 + fanguan 重写试跑（未发布，等选用）

**接入内容**：指南第六节逐字写入 `DAILY_DIRECTIVE.md`(§8) 与 `DAILY_WRITING_NOTES.md`(§九），
程序比对过 431 字零差异。硬指标：1000～1500 字（替代旧 500–800）、低于 900 重写一次（`min_words` 进摘要）、
每集 ≥3 画面点自数。事实表/连续性/补齐规则保留；另加 `backup/` 禁区规则。

**文笔审核（只记录不拦单）**：`AUDIT_PROMPT.md` 加第 7 节（压憋破/对白设定/画面点/钩子留白/幽默/越界），
模型输出改为 `{fact, style}`，旧裸格式仍兼容（style 记空）。`run_audit.py` 吐 `AUDIT_JSON` + `STYLE_JSON` 双行；
管线解析 STYLE 并打印 `[STYLE] wid/ep words=.. visual=..`，wrapper 收入 daily_log。
唯一例外：`violation=true` 按硬 FAIL 拦单，同样走复现规则。

**试跑**：备份旧 ep08（源/public/desk/审核记录，`backup/ep08-fanguan-20261005-185102/`）后清出现场，
`--works fanguan --no-deploy` 重写。新 ep08「第二灶」1193 字达标。管线：快照递接生效
（using pre-write snapshot）→ Gate 3 报 1 集待审 → 首审 FAIL（木牌压缩 MAJOR，弱）→ 重试 PASS →
噪声记账（首条）。STYLE 两轮全绿（1430字/7画面，1450字/8画面）。

**污染教训（重要）**：新版与旧版骨架高度重合（存根/眉批八字/四楼）。查证：写作者按维护规则把旧 ep08 情节
写进了 facts.json，经上下文包喂回给自己——照做是正确的，错的是事实表混入了未定稿情节。
以后重写试跑前，必须先 strip 被替集对 facts 的贡献（条目都有 source 集号可查）；`backup/` 已立禁区规则。
facts 当前混有新旧两版共有骨架，待选用后按 picked 版本做一次小对账（新版改“简化版”措辞，旧版删办事员/三米线条目）。

**选用结果（新版）**：用户选新版。facts 已按新版对账（main 只留≤ep07 + 待确认区 13 条）；
终审在新链路上跑出干净 PASS（0 issues，STYLE 全绿，模型一次跟上 `{fact, style}` 新契约），
记录已打正；备份已删。另记：模型数字数每次都不同（1050/1430/1450），浮动约 ±20%，
字数是否达标永远以脚本实数为准，模型数只看量级。

### 2026-10-06 早 · 首批全自动运行（5 新集上线，包装器部署后静默死亡）

时间线：08:00 启动（源 36 集，含昨晚饭馆 ep08；预写快照 75 文件）→ 写作者补齐其余 4 部 ep08（源 36 → 40 集）→
Gate 3 第一次实战开火（预写快照递接生效，4 集逐审；此前从未真正触发过）→
4 集全部 PASS（09:21/09:25/09:28/09:30，各带 0–1 个 MINOR）→ 09:31 部署验证通过，
线上 74 → 79（收据 f9ae3e9a）。新集字数 1093–1219 全达标；STYLE：tingjijia humor=n，
zhenqianjin dumps=Y（只记录，未拦单）。

随后包装器死亡：任务返回码 -1，无 “Daily task finished”，无 daily_log 条目。
已排除重启（uptime 135h）、超时（PT4H）、OOM（会走 finally）。
晋升步骤跑完了（facts pending 已清空），死点在部署验证成功之后、日志落盘之前，
确切原因未明。daily_log 已按证据手工补记并标注。

连带教训与修复：
- 09:00 哨兵按设计等待 15 分钟，09:15 判 STALE 时仍是 74（部署 09:31 落地）——误报，
  机制对、预算差 16 分钟。预算保持 15 分钟（用户原定），误报可接受且自解释。
- 哨兵新增两条：①管线锁/当日未完工则等（已验证触发）；②起跑超任务限时 4h 视为幽灵，
  不再空等（否则死掉的包装器会让之后每次检查都等满 15 分钟——已实测卡住一次）。
- 哨兵新增：线上增长但当日无 daily_log 条目 → [WARN]（包装器静默死亡的专属信号）。
- facts 晋升在部署后自动跑通（13 条待转已清空，主 hooks 3→8）。

### 2026-10-06 午 · 包装器死亡复盘后的加固 + 事实表转正核验

**转正核验（用户要求今晨必做）**：五部 pending 全空，转正确实跑过。但转进去的有三处毛病，
已逐条对原文核实并修正：听荷军需官重复两条→合并；流放“旧上司/他”、真千金“清点官/他”
皆无原文依据（通篇裸名）→改 null；退婚“受理员”代词栏写的是说明文字→归一。
退婚两处压缩词（涂黑页/灯熄墨）已改回原文用词。数字时间锚抽查有原文出处。
结论：晋升只管“转”，不管“对”——转入条目仍须人工抽查，本次抽查方法（新代词逐条接地）
应作为每次大批量转正后的固定动作。

**包装器死亡后续（根因仍 open）**：已排除重启/超时/OOM；任务是 Interactive 登录型，
会话注销会杀进程，列为残留嫌疑但不盲动。改动方向是让死亡后果归零，而非继续赌根因：
- 部署后事项（转正、daily_log、收据）搬进 daily_originals 收尾；包装器只写写作纪要 checkpoint + 异常条目。
- 包装器写 `.heartbeat`（started/bundles-done/writing-done/pipeline-done）。
- daily_originals 所有非诊断返回点都写发布纪要（SETUP/BUILD/AUDIT/DEPLOY + 成功）。
- 干跑验证：`--no-write --no-deploy` 全绿，daily_log 零污染，心跳正常，快照已消费。

**哨兵预算 15→90 分钟**：09:15 误报证明 15 分钟不够（部署 09:31 落地）。锁在就等，上限 90 分钟；
锁消失仍无增长才 STALE。任务限时同步到 PT2H。

**补字质量抽查（用户要求）**：真千金（1162）法医事实密集，复述占比小；退婚（1093）程序质感+新线索密，
填充不可见。退婚有一处疑似错字（“我母亲的四艘请问题”），记一笔随缘修，不单独返工。
结论：补进去的是实质，不是废话；1000 字线没有逼出注水。

### 2026-10-06 下午 · 外部批量重构事故 + ep09 试写闭环

**事故（15:10:52 / 15:20:07 两波）**：仓级自动化（与根仓 "Fix Bug #9 atomic write / R7
subprocess timeout" 提交同源）扫过本目录，未适配站点布局：
1. 全部 `.write_text` → `atomic_write_text` 并加 `from tools.*` 导入，但 `tools` 包在仓根，
   本目录脚本解析不到 → 14 个文件 import 全崩；
2. 往 4 处 `subprocess.run` 插 timeout 时插成 `subprocess.run timeout=300,(` → 语法错
   （daily_originals / verify_originals_batch / build_covers / rollback_public）。
   300s 对审核还是错的：run_audit 内部模型超时 600s，外层 300 会把健康审核杀成假 FAIL。
3. `daily_originals.py` 缺 stdout reconfigure，直跑时 GBK 控制台打印 wrangler 的 ✨ 崩溃
   （包装器跑会给子进程设 PYTHONIOENCODING，所以只有直跑才踩到）。

**修法（结构性，不是逐点打补丁）**：
- 新建 `sites/tinghe-archive/tools/__init__.py` 转发包（`__path__` 指向仓根 tools/）——
  一处修复全部 14 个导入点，重构器再扫也不怕；仓根脚本继续用真包，互不干扰。
- 4 处语法错手修，daily_originals 的 run() timeout 定 900（> audit 600 + 余量）。
- daily_originals 头部加 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`。
- 验证：全目录 ast 0 错、全部模块 import OK、三门全绿、包装器干跑绿。
**教训**：仓级批量重构会漏掉 sites/ 下的独立布局；导入可用性要靠"结构性转发"兜底，
不能假设重构器知道你的包布局。另外 debug_one.py 顶层会跑 test/ep99 审核并写
audit_failures.json——**不要 `import debug_one`**（本次误 import 清了 1 条污染）。

**ep09 试写闭环（流放星狱 · 1191 字）**：用户逐条口授总纲（爽文奇思/科幻/动手/
智商与外挂/好色男主/绿茶女主/像人话/主观偏见瑕疵/手风琴句式）→ 建 `.opencode/
skills/tinghe-author` 创作者技能 + 指令 §9/笔记 §十 同源落档 → 试稿三轮改（AI 味→
人味→偏见瑕疵）→ 入 work.json + 6 条事实进 pending → build/verify → Gate 3 审核
PASS 0 issues（STYLE：10 字/10 画面点/pressure Y/hook Y）→ 部署 → 线上 80 集
（liufang 9）收据 fc18bb9a → promote_facts --apply 自动转正（pending 清零）→
daily_log 15:49:12 DEPLOYED。
**插曲**：首次部署其实成功但 verify/记账段崩在 GBK 打印（见上），修复后重跑
管线 exit 0 补齐记录——部署成功但落账失败的场景被现场复现并闭环了。

### 2026-10-03 批次

新增 5 部域外星际爽文，各 3 集，共 15 集：`liufang` 流放星狱捡漏、`tuiqun` 退婚当日航线归我、`fanguan` 垃圾星第一饭馆、`zhenqianjin` 真千金只想挖矿、`tingjijia` 我能听见机甲说话。

状态：**已同步上线**（2026-10-03 通过 `npx wrangler pages deploy public --project-name tinghe-archive` 推送，线上 `desk.json` 现为 5 部 + 5 部 legacy 共 10 部，5 部新作各 4 集 = 20 集）。`status` 字段已统一改为 `EP01–04 可读`。

## 页面分工

- `/`：书架（首屏封面 → 六条入卷路径 → 最近场次 → 作品现场 → 档案概览 → 原创桌）
- `#/catalog`：全部场次目录，支持按场次、地点、人物筛选
- `#/read/<id>`：阅读器（字号 A−/A+、夜间模式、章节目录抽屉、阅读进度条）
- `#/world`：人物、地点、事件、物件、关系五册（只保留有内容的维度，不再有待建页签）
- `#/desk`、`#/desk/<work>`、`#/desk/<work>/<pack|ep>`、`#/desk/<work>/asset-graph`：原创桌
- `/upgrade`：三源融合、Story Sandbox、生产链与首轮实验公开页
- 顶栏搜索（Ctrl/⌘ K）：跨场次、人物、地点、物件、事件、关系

## 公开层数据与构建

`build_site_meta.py` 从已发布快照派生三样东西，输出**字节确定**（不含时间戳，重跑无漂移）：

- `public/data/counts.json`：首页要的场次/档案计数（约 0.6KB）。**首页不再加载 `snapshot.v1.json`**
- `public/data/search-index.json`：顶栏搜索用的名称索引（约 95KB，首次打开搜索时才拉）
- `public/sitemap.xml`、`public/robots.txt`

```text
py -3 build_site_meta.py --check-only   # 只报漂移
py -3 build_site_meta.py                # 写入
```

`check_site_integrity.py` 是编码门禁：`public/` 下文本文件不得含 U+FFFD、BOM，且 CSS/JS 括号必须配对。**不要用 PowerShell 的 `Get-Content`/`Set-Content` 改这些文件**——曾经把 `index.html` 的 UTF-8 改坏过。

```text
py -3 check_site_integrity.py
```

`build_og_image.py` 用 PIL 画 `public/assets/og-cover.png`（社交平台不渲染 SVG 做 `og:image`）。产物已入库，只在标题或配色变化时重跑。

### 已知数据缺口

- `book.json` 的 `chars` 字段全为空，前端改为从 `preview` 的「在场：」行解析在场人物；249 场中 194 场可解析，其余（含 wave_38 之后与 `c198`）的上游 `preview` 已被剥掉该行，页面自动退回显示开场环境。
- `c198` 的正文被「演化走向摘要」污染（只剩一段环境 + 整段摘要）。真源在 `research/persona_dna_library/20260920_canheguiying_reincarnation_v2/world_live_full_script.v1.md`，**尚未修复**：单独重跑 `build_reader.py` 会重建全部 249 场，风险高于收益，需人工决定。
- `verify_originals_batch.py` 把 5 部新作的集数写死为 4；每日任务在增长后该断言会失败，属独立待办。

## 用户入口原则

首页是作品状态本身：正式场次、当前剧情、人物状态、主线冲突、伏笔回收和最新可观看内容都从 `story-state.v1.json` 展示。研究、推演、失败实验、检查和发布收据留在后台；只有经过人物动机、世界规则与因果验证的结果，才更新正式章节与公开状态。首页版面按此排序：正文优先，生产状态与原创桌靠后且压缩成入口。

发布前运行：

```text
py -3 check_site_integrity.py
py -3 build_chapter_pages.py    # 静态章节页，--check-only 只报漂移
py -3 build_site_meta.py --check-only
py -3 build_covers.py           # 只补缺失封面，已存在的跳过
py -3 repair_chapters.py        # 只报被污染的章节，--fix 才改写
py -3 verify_originals_batch.py
py -3 tools/publish_tinghe_story_state.py --check-only
py -3 tools/publish_tinghe_story_state.py
```

早期参考过 Quartz 5（https://quartz.jzhao.xyz/）的百科思想，但小说阅读入口保留独立阅读器，避免把章节侧栏化。

### 2026-10-10 夜：路由拆分、闸门盲区、审核伪造引用

**1.「等复审」被当成「有缺陷」送去叫作家改稿**

扣留名单里混着两类完全不同的集：一类是真缺陷（转折骨架超标、审核判失败），
一类是 `PASS_UNSETTLED`——审核只过了第一次，还没到第二次，正文没毛病。
修复器对两者一视同仁，都拼一份「修复提示词」丢给作家。

对第二类，作家正确地什么都没改（`blocks unchanged`），而 `repair_one` 在
「blocks 没变」时 `continue` 到下一个模型，**确认审核永远不跑**。于是这些集
永远卡在名单上。今晚 5 集 × 2 个模型，约 50 分钟生成量花在没坏的正文上，
并且留着一份「作家可能顺手改坏一章已通过正文」的风险。

改法：`needs_corroboration()` 按扣留码分流，`confirm_only()` 对未落定的集只跑
`run_audit.py`（不调作家），落定即放行；只有审核翻成 FAIL 拿到真缺陷，才轮到
作家。放行成本因此从「一次生成」降到「一次审核」。

顺带修了自己挖的坑：下午加的 `hold_reason` 给这类集套了「真正的问题是下面这条，
按它修」，后面跟的却是英文的「held back; repair scored PASS but not settled」——
**等于在叫作家去改一章根本没坏的东西**。措辞改成如实说明「没有剧情缺陷，
下面只是解释它为什么还在名单上」。

**2. 转折骨架闸门漏掉裸「但」**

```python
r"虽然[^。！？]{0,60}?(?:但是|可|却)"   # 没有「但」
```

标签写着「虽然…但是/可/却」，实际不认「虽然…但」——而那正是模型最常用的写法。
`liufang/ep11` 七处骨架里四处是「但」，闸门只数到 2，加一处「索性…干脆」共 3，
阈值是 `> 3`，**正好从门槛下溜过去**，带着七个骨架在官网上挂着，从没被扣过。

补「但」后重测：只影响 1 集。原有 17 项测试全用 `可/却/但是` 造句，**一句裸
「但」都没有**，所以这个洞活了很久。已补 8 项，用的是该集原句。

**3. 审核会伪造「前集钩子」，而且两次都拦住了部署**

`zhenqianjin/ep11` 与 `tuiqun/ep09` 先后被 `TIMELINE_CONFLICT` 判为「与上一集
逐字完全重复」，两次都拦下部署。核验（`compare_hooks.py`，直接打印两个 hook 块
原文对比）：

| | 实际相似度 | 最长共同片段 | 审计引用的「前集钩子」 |
| --- | --- | --- | --- |
| zhenqianjin ep10/ep11 | 28.9% | 5 字 | 两集里都不存在 |
| tuiqun ep08/ep09 | 31.9% | 25 字 | 是 ep09 自己的结尾 |

「逐字重复」两次都不成立，且引用的「前集钩子」都是**后集的结尾**——伪造引用的
signature 两次一致。但**节拍确有重复**（tuiqun 两集共用同一组三连问），所以处置
不是推翻判词，而是把这两集扣留，让它们不进这次发布。

教训：**闸门拦停流程是对的（fail-closed），但判词里的证据必须能核**。
审计的引文没有任何机器校验；`check_audit_evidence.py` 试过做这件事，在当晚被
删掉了——它在设计者手里连续三次给出错误答案（拿 blocks 原文比 HTML 渲染、
拿旧判词比已重写的正文、`evidence_after` 取错集），**反复给错结果的诊断工具
比没有更糟**。真要上这道校验，必须先在已知正反例上验证过。

**4. 一条有争议的判词会拦下当天整批发布（一个周期自愈，不必改门）**

部署门是全批 fail-closed：任何一集 FAIL，当天所有新内容都不发。今晚连续两次
卡在这里，线上停在 47 集不动。

**更正**：这一条原先写成「待决策项」，是本人没读代码就下的判断，读过之后不成立，
留着会让人去改一处已经处理了这个问题的代码。

`daily_originals.py` L444-449 已经把扣留集排除在审核集之外，注释写明原因：
被扣留的集是故意不进 `public/` 的，在这里审会因为文件不存在而失败，并挡掉一次
合法发布。所以循环是自愈的——放行 → 部署时审失败 → 重新扣留 → 下一轮排除。
每失败一轮多释放几集，不会永久卡死。今晚两次拦停正是这样把
`tuiqun/ep09` 和 `zhenqianjin/ep11` 收进名单的。

紧邻的 L450-461 记录了基线为什么取交集而不是并集：并集会让一份「错但偏宽」的基线
把全新的一集判成「已上线」，从而静默退出审核集。这段推理留在代码注释里，别让人
「简化」回并集。

### 2026-10-11 夜：类型漂移的发现、根因与修复

**用户先发现的**：「你的小说剧本现在已经偏向推理剧情了，现在年轻人可不天天给你看名侦探柯南。」

**量出来的**：五部作品从 ep05 起集体转向。五部同构——前 4 集是爽文节拍
（先问矿工欠了几个月工资、赔率最高时下坑、当众撕封条、一块钢板报出三十万），
之后每一集的 `beat` 变成「某份记录/某枚章/某行字对上了」。
52,871 字里程序词 175 次、爽感词 32 次。审核侧同期 41% 的判据是
CLUE_MISPLACED 与 TIMELINE_CONFLICT，**没有任何一条奖励爽**。

**联网查证**（`research/REFERENCE_MINES.md` 存了来源与边界）：
- 类型小说的目的是「用逆境向顺境的不断反转满足欲望」，不是苦难净化
- 三种章节模板里，**「信息揭露递进」是悬疑/解谜专用**——五部作品跑的就是它
- 「用冲突驱动代替时间线驱动」；剧情枯燥的解法没有一条是「多查一点证据」
- 追读率 top10% 平均 1.8 章一次情绪高峰；快慢节奏 3:1
- **升级体系不能没有**

**根因不在模型，在事实表。** `facts.json` 记 characters/numbers/timeline/props/
open_hooks/never，「升级、阶梯、对手、反派、地图、阶段」五部作品里 **0 次命中**。
每个字段只往一个方向拉——「不许弄坏」「必须收完」，没有一条说「这集必须比上集更难」。
`open_hooks` 更是主动把剧情往「查清楚」拉。

**四处修复**
1. `DAILY_DIRECTIVE.md` §8b：起承转爽四段硬要求、明令禁用信息揭露递进模板、
   爽点密度、延伸爽点、张弛 3:1、跨集升级。「这一集赢下来的东西要变成下一集
   她被压得更狠的原因」是全篇最重的一句。
2. `facts.json` 新增 `pressure` 段（opponent/stake/how_won/deadline/last_won/
   cost/next_must_differ），渲染在事实表**最前面**、`open_hooks` 之前。
   五条赌注经用户逐条确认后写入，全部锚在已上线集上。
3. `REPAIR_DIRECTIVE.md` §1b：重写型修复必须换脊梁并读压力轴。
   **这条是前提**——没有它，重写 40 集只会得到同样的程序味。
4. `genre_check.py` + 每日 15:10 计划任务：只报趋势不判定。
   仪器是词表、绝对校准差，所以只比方向；并报「压力轴是否为空」这个前置指标。

**闭环的一处漏**：`genre_status.json` 一开始**没有任何东西读它**——与当天下午刚修掉的
「失败横幅只写本地」完全同型。教训学到四小时后自己又犯了一遍。现已接入
`desk_status.py → desk-update.json → app.js`，生产域名直读可见。

**重写四集**（用户选定：按段落 ep08–12 候选 19 集，量测发现区内有部分已挺爽，
最终只取程序味压倒性的 4 集）：fanguan/ep08·ep09、zhenqianjin/ep08·ep09。
程序/爽感比全部从 8–9:1 降到 0.2–0.3:1，**四集 beat 全部换掉，逐集读过原文**。

**路上三个 bug，都是"看起来成功"的**
- 压力轴渲染插在 `def _flat` 之前 → bundle 崩 `UnboundLocalError`，
  而磁盘上的旧 bundle 让压力轴**看起来没写进去**
- 渲染漏了 `how_won`；空 `cost` 被静默省略（§8b 里代价是承重项，
  空着会被读成"没有代价"，正是让弧线重复的那个读法）
- **第一集重写 blocks 全换、beat 没换**。下一集的作家会在上下文包里读到旧 beat
  被拉回程序腔。现在 beat 未变即整篇退回重试

**顺带**：审核伪造「前集钩子」两次拦停部署，核验后确认引文两集都不存在
（zhenqianjin ep10/ep11 相似度 28.9%、tuiqun ep08/ep09 31.9%），
但节拍确有重复，故扣留不推翻判词。同时修复 `run_daily_task._terminate`
只杀直接子进程的问题（docstring 早已声称杀进程树），22 个孤儿进程已清理。

**待办（需要创作决定，不是我能拍的）**
- `fanguan` 与 `zhenqianjin` 的 `cost` 仍空着，bundle 每次构建都会喊
- 已上线 ep03–ep07 那一段仍是程序腔，未重写

---

## 2026-10-13：地区下架伪装成限流（记录于 2026-10-13 12:04），以及它怎么烧掉一整晚

### 现象

2026-10-12 20:00 起，连续两轮重写 4 集全部失败，20 次尝试无一成功，日志只写
`blocks unchanged`。2026-10-13 早上日更连续 `AUDIT_FAILED`，线上停在
`SYNC_FAILED`、68/70 集。门禁是 fail-closed 的，拦住了坏内容——**这部分是
对的**。

### 根因（三层，逐层剥）

1. **表层**：`muse-spark-1.3-contributor-free` 报
   `This model is not available in your country`。是**提供商按地区下架**，
   不是限流、不是额度、不是脚本坏。它当时排在写作池第一位。
2. **中层**：调用方把模型的错误原文整个丢掉，只打 `blocks unchanged`。
   于是 5 个不同模型报同一个错，被记成"5 次写作失败"，排查完全失去方向。
3. **底层**：`RATE_LIMIT_PATTERNS` 与新加的 `is_rate_limited()` 都不认这句
   报错。地区下架和限流的处理方式其实相同（都是"别再花时间在这个模型上"），
   但当时只列了限流的措辞。

### 更正（2026-10-13 晚）：那不是"地区下架"

上面第 1 条把 `muse-spark-1.3` 判为"提供商按地区下架"并移出池子，**这个判断是错的**。
用户测试下来：当时只是临时切到了香港地区出口，恢复原地区后模型立刻可用。

**教训比结论重要**：一条 `not available in your country` 的报错，既可能是模型被
下架，也可能只是出口变了——而这两种情况的处置正好相反（前者要移除，后者重探一次
就好）。我拿一次探测结果就改了默认池，等于让一个能用的主力因为一次网络抖动下线。

判据应该更严：**地区类报错不下结论，先重探一次、隔一段时间再探一次，两次都失败
才当不可用**。同时，默认池不应该因为单次探测就被删条目——探测是瞬时事实，池子是
常驻配置，把瞬时事实写进常驻配置就是让噪声改配置。

`test_pool_unavailable.py` 现在断言 muse 仍在池内，就是为了防止这条错误结论
被当成既定事实固化下来。

### 修的四处

1. `repair_episodes.model_said()` —— 失败时把模型原话打进日志。这是这次排障
   唯一的线索来源，之前被丢弃了。
2. `is_rate_limited()` / `quota_exhausted()` —— 区分「限流（等 45 秒）」与
   「日额度见底（等也没用）」，后者直接换模型不空等。
3. 两处识别表都加入 `not available in your country` / `model not found`。
4. `probe_pools.py` —— 开跑前每个池只打一句最便宜的探测，结果写
   `writer_pool_probe.json`；重写脚本 `--skip-spent` 读它并跳过花完的池。
   昨晚那种空烧，应该只花 1 次探测 + 0 次空烧。

### 测试抓到的真误伤（差点放过去）

正则收紧前，`test_pool_unavailable.py` 抓到「个人额度已用完」「读者额度排行榜」
这类**中文剧情正文**会被当成 API 报错——一旦命中，日更会把正常的稿子当成死池子
跳过。现在错误词必须带报错短语（`quota exceeded` / `超出配额`），裸的
「额度」「配额」不算。10 条中文诱饵全部不误伤。

这一条比前四条都重要：**识别池子故障的模式，跑在以中文正文为主的模型输出上。**
写得越宽，越容易把好稿判成坏池。

### 池子现状（2026-10-13 实测）

| 模型 | 状态 |
| --- | --- |
| `opencode/muse-spark-1.3-contributor-free` | **地区下架，已移出默认池** |
| `opencode/step-5-preview-free` | OK，新主力 |
| `opencode/ling-3.1-flash-free` | OK |
| `opencode/mimo-v2.6-flash-free` | OK |
| `opencode/nemotron-3.5-lightning-free` | OK |
| `opencode/longcat-2.5-preview-free` | OK |
| `amd/*`（六个共用一池） | OK，但 $1/天，只派简单活 |

明细与使用规则见 `research/WRITER_POOL_STATUS.md`。

### 没做完的

- `open_hooks` 的问句措辞本身还没改写（只在渲染层标注了「这是筹码不是本集
  任务」）。这是漂移的原始拉力，仍在。
- fanguan 仍有 5 组重演事实卡在 pending，等各自达标时由同前缀查重取较新版；
  「哪版是当前」需要读剧本，机器不替人判。
- UI 改版（新国风 + 暗黑微光、悬浮毛玻璃导航、继续阅读主视觉、目录提密度）
  已完成并本地验证，因内容审计未过而**未能上线**。等内容修完一起发。

---

## 2026-10-13 补：审计晚于发布（记录于 2026-10-13 12:32），扣留名单没被重算

### 现象

三集已上线的正文带着 FAIL 判词，且不在扣留名单里：`fanguan/ep15`、
`liufang/ep15`、`tuiqun/ep14`。读者拿到的是有连续性硬伤的文本。

### 时间线

| 时刻 | 发生的事 |
| --- | --- |
| 08:28 | `build` 生成 `ep15.json` 等并上线 |
| 08:57 | 部署链因 AUDIT_FAILED 整条停下 |
| 09:05–11:26 | 各集陆续被审计判出真问题（ep15 两集各 3 条） |
| 11:17 | `liufang/ep15` 判 FAIL，3 个真问题 |
| 之后 | 没人再跑 `apply_quarantine.py` |

### 为什么门禁没挡住

**门禁每一步都是对的。** 审计判了 FAIL 是对的，部署停下是对的。错的是：
`apply_quarantine.py` 只在部署链里跑一次，而部署链在审计出结果**之前**就停了。
扣留名单本身没错——它只是**再也没被重算过**。

这不是"检查写错了"，是"检查没在正确的时机再跑一次"。这类洞比逻辑错误更隐蔽，
因为每个部件单看都对。

### 修法

`test_no_leaked_failures.py` 把不变量直接写成断言：
**`public/data/originals/` 里每一集，若最新判词不是 PASS，就必须在
`quarantine.json` 里。** 接进 `land_it.py`，位置在 `apply_quarantine` **之后**——
一个负责生成名单，一个负责验证名单完整，职责不同。

它只报告不改名单：下架已发布内容是 `apply_quarantine` 的权限，因为 settled-PASS
释放规则住在那里，一个只报告的检查不该有那个权力。

### 顺带修正的一条认知

**探测通过 ≠ 写得动整集。** 2026-10-13 修 `fanguan/ep11` 时，step-5 与 ling
探测都显示 OK，真实写作却各跑满 480s 零输出；mimo 160s 改完并直接 audit PASS。
所以 `WRITER_MODELS` 的顺序按"真跑过一整集"排，不按"探测通过"排——否则每集要先
浪费两个 480s 才轮到能写的那个。

这一列只能靠实写填，没有捷径，也别用探测结果冒充。

---

## 2026-10-13：两个模型落错位置的修复稿，我删了却没备份

### 发生了什么

`repair_episodes.py` 报 `tuiqun/ep14: blocks unchanged`，但日志里 nemotron 明明写着
它把「你父亲补字」改成了「沈父补字」——正是判词要求的那一处。排查发现两个模型都
把完整修复写进了**新文件**而不是 `work.json`：

- `_ep14_tuiqun_fix.json`（21 blocks）
- `_ep14_fix.json`（25 blocks + beat）

这是"声称改了却没落盘"的加重版：内容对，落点错。修复提示词当时没有告诉模型该改
哪个文件，已补（见 `repair_episodes.py` 提示词）。

### 我的失误

我判断这两份不该采用（比 live 版本短 251 / 221 字，`_ep14_fix.json` 的结尾照搬了
ep13 的钩子，而 live 版本解开了"鞋为什么在四楼"），判断本身我复核过，站得住。

**但我的操作是错的。** 一条命令里先 `Copy-Item` 备份再 `Remove-Item` 删除，
Copy-Item 因路径参数写错整体失败，而同一条命令里的 Remove-Item 已经执行完——
结果不是"删除并归档"，而是**直接删除**。两份文件没了，备份目录里也没有。

### 影响与教训

内容损失为零：两份我都完整读过并判定不采用，判定依据写在
`inspect_stray_fixes.py` 里，可以重跑复核。

丢的是**复核的能力**：模型对自己改了什么的那份说明没有了，将来若想推翻今天这个
"不采用"的结论，只能重新推理，不能回头看它当初怎么说的。

教训和今天早些时候那次是同一个：**清理步骤必须能报告自己的失败**。
把"删除"和"归档"放在同一条命令里，等于假设备份一定成功——而这一步正是整个操作
唯一没有可逆性的部分。正确做法是先单独备份、确认备份存在，再单独删除。
