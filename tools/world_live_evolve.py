"""荷园世界活体演化：免费矿池优先、付费兜底，分波连跑；不列分支、不进生产。"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
import time
import urllib.error
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from production_control.model_transport import post_chat_completion

MODEL = "grok-4.7"
# 写稿付费兜底只走已核对更便宜的 grok-4.7。免费矿池仍优先。
# deepseek-v4.1-flash 与已退休的 grok-4.6 不得再进这条链路。
WRITING_EXCLUDED_MODELS = [
    "deepseek-v4.1-flash",
    "grok-4.6",
    "grok-4.5",
    "gpt-5.4-mini",
    "gpt-5.4",
    "gpt-5.5",
    "gpt-5.6-terra",
    "gpt-6-astra",
]
DEFAULT_LIB = ROOT / "research" / "persona_dna_library" / "20260920_canheguiying"
LIB = Path(os.environ.get("WORLD_LIVE_LIB", str(DEFAULT_LIB))).resolve()
PRIOR_LIB = Path(os.environ["WORLD_LIVE_PRIOR_LIB"]).resolve() if os.environ.get("WORLD_LIVE_PRIOR_LIB") else None
SCENE_RE = re.compile(r"^第\s*(\d+)\s*场", re.M)
CLOSED_MARKERS = ("收束：CLOSED", "开门还是收束：CLOSED", "世界开门还是收束：CLOSED")

# CREATOR_LIVE only: a short provider outage must not discard an otherwise
# resumable world run.  These are deliberately local to this runner and do
# not alter the production provider/router policy.
TRANSPORT_RETRY_ATTEMPTS = max(1, int(os.environ.get("WORLD_LIVE_RETRY_ATTEMPTS", "6")))
TRANSPORT_RETRY_BACKOFF = max(1.0, float(os.environ.get("WORLD_LIVE_RETRY_BACKOFF_SECONDS", "5")))
TRANSPORT_RETRY_MAX_DELAY = max(
    TRANSPORT_RETRY_BACKOFF,
    float(os.environ.get("WORLD_LIVE_RETRY_MAX_DELAY_SECONDS", "120")),
)
WAVE_REPAIR_ATTEMPTS = max(1, int(os.environ.get("WORLD_LIVE_WAVE_REPAIR_ATTEMPTS", "3")))
WAVE_RETRY_BACKOFF = max(1.0, float(os.environ.get("WORLD_LIVE_WAVE_RETRY_BACKOFF_SECONDS", "15")))
WAVE_RETRY_ATTEMPTS = max(1, int(os.environ.get("WORLD_LIVE_WAVE_RETRY_ATTEMPTS", "3")))
PROMPT_LAST_WAVE_CHARS = max(6000, int(os.environ.get("WORLD_LIVE_LAST_WAVE_CHARS", "14000")))
PROMPT_PRIOR_REF_CHARS = max(8000, int(os.environ.get("WORLD_LIVE_PRIOR_REF_CHARS", "18000")))
WAVE_FIELD_ALIASES = {
    "TIME": ("时间：", "时段：", "时间段："),
    "PLACE": ("地点：", "场景：", "位置："),
    "PRESENT": ("在场：", "在场人物：", "人物："),
    "STATE": ("人物状态：", "状态："),
    "RELATION": ("关系：", "关系状态："),
    "HAPPENED": ("已发生：", "发生：", "世界状态：", "本场变化："),
    "UNRESOLVED": ("未解决：", "未决：", "待解：", "问题：", "未解异常或因果缺口：", "未解：", "因果缺口："),
    "PROPS": ("关键道具：", "道具：", "物件："),
    "ONE_LINE": ("一句话：", "一句："),
}


def _key() -> str:
    return (
        os.environ.get("ONEAPI_LOCAL_MASTER_KEY")
        or os.environ.get("ONEAPI_ADMIN_TOKEN")
        or os.environ.get("ONEAPI_KEY")
        or os.environ.get("ONEAPI_API_KEY")
        or os.environ.get("ONE_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    )


def _base_url() -> str:
    raw = (
        os.environ.get("ONEAPI_BASE_URL")
        or os.environ.get("ONE_API_URL")
        or "http://127.0.0.1:3000/v1"
    ).strip().rstrip("/")
    if raw.endswith("/chat/completions"):
        raw = raw[: -len("/chat/completions")].rstrip("/")
    return raw


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _bounded_text(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    left = limit // 2
    right = limit - left
    return text[:left] + "\n……（上下文压缩，原文仍在真源文件）……\n" + text[-right:]


CONSTITUTION = """你是荷园世界演化引擎，不是编剧，不是分镜师。
任务：让世界活起来。人物自己行动、遇见、选择、离开或留下。
禁止：列A/B分支、请示确认、停住等勾选、锁结局、写成镜头合同、写成分镜、写成制作备注。
禁止：把林墨写成少女、十六七岁、未成年；林墨是成年女子。
禁止：空转和大纲充数。每一场必须有具体环境、具体在场者、具体对白或动作，并且改变世界或关系。
允许：街坊、旧邻、守灵人、孤魂、精怪、过路修士/方士、中介、官府、宗族后人等自行登场或离场。
重要：周培与林墨是世界锚点，不是每场必须同场的固定搭档。不要把每一波都写成两人在听荷轩轮流谈话；优先让已经出现过的配角、街坊、官差、沈家/林家相关人或自然遇见的新角色承担一场完整行动、带来信息、利益压力或立场变化。新角色必须有名字（或稳定称谓）、自己的动机和可离场的选择，不是为递台词而来；没有因果需要时不要硬塞人。
本波分布倾向：在不违背当前世界状态的前提下，至少让一场不以周培与林墨同场为核心，至少让一场由第三方或群体行动推动变化；这不是锁阵容，也不是强行安排，世界若自然走向别处仍以已发生事实为准。
允许：情感、利益、灵异、动作、权谋自然缠在一起，哪股力强就往哪走。
允许：人物成长、动摇、犯错、后悔、再选择。
基调底色：清冷志怪、含蓄深情、物是人非。语言克制有张力，情绪落到动作、眼神、风雨、物件。
创者层基调锁定：灵异为表、人心为本、情义为骨、放下为归。主线优先落在人物内心成长、羁绊联结、执念释怀与关系修复；以温柔立根基，以坚定护所爱。
意象美学锁定唯美空灵系：月色、残荷、晨雾、水光、灯影、衣袂流光、寒波凝影。氛围清冷古雅、幽而不厉、静中有张力。严禁狰狞形貌、血腥虐杀、惊悚突脸、猎奇残酷描写。
冲突可以激烈、沉重、催泪，但激烈不残忍、沉重不绝望。自然形成“守界护衡一脉”与“执念淤滞所化障碍”的张力；后者不是天生邪恶，应保留可理解、可追溯、可化解的因。允许同伴、指引者、宿缘或宿敌出现，别离、牺牲与信念延续要悲壮但不黑暗。
成长方向：人物从困局内看清因果，守住本心，学会成全；心境通透是破局力量。爽点落在真相澄明、边界建立、误会冰释、执念化解、情义相守、迷途知返、善恶各有归；以共情、明悟、坚守、渡化、归位破局，拒绝极端复仇、毁灭式结局和无差别伤害。有遗憾仍存希望，结局优先朝圆满、释怀、清醒而非虐化推进。
《残荷诡影》创者层基调 V2.0：美中藏诡，情中藏局，局中藏因果。灵异是入口，悬念是牵引，人物是核心，情义是底色，因果是主线；不是讲鬼，而是把被时间掩埋的人、事、情、债拖回水面。
每一波至少保留一个尚未解释的异常或因果缺口，并自然经过“异常→疑问→介入→另一层秘密→暂释一层→再引更大谜面”；不要为了吓人制造诡异，也不要一次性解释完。节奏允许静—疑—险—燃—释—再疑，先让观众喜欢世界，再让不合理变得无法忽略。
美学必须承担叙事：月色可温柔也可预兆，残荷可写秋意也可作旧事证据，水面可映真实也可映出隐藏过去，灯影可指路也可误导，雾可遮危险也可遮真相。尽量做到一景两用、一物两意、一句两解，让后来的真相能反照前面的美。
重要人物都可以有不愿说的事：护秘密、寻真相、逃过去、知情沉默、守承诺或完成执念。立场不透明应来自动机与信息差，不是无证据的脸谱化善恶。爽点来自看穿局、面对因果、反转和情感回收，不来自残杀。
若自然发生对抗，战斗不追求血腥或大招轰炸；前面越安静，出手越应克制而有分量，以守界、止损、渡化或“到此为止”完成选择。结局可以悲痛或有牺牲，但重要债、承诺、秘密和离别必须得到回应；不强求所有遗憾弥补，但要有放下、等到、见光和被记住的落点。
魂句：月下见影，水中藏局；所见未必是真，所失终有其因。可以让观众以为看见的是鬼，后来发现看见的是一个人不肯放下的过去。
活人门槛（全剧共用，过不了整场重写，结构过关不能顶替）：写任何一场之前先过三问。1) 观众第一感：打开是人还是说明书？软/狠/盼有没有落在具体人身上？2) 有没有AI感：先讲规则再给反应、用比喻解释情绪、功能句推进、一上来就引擎口吻→退回。3) 想不想往下看：这人不肯将就、不肯低头、不肯放下的那一点有没有咬住？没有冲动就切开失败。人味是先要一样东西、付代价、还不将就；AI味是先讲规则、再给反应、再用比喻解释情绪。沙盒推的是活人，不是功能句。
禁止纯惊吓、猎奇虐杀、血腥炫技、无因果大招、强行翻案、为了反转硬塞人物或把温柔写成软弱、把清醒写成冷酷。
时间可从夏末入秋流向中秋、寒露，但不要为了过节而过节。
周培外温内韧，尊重不占有，护园护她但不盲从，会动手、谈判、周旋、决断。
林墨倨傲守界，夜来晓走可被她自己改掉或守住，重诺重体面，可柔可刚，触底线会显形、护家、退或留。
参考提示不是必须正确的路线。人物想留就留，想走就走，想查就查，想断就断。
直接输出场次正文和【本波快照】。思考不超过十句。禁止只推理不写正文。
"""


HEADER = (
    "# 《莲蓬鬼话》残荷诡影｜世界活体演化剧本\n\n"
    "层：CREATOR_LIVE。grok-4.7 自主连跑。非锁稿，未进 Agnes。\n"
    "林墨按成年女子演化。前史十场见 evolve_candidate.v1.md，此处不重演。\n\n"
    "## 前史收束（已发生）\n\n"
    "债清。园名空着。旧匾未揭。契未签。林墨不承诺明日。周培把酒留在太湖石上未开。\n\n"
)


def _compact_seed() -> str:
    ws = json.loads(_read(LIB / "creator_world_state.v1.json"))
    current = ws.get("current_after_s10") or {}
    dna1 = json.loads(_read(LIB / "C001.persona_dna.v1.json"))
    dna2 = json.loads(_read(LIB / "C002.persona_dna.v1.json"))
    seed = (
        "【人物DNA·周培C001】\n"
        + json.dumps(dna1, ensure_ascii=False, indent=2)
        + "\n【人物DNA·林墨C002】\n"
        + json.dumps(dna2, ensure_ascii=False, indent=2)
        + "\n【十场后世界 current_after_s10·只作起点，禁止重演第1-10场】\n"
        + json.dumps(current, ensure_ascii=False, indent=2)
        + "\n【前史真源】evolve_candidate.v1.md 已发生，本波不得重写。\n"
    )
    if PRIOR_LIB and PRIOR_LIB.exists():
        # Reincarnation reference: carry forward lessons and unresolved shape,
        # never the prior world's facts as current state or a locked storyline.
        prior_parts: list[str] = []
        experience = PRIOR_LIB / "creator_experience.jsonl"
        if experience.exists():
            prior_parts.append("【前世运行经验（只吸收教训，不当当前事实）】\n" + _read(experience))
        prior_waves = sorted((PRIOR_LIB / "world_live_waves").glob("wave_*.md"))
        for wave_path in prior_waves[-8:]:
            prior_parts.append("【前世参考 %s（只作反事实参照）】\n%s" % (
                wave_path.name,
                _bounded_text(_extract_snapshot(_read(wave_path)), 1800),
            ))
        if prior_parts:
            prior_blob = _bounded_text("\n\n".join(prior_parts), PROMPT_PRIOR_REF_CHARS)
            seed += (
                "\n"
                "【前世参考总则】这是上一条世界时间线留下的经验，不是本轮已发生事实。\n"
                "可用它避免重复卡点、识别人物秘密与未解因果、参考哪些配角曾有效推动世界；禁止照抄其主线、结局、阵容或把前世结果当成本轮记忆。\n"
                + prior_blob
                + "\n"
            )
    return seed


def _extract_snapshot(text: str) -> str:
    if "【本波快照】" in text:
        return text.split("【本波快照】", 1)[1].strip()
    return text[-1800:]


def _scene_headings(text: str) -> list[str]:
    hits: list[str] = []
    for line in text.splitlines():
        raw = line.strip()
        if SCENE_RE.match(raw) and "场｜" in raw:
            hits.append(raw)
    return hits


def _last_scene_num(text: str, fallback: int) -> int:
    nums = [int(m.group(1)) for m in SCENE_RE.finditer(text)]
    return max(nums) if nums else fallback


def _is_closed(text: str) -> bool:
    return any(mark in text for mark in CLOSED_MARKERS)


def _already_for_prompt(already_parts: list[str]) -> str:
    if not already_parts:
        return "尚无新波。从债清天亮的太湖石开始。"
    last = _bounded_text(already_parts[-1], PROMPT_LAST_WAVE_CHARS)
    if len(already_parts) == 1:
        return last
    prev_snap = _bounded_text(_extract_snapshot(already_parts[-2]), 6000)
    return "【再上一波只保留快照】\n" + prev_snap + "\n\n【最近一波全文】\n" + last


def _wave_prompt(wave: int, total: int, prev_snapshot: str, already: str) -> str:
    return f"""{CONSTITUTION}

这是第 {wave}/{total} 波活体演化。从当前世界继续往前活，不要重演已发生的十场，也不要重演已写出的波次。
本波写 4 到 6 场连续生活。场次编号从本波起始场号继续。
每场格式必须如下，一行不能少：
第N场｜日或夜｜内或外｜地点
环境：……
在场：……
周培：（若在场则写动作+对白；不在场写未出场）
林墨：（若在场则写动作+对白；不在场写未出场）
其他人：姓名/身份/立场/动作对白；若无写无
本场变化：世界/关系/物件/未决 各一句

本波结束时必须追加：
【本波快照】
时间：
地点：
在场：
人物状态：
关系：
新登场：
离场/生死：
已发生：
未解决：
关键道具：
世界开门还是收束：LIVE 或 CLOSED
一句话：本波世界自己走向了哪里

硬要求：
- 不要写“选项A/选项B”。
- 不要在中途问创者。
- 不要把债清当夜反复空耗；时间必须前进。
- 若有新人，必须有名字和自己的动机，不是工具人。
- 不要连续重复“周培和林墨在屋内谈话”作为主要推进方式；若两人同场，必须有新的外部行动、第三方介入或物件变化真正改变局面。
- 灵异冲突的落点必须回到人心与关系，不用恐怖强度代替因果；若出现对决，优先写共情/明悟/守界后的化解、归位或留有余地的退场。
- 已打开的锁、已取出的纸、已出场的人，一律视为既成事实，禁止重演“再开一次”“再当新登场”。
- 林墨字静逸。禁止把“静逸”派给她的长辈、曾祖母或其他新身份。
- 张四是塘北菜农，陆卷是已出场的户房书办。旧铜锁已在第207场打开并取出“换锁之日，此钥归赵。若有回音，荷下见”。
- 赵贞是郑茂之母、荷园二房、光绪二十六年嫁郑凤山、二十八年南去。禁止把赵贞写成赵家老屋姑娘、十九岁出籍或随锁匠离开。赵家老屋旧住姑姑未通名，与赵贞不是同一人。不要新造看屋人取代张四。秀兰可暗示，禁止当场认死戴手套女人。
- 走慢可以，禁止注水：同一匾、同一锁、同一哭声不要连场复读。
- 活人三问先于结构：观众第一感必须是人不是说明书；禁止AI味（先讲规则再给反应、比喻解释情绪、功能句推进）；本场必须咬住这个人不肯将就的那一点，让人想往下看。三问不过，本场作废重写，不准用有效推进顶替。
- 写稿与制作同一套冲突驱动：不是把话说长。禁止把冲突当信息传递（提问→答完→推进）。关键场先写清双方要什么、对方为什么不让，再写试探/施压/反击；收场必须改关系、信息、选择或行动之一。潜台词、压力升级、信息差拆开用，禁止每场套挑衅-隐忍-爆发。重复辱骂不是升级。A类高冲突允许多轮铺垫，B类推进简洁留个性，C类动作转场少废话。冲突没完成不要早收；再说只会重复就用行动、沉默或切场收束。
- 每场必须完成一次有效推进，并写进「本场变化」：确认一件事、推翻一个误认、缩小一个未决、或把旧伏笔勾回当前主线。四者至少居其一。禁止只写气氛、巡视、复述旧物而不改局面。
- 试炼规则必须咬选择：把已有规矩（待认不对名、不问不保、不拆船、空名透气、门不插、化冻前对完锁、春检翻舱）推到人物当场付代价才能过。规则不是说明书，是逼问。不要列出选项A/B，直接让人物做出不可逆的小选择。
- 绝境先堆满再给反击：封闭空间、时限、搜检、信物将失，至少一场把压力顶到不得不动手。反击靠看穿规则缝、守界、调转信物或扛代价，不靠大招、血腥和突然开挂。
- 信物链每场至少动一件，或明确拒绝移动并因此改变关系：锁鼻、锁芯、原封、冰纸、石缝盐、迁户白条、铁屑、岸位「荷下」签、带血脚夫线。禁止信物只旁观。
- 情绪转折要锋利：一场内关键人物态度须有一次可见转向（忍→决、退→挡、瞒→露、冷→痛），落到动作、眼神、手、物件，不靠独白解释。
- 冷必须落在日常生活的异化：邻里、饭桌、锁、船、帖、灯、荷。鬼从人的日子里长出来。禁止空洞地府、阎王殿、无来由阴差。
- 本波至少一场有认知或视觉反差（不该在的人还在、不该动的物自己动、全场若无其事只有一人看见），禁止连场拖沓探案。
- 残荷的爽落在看穿、守界、因果归位；禁止写成超自然虐恶现世报。那条只活在冷爽原创桌。
- 保持底色同时拉张力：清冷、干净、幽而不厉。走锐不走乱，不扩名，不把燃写成屠戮。
- 若本波世界自然收束，快照写 CLOSED，并写清谁留谁走、园名/契/匾/债后关系落到哪。
- 若尚未收束，写 LIVE。

【此前已活内容】
{already}

【上一波快照】
{prev_snapshot}
"""


def _is_transient_transport_error(exc: BaseException) -> bool:
    """Return true only for errors that are plausibly temporary transport failures."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in {408, 425, 429, 500, 502, 503, 504}
    if isinstance(exc, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError)):
        return True
    if isinstance(exc, OSError):
        return getattr(exc, "winerror", None) in {10053, 10054, 10060, 11001}
    return False


def _transport_retry_delay(retry_number: int) -> float:
    return min(TRANSPORT_RETRY_MAX_DELAY, TRANSPORT_RETRY_BACKOFF * (2 ** max(0, retry_number - 1)))


def _miner_chat():
    try:
        from tools.free_miner_router import chat as miner_chat
    except ImportError:
        tools_dir = str(Path(__file__).resolve().parent)
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        from free_miner_router import chat as miner_chat  # type: ignore
    return miner_chat


def _call(messages: list[dict[str, Any]], max_tokens: int, temperature: float, timeout: float, quality: str = "any") -> dict[str, Any]:
    retry_log: list[dict[str, Any]] = []
    miner_attempts: list[dict[str, Any]] = []
    miner_kwargs: dict[str, Any] = {
        "capability": "simple",
        "timeout": timeout,
        "task_class": "world_state_update",
        "allow_paid": True,
        "free_preferred": True,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "skip_unknown": True,
    }
    miner_kwargs["exclude_models"] = list(WRITING_EXCLUDED_MODELS)
    if quality == "wave":
        miner_kwargs["exclude_models"] = [
            *WRITING_EXCLUDED_MODELS,
            "glm-4-flash",
            "glm-4.5-flash",
            "openai/gpt-oss-20b",
            "z-ai/glm-5.3-flash",
        ]
        miner_kwargs["min_content_chars"] = 4000
        miner_kwargs["must_substrings"] = ["第", "场"]
        miner_kwargs["timeout"] = max(float(timeout), 300.0)
    try:
        data, miner_attempts = _miner_chat()(messages, **miner_kwargs)
        print(
            "[world-live] miner hit model=%s provider=%s finish=%s content=%s reasoning=%s"
            % (
                data.get("model"),
                data.get("provider"),
                data.get("finish_reason"),
                len(str(data.get("content") or "")),
                len(str(data.get("reasoning") or "")),
            ),
            flush=True,
        )
        return {
            "content": str(data.get("content") or "").strip(),
            "reasoning": str(data.get("reasoning") or "").strip(),
            "finish_reason": str(data.get("finish_reason") or ""),
            "actual_model": str(data.get("model") or ""),
            "usage": data.get("usage") or {},
            "latency_ms": data.get("latency_ms"),
            "transport_retries": retry_log,
            "miner_attempts": miner_attempts,
        }
    except Exception as exc:
        retry_log.append({"stage": "miner_pool", "error_type": type(exc).__name__, "error": str(exc)[:2000]})
        print("[world-live] miner pool missed; paid/local fallback model=%s error=%s" % (MODEL, type(exc).__name__), flush=True)

    for attempt in range(1, TRANSPORT_RETRY_ATTEMPTS + 1):
        try:
            data, meta = post_chat_completion(
                base_url=_base_url(),
                api_key=_key(),
                model=MODEL,
                messages=messages,
                asset_store=ROOT / "assets" / "cache" / "transport",
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            )
            break
        except Exception as exc:
            retryable = _is_transient_transport_error(exc)
            rec = {
                "attempt": attempt,
                "retryable": retryable,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            retry_log.append(rec)
            if not retryable or attempt >= TRANSPORT_RETRY_ATTEMPTS:
                raise
            delay = _transport_retry_delay(attempt)
            rec["sleep_seconds"] = delay
            print(
                "[world-live] transient OneAPI failure attempt=%s/%s error=%s retry_in=%.1fs"
                % (attempt, TRANSPORT_RETRY_ATTEMPTS, type(exc).__name__, delay),
                flush=True,
            )
            time.sleep(delay)
    else:  # pragma: no cover - loop either returns or raises above
        raise RuntimeError("WORLD_LIVE_TRANSPORT_RETRY_EXHAUSTED")

    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = str(message.get("content") or "").strip()
    reasoning = str(message.get("reasoning_content") or "").strip()
    finish = str(choice.get("finish_reason") or "")
    actual = str(data.get("model") or MODEL)
    usage = data.get("usage") or {}
    return {
        "content": content,
        "reasoning": reasoning,
        "finish_reason": finish,
        "actual_model": actual,
        "usage": usage,
        "latency_ms": meta.get("latency_ms"),
        "transport_retries": retry_log,
        "miner_attempts": miner_attempts,
    }


FOLLOW_BODY = "推理结束。从现在起只输出本波场次正文和【本波快照】。第一行必须是：第%s场。不要思考过程，不要分支，不要大纲。禁止空正文。"
INNER_DONE = "（内部推演已完成）"
TRUNC_HINT = "上一次输出被截断。从断点后继续写，不要重复已写段落，不要改写事实。"
CONT_HINT = "请接着写完本波剩余场次和【本波快照】。"


def _attempt_rec(kind: str, result: dict[str, Any], content: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "finish_reason": result["finish_reason"],
        "content_len": len(content or ""),
        "reasoning_len": len(result.get("reasoning") or ""),
        "usage": result.get("usage"),
        "latency_ms": result.get("latency_ms"),
        "transport_retries": result.get("transport_retries") or [],
        "validation_warnings": result.get("validation_warnings") or [],
    }


def _wave_output_errors(text: str, start_scene: int) -> list[str]:
    """Reject output that cannot be resumed as a world wave."""
    errors: list[str] = []
    # Accept equivalent ASCII punctuation from the model, while still
    # requiring the semantic fields themselves.
    normalized = (text or "").replace("|", "｜").replace(":", "：")
    headings = _scene_headings(normalized)
    if not headings:
        errors.append("NO_SCENE_HEADINGS")
    else:
        nums = [int(match.group(1)) for match in SCENE_RE.finditer(normalized)]
        if nums and nums[0] != start_scene:
            errors.append("FIRST_SCENE_%s_EXPECTED_%s" % (nums[0], start_scene))
        if nums != sorted(nums):
            errors.append("SCENE_NUMBERS_NOT_MONOTONIC")
    if "【本波快照】" not in normalized:
        errors.append("MISSING_WAVE_SNAPSHOT")
    snapshot_body = normalized.split("【本波快照】", 1)[1] if "【本波快照】" in normalized else ""
    if len(snapshot_body.strip()) < 120:
        errors.append("EMPTY_WAVE_SNAPSHOT")
    # These two fields prove that the wave can continue causally. Other
    # headings remain visible warnings because models vary their labels.
    for field in ("HAPPENED", "UNRESOLVED"):
        if not any(alias in snapshot_body for alias in WAVE_FIELD_ALIASES[field]):
            errors.append("MISSING_%s" % field)
    if any(token in normalized for token in ("选项A", "选项B", "请选择", "请创者决定")):
        errors.append("BRANCH_OR_CONFIRMATION_TEXT")
    if "曾祖母" in normalized:
        errors.append("LINMO_AS_GREAT_GRANDMOTHER")
    if "杨婆子" in normalized:
        errors.append("FORBIDDEN_NAME_YANGPOZI")
    if "塘北宋氏" in normalized:
        errors.append("ZHAO_HOUSE_AS_SONG")
    if re.search(r"赵贞.{0,30}(锁匠|出籍|年十九|赵家姑娘|随匠)", normalized) or re.search(
        r"(锁匠|年十九|赵家姑娘|随匠人).{0,30}赵贞", normalized
    ):
        errors.append("ZHAOZHEN_IDENTITY_COLLISION")
    return errors


def _wave_output_warnings(text: str) -> list[str]:
    normalized = (text or "").replace("|", "｜").replace(":", "：")
    snapshot_body = normalized.split("【本波快照】", 1)[1] if "【本波快照】" in normalized else normalized
    return [
        "MISSING_%s" % field
        for field, aliases in WAVE_FIELD_ALIASES.items()
        if not any(alias in snapshot_body for alias in aliases)
    ]


def _continue_truncated(
    result: dict[str, Any],
    text: str,
    attempts: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    if not text or result.get("finish_reason") != "length":
        return result, text
    print("[world-live] truncated, continue", flush=True)
    cont_prompt = CONSTITUTION + "\n" + TRUNC_HINT + "\n" + text[-6000:] + "\n" + CONT_HINT
    cont = _call([{"role": "user", "content": cont_prompt}], max_tokens=8192, temperature=0.7, timeout=180.0, quality="wave")
    text = text.rstrip() + "\n" + (cont["content"] or "")
    attempts.append(_attempt_rec("continue", cont, cont["content"]))
    merged = dict(result)
    merged["continue"] = attempts[-1]
    merged["finish_reason"] = cont["finish_reason"]
    merged["usage"] = cont["usage"]
    merged["latency_ms"] = cont["latency_ms"]
    merged["transport_retries"] = (result.get("transport_retries") or []) + (cont.get("transport_retries") or [])
    return merged, text



def _run_canon_pass() -> None:
    """Publish today's quota even when this cycle writes no new wave."""
    try:
        import subprocess
        script = ROOT / "tools" / "canon_scene_pass.py"
        if not script.exists():
            return
        subprocess.run(
            [sys.executable, str(script), "--once", "--lib", str(LIB)],
            cwd=str(ROOT),
            timeout=180,
            check=False,
        )
    except Exception as exc:
        print("[world-live] canon pass skipped: %s" % exc, flush=True)


def _force_wave(prompt: str, start_scene: int) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    result = _call(messages, max_tokens=8192, temperature=0.88, timeout=180.0, quality="wave")
    text = result["content"]
    attempts = [_attempt_rec("primary", result, text)]
    print("[world-live] primary finish=%s content=%s reasoning=%s usage=%s" % (
        result["finish_reason"], len(text), len(result["reasoning"]), result["usage"]
    ), flush=True)

    empty_tries = 0
    while not text and empty_tries < 3:
        empty_tries += 1
        follow = FOLLOW_BODY % start_scene
        messages = [
            {"role": "user", "content": prompt},
            {
                "role": "assistant",
                "content": result["content"] or INNER_DONE,
                "reasoning_content": result["reasoning"],
            },
            {"role": "user", "content": follow},
        ]
        forced = _call(messages, max_tokens=8192, temperature=0.45 if empty_tries > 1 else 0.55, timeout=180.0, quality="wave")
        text = forced["content"]
        attempts.append(_attempt_rec("force_body_%s" % empty_tries, forced, text))
        print("[world-live] force_body_%s finish=%s content=%s reasoning=%s usage=%s" % (
            empty_tries, forced["finish_reason"], len(text), len(forced["reasoning"]), forced["usage"]
        ), flush=True)
        result = forced
        if not text and empty_tries == 2:
            slim = (
                CONSTITUTION
                + "\n不要重演旧场。从第%s场写起，连续4到6场，最后必须有【本波快照】。\n" % start_scene
                + "【当前快照】\n"
                + prompt[-3500:]
            )
            retry = _call([{"role": "user", "content": slim}], max_tokens=8192, temperature=0.5, timeout=180.0, quality="wave")
            text = retry["content"]
            attempts.append(_attempt_rec("slim_retry", retry, text))
            print("[world-live] slim_retry finish=%s content=%s reasoning=%s usage=%s" % (
                retry["finish_reason"], len(text), len(retry["reasoning"]), retry["usage"]
            ), flush=True)
            result = retry

    result, text = _continue_truncated(result, text, attempts)

    if not str(text or "").strip():
        raise RuntimeError(
            "EMPTY_CONTENT finish=%s reasoning_len=%s usage=%s"
            % (result["finish_reason"], len(result.get("reasoning") or ""), result.get("usage"))
        )

    errors = _wave_output_errors(text, start_scene)
    for repair_no in range(1, WAVE_REPAIR_ATTEMPTS + 1):
        if not errors:
            break
        print("[world-live] wave structure invalid repair=%s/%s errors=%s" % (
            repair_no, WAVE_REPAIR_ATTEMPTS, ",".join(errors)
        ), flush=True)
        repair_prompt = (
            CONSTITUTION
            + "\n这是一次结构修复，不是新主线。请从第%s场重新输出本波完整正文和【本波快照】。\n" % start_scene
            + "上一版不能采用，问题：%s。禁止解释修复过程，禁止分支，禁止摘要代替场次。\n" % ", ".join(errors)
            + "上一版尾部仅供识别错误，不得照抄：\n"
            + text[-5000:]
            + "\n"
        )
        repaired = _call([{"role": "user", "content": repair_prompt}], max_tokens=8192, temperature=0.5, timeout=180.0, quality="wave")
        repaired_text = repaired["content"]
        attempts.append(_attempt_rec("structure_repair_%s" % repair_no, repaired, repaired_text))
        repaired, repaired_text = _continue_truncated(repaired, repaired_text, attempts)
        result = repaired
        text = repaired_text
        errors = _wave_output_errors(text, start_scene)
    if errors:
        # Last bounded fallback: remove the long failed draft from context and
        # force a body-only response. This is still a candidate wave; no facts
        # are synthesized locally.
        forced_prompt = (
            CONSTITUTION
            + "\n强制输出正文。从第%s场开始写4到6场连续生活，第一行必须是第%s场，最后必须有【本波快照】。\n"
            % (start_scene, start_scene)
            + "每场必须有环境、在场、人物动作/对白、本场变化；快照至少写已发生、未解决、世界开门还是收束。\n"
            + "不要解释、不要思考过程、不要分支。当前世界证据如下：\n"
            + _bounded_text(prompt[-6000:], 6000)
        )
        forced = _call([{"role": "user", "content": forced_prompt}], max_tokens=8192, temperature=0.35, timeout=180.0, quality="wave")
        forced_text = forced["content"]
        attempts.append(_attempt_rec("forced_structure_fallback", forced, forced_text))
        forced, forced_text = _continue_truncated(forced, forced_text, attempts)
        result = forced
        text = forced_text
        errors = _wave_output_errors(text, start_scene)
    if errors:
        raise RuntimeError("INVALID_WAVE_OUTPUT " + ",".join(errors))
    result["content"] = text
    result["validation_warnings"] = _wave_output_warnings(text)
    result["attempts"] = attempts
    return result


def _start_snapshot() -> str:
    return json.dumps(
        json.loads(_read(LIB / "creator_world_state.v1.json")).get("current_after_s10"),
        ensure_ascii=False,
        indent=2,
    )


def _cli_total(default: int = 8) -> int:
    args = sys.argv[1:]
    total = default
    i = 0
    while i < len(args):
        if args[i] in ("--total", "-n") and i + 1 < len(args):
            total = int(args[i + 1])
            i += 2
            continue
        i += 1
    if total < 1:
        raise SystemExit("total must be >= 1")
    return total


def _continue_seed() -> str:
    path = LIB / "next_live_seed.v1.json"
    if not path.exists():
        return ""
    data = json.loads(_read(path))
    inject = data.get("inject") or {}
    resume_scene = data.get("resume_from_scene")
    after = data.get("after") or "上一波快照"
    snapshot = data.get("current_snapshot")
    if snapshot and not inject:
        inject = {"resume_from_scene": resume_scene, "after": after, "current_snapshot": snapshot}
    return (
        "\n【动态续跑入口 %s·从第%s场继续】\n" % (after, resume_scene or "UNKNOWN")
        + json.dumps(inject, ensure_ascii=False, indent=2)
        + "\n硬锁：林墨成年女子。禁止十六七岁/少女。世界LIVE则继续活，自然收束才写CLOSED。不得重演已写波次。\n"
    )


def assemble_full_script() -> Path:
    opening = _read(LIB / "opening_given.v1.md").strip()
    s01_10 = _read(LIB / "evolve_candidate.v1.md").strip()
    waves_dir = LIB / "world_live_waves"
    wave_parts: list[str] = []
    if waves_dir.exists():
        for path in sorted(waves_dir.glob("wave_*.md")):
            body = path.read_text(encoding="utf-8").strip()
            if body:
                wave_parts.append("## %s\n\n%s" % (path.stem, body))
    summary = ""
    summary_path = LIB / "world_live_summary.v1.md"
    if summary_path.exists():
        summary = summary_path.read_text(encoding="utf-8").strip()
    out = LIB / "world_live_full_script.v1.md"
    chunks = [
        "# 《莲蓬鬼话》残荷诡影｜完整活体剧本",
        "",
        "层：CREATOR_LIVE 候选。非锁稿，未进 Agnes / Beat / Shot。",
        "真源拼接：opening_given + evolve_candidate(S01-S10) + world_live_waves。禁止覆盖各真源原文。",
        "林墨按成年女子。grok-4.7 自主连跑。",
        "",
        "## 给定开头",
        "",
        opening,
        "",
        "## 第1-10场（evolve_candidate 真源）",
        "",
        s01_10,
        "",
        "## 第11场起（世界自活）",
        "",
        "\n\n".join(wave_parts),
        "",
        "## 演化走向摘要",
        "",
        summary or "（摘要缺失，以各波【本波快照】为准）",
        "",
    ]
    _write(out, "\n".join(chunks))
    return out


def _load_resume(total: int) -> dict[str, Any]:
    waves_dir = LIB / "world_live_waves"
    waves_dir.mkdir(parents=True, exist_ok=True)
    already_parts: list[str] = []
    receipts: list[dict[str, Any]] = []
    prev_snapshot = _start_snapshot()
    next_scene_hint = 11
    start_wave = 1
    closed = False
    trace_id = uuid.uuid4().hex

    receipt_path = LIB / "world_live_receipt.v1.json"
    old: dict[str, Any] = {}
    if receipt_path.exists():
        try:
            old = json.loads(_read(receipt_path))
        except json.JSONDecodeError:
            old = {}
    if old.get("trace_id"):
        trace_id = str(old["trace_id"])
    prior = old.get("completed_waves") or old.get("waves") or []
    prior_by_wave = {int(item.get("wave")): item for item in prior if isinstance(item, dict) and item.get("wave")}

    for wave in range(1, total + 1):
        path = waves_dir / ("wave_%02d.md" % wave)
        if not path.exists():
            start_wave = wave
            break
        text = _read(path).strip()
        if not text:
            start_wave = wave
            break
        already_parts.append(text)
        prev_snapshot = _extract_snapshot(text)
        closed = _is_closed(text)
        next_scene_hint = _last_scene_num(text, next_scene_hint - 1) + 1
        rec = prior_by_wave.get(wave) or {
            "wave": wave,
            "status": "COMPLETED",
            "file": str(path.relative_to(ROOT)),
            "closed": closed,
            "scene_headings": _scene_headings(text),
            "resumed": True,
        }
        receipts.append(rec)
        start_wave = wave + 1
    else:
        start_wave = total + 1

    return {
        "already_parts": already_parts,
        "receipts": receipts,
        "prev_snapshot": prev_snapshot,
        "next_scene_hint": next_scene_hint,
        "start_wave": start_wave,
        "closed": closed,
        "trace_id": trace_id,
        "waves_dir": waves_dir,
    }


def _ensure_script(script_path: Path) -> None:
    if script_path.exists() and script_path.stat().st_size > 80:
        return
    _write(script_path, HEADER)


def _append_script(script_path: Path, wave: int, text: str) -> None:
    marker = "## 第%s波" % wave
    existing = _read(script_path) if script_path.exists() else ""
    if marker in existing:
        return
    with script_path.open("a", encoding="utf-8") as fh:
        fh.write("\n%s\n\n" % marker)
        fh.write(text.rstrip() + "\n")


def _partial_receipt(
    *,
    status: str,
    trace_id: str,
    started: float,
    total: int,
    receipts: list[dict[str, Any]],
    closed: bool,
    failed_wave: int | None = None,
    error: str | None = None,
    summary_rec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lib_rel = str(LIB.relative_to(ROOT)).replace("\\", "/")
    rec: dict[str, Any] = {
        "schema": "video_kingdom.world_live_receipt.v1",
        "status": status,
        "layer": "CREATOR_LIVE",
        "production_integration": False,
        "script_locked": False,
        "agnes": "NOT_PERFORMED",
        "beat": "NOT_PERFORMED",
        "shot": "NOT_PERFORMED",
        "model": MODEL,
        "gateway": _base_url(),
        "trace_id": trace_id,
        "waves_planned": total,
        "waves_run": len(receipts),
        "closed_by_world": closed,
        "elapsed_seconds": round(time.time() - started, 1),
        "files": {
            "script": lib_rel + "/world_live_script.v1.md",
            "summary": lib_rel + "/world_live_summary.v1.md",
            "waves_dir": lib_rel + "/world_live_waves",
        },
        "completed_waves": receipts,
        "waves": receipts,
        "true_source_untouched": "evolve_candidate.v1.md",
        "note": "活体演化候选。不是锁稿。未进生产。resume-safe。",
    }
    if failed_wave is not None:
        rec["failed_wave"] = failed_wave
    if error:
        rec["error"] = error
    if summary_rec is not None:
        rec["summary"] = summary_rec
    return rec


def _write_next_live_seed(next_scene: int, wave: int, snapshot: str, closed: bool) -> None:
    lib_rel = str(LIB.relative_to(ROOT)).replace("\\", "/")
    _dump(
        LIB / "next_live_seed.v1.json",
        {
            "schema": "video_kingdom.next_live_seed.v1",
            "layer": "CREATOR_LIVE",
            "production_integration": False,
            "resume_from_scene": next_scene,
            "after": "wave_%02d_snapshot" % wave,
            "world_open": not closed,
            "do_not_lock_cast": True,
            "do_not_lock_ending": True,
            "current_snapshot": snapshot,
            "continue_from_files": [
                lib_rel + "/world_live_waves/wave_%02d.md" % wave,
                lib_rel + "/world_live_script.v1.md",
            ],
            "forbidden": ["agnes", "imagegen", "video_kingdom_entry", "beat", "shot", "lock_script"],
        },
    )


def _update_script_status() -> None:
    path = LIB / "script_status.v1.json"
    if not path.exists():
        return
    try:
        data = json.loads(_read(path))
    except json.JSONDecodeError:
        return
    files = list(data.get("files") or [])
    extra = [
        "world_live_script.v1.md",
        "world_live_summary.v1.md",
        "world_live_receipt.v1.json",
        "world_live_waves/wave_01.md",
    ]
    for name in extra:
        if name not in files:
            files.append(name)
    data["files"] = files
    data["script_locked"] = False
    data["production_integration"] = False
    data["world_live"] = "CANDIDATE_NOT_LOCKED"
    skipped = list(data.get("skipped") or [])
    for item in ("shot_contract", "agnes", "imagegen", "video_kingdom_entry"):
        if item not in skipped:
            skipped.append(item)
    data["skipped"] = skipped
    waves = sorted((LIB / "world_live_waves").glob("wave_*.md")) if (LIB / "world_live_waves").exists() else []
    for wp in waves:
        rel = "world_live_waves/" + wp.name
        if rel not in files:
            files.append(rel)
    full_name = "world_live_full_script.v1.md"
    if (LIB / full_name).exists() and full_name not in files:
        files.append(full_name)
    data["files"] = files
    last_scene = 10
    for wp in waves:
        last_scene = _last_scene_num(_read(wp), last_scene)
    data["next_live_scene"] = last_scene + 1
    _dump(path, data)


def _compact_summary_blob(parts: list[str]) -> str:
    """Keep summary context bounded so a long run cannot fail only at the end."""
    if not parts:
        return "（暂无波次快照）"
    indexes = list(range(min(4, len(parts))))
    indexes.extend(range(max(4, len(parts) - 12), len(parts)))
    seen: set[int] = set()
    chunks: list[str] = []
    for index in indexes:
        if index in seen:
            continue
        seen.add(index)
        snapshot = _extract_snapshot(parts[index]).strip()
        if len(snapshot) > 2200:
            snapshot = snapshot[:1100] + "\n……（中间快照省略）……\n" + snapshot[-1100:]
        chunks.append("第%s波快照\n%s" % (index + 1, snapshot))
    return "\n\n".join(chunks)


def main() -> int:
    return _main_impl()


def _canon_quota_block_reason() -> str:
    """Block a paid model call when today cap is already full.
    Missing or unreadable quota fails closed.
    STOP_PAID_WRITING is retired. The daily cap is the only switch.
    """
    path = LIB / "canon_pass_quota.v1.json"
    if not path.exists():
        return "quota_missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        max_per = int(data.get("max_per_day") or 2)
    except Exception:
        return "quota_unreadable"
    if max_per < 1:
        return "quota_unreadable"
    today = time.strftime("%Y-%m-%d")
    day = (data.get("days") or {}).get(today) or {}
    try:
        passed = int(day.get("passed") or 0)
    except (TypeError, ValueError):
        return "quota_unreadable"
    if passed >= max_per:
        return "daily_cap passed=%s max=%s day=%s" % (passed, max_per, today)
    return ""


def _return_if_canon_quota_blocks():
    reason = _canon_quota_block_reason()
    if not reason:
        return None
    print("[world-live] canon quota blocks paid call, exit 3: %s" % reason, flush=True)
    return 3


def _main_impl() -> int:
    blocked = _return_if_canon_quota_blocks()
    if blocked:
        return blocked
    if not _key():
        print("FAIL NO_API_KEY", flush=True)
        return 2
    total = _cli_total(8)
    seed = _compact_seed() + _continue_seed()
    resume = _load_resume(total)
    already_parts: list[str] = resume["already_parts"]
    receipts: list[dict[str, Any]] = resume["receipts"]
    prev_snapshot = resume["prev_snapshot"]
    next_scene_hint = resume["next_scene_hint"]
    closed = bool(resume["closed"])
    trace_id = resume["trace_id"]
    waves_dir: Path = resume["waves_dir"]
    started = time.time()
    script_path = LIB / "world_live_script.v1.md"
    _ensure_script(script_path)

    print(
        "[world-live] resume start_wave=%s next_scene=%s have_waves=%s closed=%s"
        % (resume["start_wave"], next_scene_hint, len(already_parts), closed),
        flush=True,
    )

    for wave in range(int(resume["start_wave"]), total + 1):
        if closed:
            break
        blocked = _return_if_canon_quota_blocks()
        if blocked:
            return blocked
        print("[world-live] wave %s/%s start scene~%s" % (wave, total, next_scene_hint), flush=True)
        prompt = seed + "\n\n" + _wave_prompt(
            wave,
            total,
            prev_snapshot,
            _already_for_prompt(already_parts),
        ) + "\n本波场号从第%s场起编。\n" % next_scene_hint
        result: dict[str, Any] | None = None
        text = ""
        wave_error: Exception | None = None
        for wave_try in range(1, WAVE_RETRY_ATTEMPTS + 1):
            try:
                result = _force_wave(prompt, next_scene_hint)
                text = result["content"]
                wave_error = None
                break
            except Exception as exc:
                wave_error = exc
                recoverable = _is_transient_transport_error(exc) or str(exc).startswith(("INVALID_WAVE_OUTPUT", "EMPTY_CONTENT"))
                if not recoverable or wave_try >= WAVE_RETRY_ATTEMPTS:
                    break
                delay = min(120.0, WAVE_RETRY_BACKOFF * (2 ** (wave_try - 1)))
                print(
                    "[world-live] recoverable wave failure wave=%s attempt=%s/%s error=%s retry_in=%.1fs"
                    % (wave, wave_try, WAVE_RETRY_ATTEMPTS, type(exc).__name__, delay),
                    flush=True,
                )
                time.sleep(delay)
        if wave_error is not None:
            fail = _partial_receipt(
                status="FAILED",
                trace_id=trace_id,
                started=started,
                total=total,
                receipts=receipts,
                closed=closed,
                failed_wave=wave,
                error="%s: %s" % (type(wave_error).__name__, wave_error),
            )
            _dump(LIB / "world_live_receipt.v1.json", fail)
            _run_canon_pass()
            print("FAIL", fail["error"], flush=True)
            return 1

        wave_path = waves_dir / ("wave_%02d.md" % wave)
        _write(wave_path, text + "\n")
        already_parts.append(text)
        prev_snapshot = _extract_snapshot(text)
        closed = _is_closed(text)
        headings = _scene_headings(text)
        next_scene_hint = _last_scene_num(text, next_scene_hint - 1) + 1
        _append_script(script_path, wave, text)
        _write_next_live_seed(next_scene_hint, wave, prev_snapshot, closed)
        rec = {
            "wave": wave,
            "status": "COMPLETED",
            "model": result["actual_model"],
            "requested_model": MODEL,
            "finish_reason": result["finish_reason"],
            "latency_ms": result["latency_ms"],
            "usage": result["usage"],
            "file": str(wave_path.relative_to(ROOT)),
            "closed": closed,
            "scene_headings": headings,
            "attempts": result.get("attempts") or [],
            "validation_warnings": result.get("validation_warnings") or [],
        }
        receipts.append(rec)
        running = _partial_receipt(
            status="RUNNING",
            trace_id=trace_id,
            started=started,
            total=total,
            receipts=receipts,
            closed=closed,
        )
        _dump(LIB / "world_live_receipt.v1.json", running)
        # Keep a readable derived script current even if the watchdog has to
        # resume before the final summary step.
        assemble_full_script()
        _run_canon_pass()
        print("[world-live] wave %s done scenes=%s closed=%s" % (wave, len(headings), closed), flush=True)

    if int(resume["start_wave"]) > total or closed:
        _run_canon_pass()

    blocked = _return_if_canon_quota_blocks()
    if blocked:
        return blocked
    snap_blob = _compact_summary_blob(already_parts)
    summary_prompt = (
        CONSTITUTION
        + "\n根据以下已发生的活体演化快照，只写一份短摘要，不要扩写新剧情。\n"
        + "必须包含：谁来了、发生了什么、关键转折、结局形态、哪些人留/走。\n"
        + "禁止分支清单，禁止镜头。800字内。只依据快照，不把省略部分补成新事实。\n\n"
        + snap_blob
    )
    summary_text = ""
    summary_rec: dict[str, Any] = {}
    summary_attempts: list[dict[str, Any]] = []
    # Summary is derived convenience output, never a reason to invalidate a
    # completed world run. DeepSeek may spend the whole short budget in
    # reasoning and return an empty body; retry with a smaller evidence window
    # before falling back to an exact, non-invented excerpt.
    summary_prompts = [
        (summary_prompt, 2400),
        (
            CONSTITUTION
            + "\n只输出不超过500字的事实摘要，不要分析、不要新剧情、不要分支。\n"
            + "必须包含：谁来了、发生了什么、关键转折、结局形态、哪些人留/走。\n"
            + _compact_summary_blob(already_parts[-6:]),
            2200,
        ),
    ]
    last_error: str | None = None
    for summary_no, (candidate_prompt, budget) in enumerate(summary_prompts, 1):
        try:
            sres = _call([{"role": "user", "content": candidate_prompt}], max_tokens=budget, temperature=0.2, timeout=180.0)
            candidate = (sres.get("content") or "").strip()
            attempt = {
                "attempt": summary_no,
                "model": sres.get("actual_model"),
                "latency_ms": sres.get("latency_ms"),
                "usage": sres.get("usage"),
                "finish_reason": sres.get("finish_reason"),
                "prompt_chars": len(candidate_prompt),
                "content_len": len(candidate),
                "transport_retries": sres.get("transport_retries") or [],
            }
            summary_attempts.append(attempt)
            if candidate:
                summary_text = candidate
                summary_rec = {
                    "status": "COMPLETED",
                    "attempt": summary_no,
                    "model": sres.get("actual_model"),
                    "latency_ms": sres.get("latency_ms"),
                    "usage": sres.get("usage"),
                    "finish_reason": sres.get("finish_reason"),
                    "prompt_chars": len(candidate_prompt),
                    "transport_retries": sres.get("transport_retries") or [],
                    "attempts": summary_attempts,
                }
                break
            last_error = "EMPTY_SUMMARY_BODY"
        except Exception as exc:
            last_error = "%s: %s" % (type(exc).__name__, exc)
            summary_attempts.append({"attempt": summary_no, "status": "FAILED", "error": last_error})
    if not summary_text:
        # Exact source excerpt is a valid resumable result, not a fabricated
        # summary. Mark it explicitly so downstream readers know its nature.
        summary_text = "模型摘要未完成；以下为波次快照原文摘录，完整事实以各 wave 文件为准。\n\n" + _compact_summary_blob(already_parts[-6:])
        summary_rec = {
            "status": "FALLBACK_EVIDENCE",
            "reason": last_error or "SUMMARY_UNAVAILABLE",
            "attempts": summary_attempts,
            "note": "仅保留真源快照摘录，未生成或补写事实。",
        }

    _write(LIB / "world_live_summary.v1.md", summary_text + "\n")
    receipt = _partial_receipt(
        status="COMPLETED",
        trace_id=trace_id,
        started=started,
        total=total,
        receipts=receipts,
        closed=closed,
        summary_rec=summary_rec,
    )
    _dump(LIB / "world_live_receipt.v1.json", receipt)
    full_path = assemble_full_script()
    _update_script_status()
    print("OK", json.dumps({"waves": len(receipts), "closed": closed, "trace": trace_id, "full_script": str(full_path.relative_to(ROOT))}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
