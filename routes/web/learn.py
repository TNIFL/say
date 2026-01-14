from __future__ import annotations

from flask import Blueprint, render_template, abort, request
from flask_babel import lazy_gettext as _

learn_bp = Blueprint("learn", __name__)

# ============================================================
#  IMPORTANT DESIGN
#   - URL/식별자: 절대 번역하지 않는다 (section_key, slug, type)
#   - 화면 표시용: section_label, desc, title, intro, blocks... 은 번역 대상
# ============================================================

PAGES = [
    {
        "section_key": "quick_start",
        "section_label": _("빠른 시작"),
        "desc": _("문장만 넣고, 옵션만 클릭해서 끝내는 가장 빠른 사용법"),
        "items": [
            {
                "slug": "start-10s",
                "title": _("10초 시작 (프롬프트 없이)"),
                "intro": _("Lexinoa는 프롬프트를 안 씁니다. 문장 + 옵션 선택만으로 결과를 컨트롤합니다."),
                "blocks": [
                    {"type": "bullets", "h": _("핵심 원칙"), "items": [
                        _("사용자는 ‘문장’만 제공하고, 결과 방향은 옵션으로 결정합니다."),
                        _("카테고리 1개 + 톤 1개 + 체크 0~2개로 시작하면 대부분 1회에 끝납니다."),
                        _("잘 안 맞으면 ‘문장을 더 쓰는’ 게 아니라 옵션을 바꿉니다."),
                    ]},
                    {"type": "steps", "h": _("웹에서 가장 빠른 흐름"), "items": [
                        _("문장을 붙여넣기"),
                        _("카테고리 1개 선택 (요청/리마인드/사과/거절/감사 등)"),
                        _("톤 1개 선택 (부드럽게/단호하지만 예의/공식)"),
                        _("필요할 때만 체크: 존댓말 / 완충문 / 이모지"),
                        _("결과 선택 → 복사/사용"),
                    ]},
                    {"type": "bullets", "h": _("결과가 마음에 안 들면(프롬프트 금지)"), "items": [
                        _("요청인데 차갑다 → 톤을 ‘부드럽게’로"),
                        _("리마인드가 약하다 → 톤을 ‘단호하지만 예의’로"),
                        _("거절이 날카롭다 → 카테고리를 ‘거절/대안’ 쪽으로"),
                        _("메신저에서 딱딱하다 → ‘완충문’ 체크 ON"),
                    ]},
                ],
            },
            {
                "slug": "presets",
                "title": _("추천 옵션 조합 (프리셋)"),
                "intro": _("자주 쓰는 조합만 저장/기억하면 대부분 클릭 몇 번으로 끝납니다."),
                "blocks": [
                    {"type": "cards", "h": _("메신저(카톡/슬랙)"), "items": [
                        {"title": _("부드러운 요청"), "desc": _("카테고리: 요청 / 톤: 부드럽게 / 완충문 ON / 이모지 OFF")},
                        {"title": _("부드러운 리마인드"), "desc": _("카테고리: 리마인드 / 톤: 부드럽게 / 완충문 ON")},
                    ]},
                    {"type": "cards", "h": _("이메일/대외"), "items": [
                        {"title": _("공식 요청"), "desc": _("카테고리: 요청 / 톤: 공식 / 존댓말 ON / 완충문 OFF")},
                        {"title": _("사과/정정"), "desc": _("카테고리: 사과/정정 / 톤: 공식 / 존댓말 ON")},
                    ]},
                    {"type": "cards", "h": _("단호한 커뮤니케이션"), "items": [
                        {"title": _("원칙 안내/불가"), "desc": _("카테고리: 거절/대안 / 톤: 단호하지만 예의 / 존댓말 ON")},
                        {"title": _("기한 리마인드"), "desc": _("카테고리: 리마인드 / 톤: 단호하지만 예의 / 완충문 OFF")},
                    ]},
                ],
            },
        ],
    },

    {
        "section_key": "options",
        "section_label": _("옵션 사용법"),
        "desc": _("프롬프트 대신 옵션으로 결과를 원하는 방향으로 고정하는 법"),
        "items": [
            {
                "slug": "category-first",
                "title": _("카테고리 선택이 80%입니다"),
                "intro": _("Lexinoa는 ‘의도’를 카테고리로 먼저 고정해서 가장 빠르게 안정적인 결과를 냅니다."),
                "blocks": [
                    {"type": "cards", "h": _("카테고리 선택 기준"), "items": [
                        {"title": _("요청"), "desc": _("상대에게 행동을 부탁하는 문장")},
                        {"title": _("리마인드"), "desc": _("진행/답장을 재촉하되 마찰을 줄이는 문장")},
                        {"title": _("사과/정정"), "desc": _("혼선/실수를 수습하고 신뢰를 회복하는 문장")},
                        {"title": _("거절/대안"), "desc": _("불가를 전달하되 대안을 제시하는 문장")},
                        {"title": _("감사/칭찬"), "desc": _("관계를 강화하고 분위기를 좋게 만드는 문장")},
                    ]},
                    {"type": "bullets", "h": _("자주 생기는 오해 해결"), "items": [
                        _("‘요청’인데 결과가 명령처럼 보임 → 톤을 ‘부드럽게’ + 완충문 ON"),
                        _("‘리마인드’가 너무 약함 → 톤을 ‘단호하지만 예의’"),
                        _("‘거절’이 공격적으로 보임 → ‘대안’ 성격 카테고리 선택 + 존댓말 ON"),
                    ]},
                ],
            },
            {
                "slug": "tone-control",
                "title": _("톤은 ‘인상’을 결정합니다"),
                "intro": _("같은 내용도 톤에 따라 공격/정중/공식으로 읽힙니다. 프롬프트 대신 톤으로 조정하세요."),
                "blocks": [
                    {"type": "cards", "h": _("톤 추천"), "items": [
                        {"title": _("부드럽게"), "desc": _("메신저/동료/감정 마찰 방지")},
                        {"title": _("단호하지만 예의"), "desc": _("기한/원칙/기준이 필요한 상황")},
                        {"title": _("공식"), "desc": _("고객/외부/이메일/문서")},
                    ]},
                    {"type": "bullets", "h": _("실전 팁"), "items": [
                        _("대부분은 ‘부드럽게’로 시작 → 필요할 때만 단호/공식으로 이동"),
                        _("이메일은 ‘공식 + 존댓말 ON’이 기본"),
                    ]},
                ],
            },
            {
                "slug": "checkboxes",
                "title": _("체크 옵션(존댓말·완충문·이모지) 사용법"),
                "intro": _("체크는 분위기를 한 번에 바꾸는 스위치입니다. 과하면 오히려 어색해질 수 있습니다."),
                "blocks": [
                    {"type": "cards", "h": _("체크 옵션 가이드"), "items": [
                        {"title": _("존댓말"), "desc": _("상사/고객/외부면 ON. 내부 친한 사이면 OFF도 가능")},
                        {"title": _("완충문"), "desc": _("메신저/재촉/요청에서 ON이 강력. 너무 길어지면 OFF")},
                        {"title": _("이모지"), "desc": _("내부 분위기 완화용. 고객/상사/공식 문서에서는 OFF")},
                    ]},
                    {"type": "bullets", "h": _("가장 많이 쓰는 조합"), "items": [
                        _("카톡/슬랙: 부드럽게 + 완충문 ON + 이모지 OFF(기본)"),
                        _("고객/이메일: 공식 + 존댓말 ON + 이모지 OFF"),
                    ]},
                ],
            },
        ],
    },

    {
        "section_key": "extension",
        "section_label": _("확장프로그램"),
        "desc": _("페이지 이동 없이 그 자리에서 순화하는 것이 핵심"),
        "items": [
            {
                "slug": "ext-rightclick",
                "title": _("우클릭 순화 (가장 빠른 흐름)"),
                "intro": _("웹페이지에서 문장 드래그 → 우클릭 → 옵션만 선택 → 즉시 사용"),
                "blocks": [
                    {"type": "steps", "h": _("사용 방법"), "items": [
                        _("문장을 드래그로 선택"),
                        _("우클릭 → Lexinoa 순화"),
                        _("팝업에서 카테고리/톤/체크만 선택"),
                        _("결과 복사 또는 교체"),
                    ]},
                    {"type": "bullets", "h": _("언제 최고인가"), "items": [
                        _("메일/채팅/폼 입력 도중: 페이지를 옮기지 않고 바로 다듬고 싶을 때"),
                        _("전체 글이 아니라 ‘문장 일부만’ 빠르게 고치고 싶을 때"),
                    ]},
                ],
            },
            {
                "slug": "ext-drag",
                "title": _("드래그로 바로 순화 (흐름 유지)"),
                "intro": _("작성 흐름을 끊지 않는 것이 확장의 가치입니다."),
                "blocks": [
                    {"type": "steps", "h": _("사용 방법"), "items": [
                        _("문장 드래그"),
                        _("뜬 UI에서 옵션만 선택"),
                        _("결과를 즉시 반영"),
                    ]},
                    {"type": "bullets", "h": _("옵션 선택 팁"), "items": [
                        _("메신저면: 완충문 ON을 먼저"),
                        _("이메일이면: 공식 + 존댓말 ON"),
                        _("재촉이면: 리마인드 카테고리를 우선"),
                    ]},
                ],
            },
        ],
    },

    {
        "section_key": "templates",
        "section_label": _("템플릿"),
        "desc": _("프롬프트가 아니라 ‘옵션 조합’을 저장해서 반복을 없앰"),
        "items": [
            {
                "slug": "templates-as-presets",
                "title": _("템플릿 = 옵션 조합 저장"),
                "intro": _("자주 쓰는 카테고리/톤/체크 조합을 저장해두면 다음부터는 클릭 몇 번으로 끝납니다."),
                "blocks": [
                    {"type": "cards", "h": _("추천 템플릿"), "items": [
                        {"title": _("업무 요청(부드럽게)"), "desc": _("요청 / 부드럽게 / 완충문 ON / 이모지 OFF")},
                        {"title": _("고객 안내(공식)"), "desc": _("요청 또는 안내 / 공식 / 존댓말 ON / 이모지 OFF")},
                        {"title": _("기한 리마인드(단호)"), "desc": _("리마인드 / 단호하지만 예의 / 완충문 OFF")},
                    ]},
                    {"type": "steps", "h": _("사용 흐름"), "items": [
                        _("템플릿 선택"),
                        _("문장만 붙여넣기(또는 드래그)"),
                        _("필요하면 톤만 변경해 미세 조정"),
                    ]},
                ],
            },
        ],
    },
]


def _build_index():
    """Exported NAV and SLUG_MAP for other modules (e.g., sitemap)."""
    slug_map: dict[str, dict] = {}
    nav: list[dict] = []

    for sec in PAGES:
        nav.append({
            "section_key": sec["section_key"],
            "section_label": sec["section_label"],
            "desc": sec.get("desc", ""),
            "items": [
                {"slug": it["slug"], "title": it["title"], "intro": it.get("intro", "")}
                for it in sec["items"]
            ],
        })

        for it in sec["items"]:
            slug_map[it["slug"]] = {
                **it,
                "section_key": sec["section_key"],
                "section_label": sec["section_label"],
            }

    return nav, slug_map


# IMPORTANT: keep these names for external imports (sitemap.py expects SLUG_MAP)
NAV, SLUG_MAP = _build_index()


@learn_bp.route("/learn")
def learn_index():
    section_key = request.args.get("section")
    return render_template("learn/index.html", nav=NAV, active_section_key=section_key)


@learn_bp.route("/learn/<slug>")
def learn_page(slug: str):
    page = SLUG_MAP.get(slug)
    if not page:
        abort(404)

    return render_template(
        "learn/page.html",
        nav=NAV,
        page=page,
        active_section_key=page.get("section_key"),
    )
