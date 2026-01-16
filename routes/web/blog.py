from flask import Blueprint, render_template, abort, request
from flask_babel import get_locale

blog_bp = Blueprint("blog", __name__)

# 언어별 포스트 데이터: 총 10개 (ko 10 / en 10)
# - ko: 한국어만 최대한 유지(중간에 영어 표현/약어/문구 삽입 없음)
# - en: 영어 자연스러운 표현 유지
POSTS = {
    "ko": [
        # 1) 이메일 톤 오해
        {
            "slug": "why-your-email-sounds-rude",
            "title": "왜 이메일이 의도보다 무례하게 들릴까?",
            "description": "이메일에서 말투가 쉽게 오해되는 이유와, 자연스럽게 톤을 다듬는 방법",
            "content_html": """
<h1>왜 이메일이 의도보다 무례하게 들릴까?</h1>
<p>보내고 나서 다시 읽어보면, 내가 생각한 것보다 훨씬 딱딱하거나 차갑게 느껴지는 이메일이 있습니다. 의도는 전혀 그런 게 아니었는데도요.</p>

<h2>문제는 ‘단어’보다 ‘환경’에 있습니다</h2>
<p>이메일에는 표정, 억양, 말의 속도 같은 정보가 없습니다. 그래서 짧은 문장일수록 ‘명령’이나 ‘불만’처럼 읽힐 여지가 커집니다.</p>

<h2>업무 이메일에서 오해가 특히 잦은 이유</h2>
<ul>
  <li><strong>시간 압박</strong>: 급할수록 짧게 쓰게 되고, 완충 표현이 빠지기 쉽습니다.</li>
  <li><strong>관계/직급</strong>: 요청이 ‘부탁’이 아니라 ‘지시’처럼 읽힐 수 있습니다.</li>
  <li><strong>맥락 부족</strong>: 상대는 “왜 지금 이걸 요구하지?”를 추측하게 됩니다.</li>
</ul>

<h2>해결의 핵심: 내용은 유지하고, 의도만 한 번 더 표시하기</h2>
<ul>
  <li><strong>완충 표현 한 줄</strong>: “가능하실 때”, “편하실 때”, “확인 부탁드립니다”</li>
  <li><strong>이유 한 줄</strong>: 왜 지금 필요하고, 어떤 일정과 연결되는지</li>
  <li><strong>원하는 행동 명확히</strong>: 회신/확인/공유/승인 중 무엇이 필요한지</li>
</ul>

<h2>짧은 예시</h2>
<p><strong>전:</strong> “오늘 안에 주세요.”<br>
<strong>후:</strong> “오늘 중으로 반영이 필요해서요. 가능하시면 오늘 안에 공유 부탁드립니다.”</p>

<p>상대가 ‘압박’으로 받아들이지 않게, “상황 공유 + 요청” 구조로 바꾸는 것만으로도 오해가 크게 줄어듭니다.</p>
""".strip(),
        },

        # 2) 빈정거림으로 읽히는 문구(한국 조직 문화/메일 문화 고려)
        {
            "slug": "emails-that-sound-sarcastic",
            "title": "그냥 확인인데도 ‘빈정거림’으로 읽히는 이메일 문장들",
            "description": "의도는 확인이지만, 상대가 불쾌하게 느낄 수 있는 표현과 자연스러운 대체 문장",
            "content_html": """
<h1>그냥 확인인데도 ‘빈정거림’으로 읽히는 이메일 문장들</h1>
<p>일을 하다 보면 “이미 말했는데…”라는 감정이 올라올 때가 있습니다. 문제는 그 감정이 문장에 묻어 나오면, 상대는 즉시 방어적으로 반응할 수 있다는 점입니다.</p>

<h2>오해가 잦은 유형</h2>
<ul>
  <li><strong>상대의 실수를 전제로 하는 문장</strong>: “지난번에 말씀드렸는데요.”</li>
  <li><strong>책임을 떠넘기는 느낌</strong>: “확인해 보시고 말씀 주세요.”만 던지는 형태</li>
  <li><strong>차갑게 끊는 짧은 회신</strong>: “확인.” “네.”만 남기는 형태</li>
  <li><strong>압박처럼 보이는 마무리</strong>: “빠른 회신 바랍니다.”를 반복하는 형태</li>
</ul>

<h2>대체 문장의 핵심: ‘상대 탓’이 아니라 ‘업무 진행’으로 보이게</h2>
<ul>
  <li>“중요한 부분이라 다시 한 번 공유드립니다. 확인 부탁드립니다.”</li>
  <li>“다음 일정 조율이 필요해서요. 가능하실 때 의견 부탁드립니다.”</li>
  <li>“확인했습니다. 저는 이 방향으로 진행하겠습니다.”(짧은 회신은 ‘다음 행동’을 붙이면 부드러워집니다)</li>
</ul>

<h2>실전 예시</h2>
<p><strong>전:</strong> “지난번에 말씀드렸는데요. 확인해보시고 말씀 주세요.”<br>
<strong>후:</strong> “이전에 공유드린 내용 다시 전달드립니다. 일정 조율 때문에 방향 확인이 필요해서요. 가능하실 때 의견 부탁드립니다.”</p>

<p>같은 내용을 말하더라도, 상대의 ‘미확인/미처리’를 전제로 삼는 표현만 줄이면 관계 비용이 크게 줄어듭니다.</p>
""".strip(),
        },

        # 3) 재촉(리마인드) 메시지
        {
            "slug": "follow-up-message-without-pressure",
            "title": "재촉 메시지를 부담 없이 보내는 법: 답을 받는 리마인드 구조",
            "description": "불편하지 않으면서도 회신을 끌어내는 ‘맥락-요청-시간’ 3단 구성",
            "content_html": """
<h1>재촉 메시지를 부담 없이 보내는 법: 답을 받는 리마인드 구조</h1>
<p>답이 늦어지면 확인이 필요하지만, 재촉이 관계를 망칠까 조심스러운 순간이 있습니다. 이럴 때는 ‘정중함’보다 ‘구체성’이 더 중요합니다.</p>

<h2>리마인드가 싫게 들리는 순간</h2>
<ul>
  <li><strong>원하는 행동이 불명확</strong>: “확인차 연락드립니다”만 있는 경우</li>
  <li><strong>상대 탓처럼 들림</strong>: “아직도 안 됐나요?”처럼 지적이 섞이는 경우</li>
  <li><strong>짧은 문장 연속</strong>: 물음표나 한 단어를 여러 번 보내는 경우</li>
</ul>

<h2>답을 받는 리마인드 3요소</h2>
<ul>
  <li><strong>맥락 1문장</strong>: 왜 지금 확인이 필요한지</li>
  <li><strong>요청 1문장</strong>: 회신/확인/진행 상황 공유 중 무엇을 원하는지</li>
  <li><strong>시간 1문장(필요할 때만)</strong>: “오늘 중”, “오후 3시 전”처럼 최소한으로</li>
</ul>

<h2>예시 문장</h2>
<ul>
  <li>“일정 조율 때문에 진행 상황 확인이 필요합니다. 가능하실 때 현재 상태 공유 부탁드립니다.”</li>
  <li>“오늘 중으로 다음 단계 진행 여부를 결정해야 해서요. 가능하시면 오늘 안에 확인 부탁드립니다.”</li>
  <li>“확인이 늦어져서 일정이 밀릴 수 있어요. 편하실 때 회신 부탁드립니다.”</li>
</ul>

<p>리마인드는 ‘재촉’이 아니라 ‘조율’로 읽히게 만드는 것이 핵심입니다.</p>
""".strip(),
        },

        # 4) 메신저에서 차갑게 보이는 패턴(한국 조직 채팅 문화: 짧은 지시, 공개 지적, 마침표)
        {
            "slug": "chat-tone-feels-cold",
            "title": "메신저에서 유독 차갑게 보이는 말투 3가지와 안전한 대체 문장",
            "description": "짧은 지시, 공개 지적, 끊어 말하기가 왜 갈등을 만드는지와 해결 방법",
            "content_html": """
<h1>메신저에서 유독 차갑게 보이는 말투 3가지와 안전한 대체 문장</h1>
<p>메신저는 빠르고 편하지만, 문장이 짧아질수록 의도가 빠져나가 ‘차갑게’ 읽히기 쉽습니다. 특히 업무 채팅에서는 작은 표현 차이가 관계 비용으로 이어지곤 합니다.</p>

<h2>1) 단어만 던지는 지시형 문장</h2>
<p><strong>전:</strong> “오늘까지.”<br>
<strong>후:</strong> “오늘 중으로 필요해서요. 가능하시면 오늘까지 부탁드립니다.”</p>

<h2>2) 공개 채널에서의 실수 지적</h2>
<p>공개 지적은 내용보다 감정이 먼저 전달될 수 있습니다. 공개 채널에서는 사실만 짧게, 자세한 내용은 별도로 전달하는 편이 안전합니다.</p>
<ul>
  <li>“이 부분은 이렇게 해석될 수 있어서 확인이 필요합니다. 한 번만 점검 부탁드립니다.”</li>
  <li>“세부 내용은 따로 공유드릴게요. 여기서는 결론만 정리하겠습니다.”</li>
</ul>

<h2>3) 끊어 말하기(짧은 문장 여러 번)</h2>
<p>물음표나 한 단어를 반복해서 보내면 상대는 압박을 강하게 느낍니다. 한 번에 맥락과 요청을 담는 편이 좋습니다.</p>
<p><strong>대체:</strong> “일정 때문에 확인이 필요합니다. 가능하실 때 회신 부탁드립니다.”</p>

<p>메신저에서는 길게 쓰기보다, “의도 표시”를 한 줄만 더하는 것이 가장 효과적입니다.</p>
""".strip(),
        },

        # 5) 긴급 요청을 무례하지 않게(‘최대한 빨리’ 중심)
        {
            "slug": "urgent-request-without-sounding-rude",
            "title": "급하다고 말해야 할 때: ‘최대한 빨리’가 무례하지 않게 들리게 하는 법",
            "description": "긴급함은 유지하면서도 압박/비난처럼 보이지 않게 요청하는 문장 구조",
            "content_html": """
<h1>급하다고 말해야 할 때: ‘최대한 빨리’가 무례하지 않게 들리게 하는 법</h1>
<p>급한 상황에서는 문장이 짧아지고, 짧은 문장은 쉽게 ‘명령’처럼 읽힙니다. 긴급함을 숨길 필요는 없지만, “왜 급한지”를 한 줄만 덧붙이면 분위기가 크게 달라집니다.</p>

<h2>긴급 요청이 거칠게 들리는 이유</h2>
<ul>
  <li><strong>상대 사정 무시처럼 보임</strong></li>
  <li><strong>지연 책임을 떠넘기는 느낌</strong></li>
  <li><strong>요청이 지시처럼 읽힘</strong></li>
</ul>

<h2>긴급함은 유지하고, 톤만 바꾸는 3요소</h2>
<ul>
  <li><strong>상황</strong>: 왜 급한지 한 문장</li>
  <li><strong>요청</strong>: 무엇을 언제까지 원하는지</li>
  <li><strong>완충</strong>: “가능하시면”, “편하실 때” 같은 신호</li>
</ul>

<h2>예시</h2>
<p><strong>전:</strong> “오늘 안에 꼭 주세요. 최대한 빨리요.”<br>
<strong>후:</strong> “오늘 중으로 반영이 필요해서요. 가능하시면 오늘 안에 공유 부탁드립니다.”</p>

<p>핵심은 상대가 ‘압박’이 아니라 ‘조율’로 읽게 만드는 것입니다.</p>
""".strip(),
        },

        # 6) 짧은 회신이 차갑게 보이는 문제(‘검토 요청’/‘확인’/‘알겠습니다’)
        {
            "slug": "short-replies-sound-cold",
            "title": "짧은 회신이 차갑게 들리는 이유: 한 문장만 더해도 달라집니다",
            "description": "‘확인했습니다’만 보내면 오해가 생기는 이유와, 다음 행동을 붙여 해결하는 방법",
            "content_html": """
<h1>짧은 회신이 차갑게 들리는 이유: 한 문장만 더해도 달라집니다</h1>
<p>업무에서는 빠르게 답하는 게 중요하지만, 너무 짧은 회신은 종종 ‘거리감’이나 ‘무성의’로 읽힐 수 있습니다.</p>

<h2>오해가 생기는 이유</h2>
<ul>
  <li><strong>다음 단계가 보이지 않음</strong>: “확인했습니다”만 있으면 상대는 “그래서 이제 뭐가 되지?”를 떠올립니다.</li>
  <li><strong>감정/의도 정보가 없음</strong>: 고맙다/수고했다 같은 신호가 빠지면 차갑게 느껴질 수 있습니다.</li>
  <li><strong>협업의 흐름이 끊김</strong>: 답이 ‘끝’처럼 보여서 다시 물어봐야 합니다.</li>
</ul>

<h2>해결: ‘다음 행동’을 한 문장으로 붙이기</h2>
<ul>
  <li>“확인했습니다. 말씀하신 내용 반영해서 진행하겠습니다.”</li>
  <li>“확인했습니다. 오늘 중으로 수정해서 다시 공유드리겠습니다.”</li>
  <li>“확인했습니다. 추가로 확인이 필요한 부분이 있으면 다시 말씀드리겠습니다.”</li>
</ul>

<h2>예시</h2>
<p><strong>전:</strong> “확인했습니다.”<br>
<strong>후:</strong> “확인했습니다. 말씀하신 방향으로 반영해서 진행하겠습니다.”</p>

<p>짧음은 유지하되, 상대가 다음 흐름을 예측할 수 있게 만드는 것이 포인트입니다.</p>
""".strip(),
        },

        # 7) 피드백/지적을 부드럽게(한국 문화: 체면/방어심 고려)
        {
            "slug": "feedback-without-hurting-feelings",
            "title": "피드백이 ‘공격’으로 읽히지 않게: 협업 톤을 지키는 문장 구조",
            "description": "단정·비난을 피하고, 사실-영향-제안으로 전달하는 방법",
            "content_html": """
<h1>피드백이 ‘공격’으로 읽히지 않게: 협업 톤을 지키는 문장 구조</h1>
<p>피드백은 필요하지만, 텍스트에서는 의도보다 ‘평가’가 먼저 보이기 쉽습니다. 특히 한국 문화에서는 공개적인 지적이 체면을 건드릴 수 있어 더 민감하게 작동합니다.</p>

<h2>공격으로 읽히는 피드백의 공통점</h2>
<ul>
  <li><strong>단정</strong>: “말이 안 됩니다”, “틀렸습니다”</li>
  <li><strong>사람을 겨냥</strong>: “왜 이렇게 하셨어요?”(행동이 아니라 사람을 지적하는 느낌)</li>
  <li><strong>대안 없음</strong>: 문제만 말하고 끝</li>
</ul>

<h2>안전한 구조: 사실 → 영향 → 제안</h2>
<ul>
  <li><strong>사실</strong>: “현재 문서에서 이 부분이 이렇게 적혀 있습니다.”</li>
  <li><strong>영향</strong>: “이대로면 다음 단계에서 혼동이 생길 수 있습니다.”</li>
  <li><strong>제안</strong>: “이 문장을 이렇게 바꾸면 더 명확할 것 같습니다.”</li>
</ul>

<h2>예시</h2>
<p><strong>전:</strong> “이거 별로인데요.”<br>
<strong>후:</strong> “이 부분은 이렇게 해석될 수 있어서 혼동이 생길 것 같습니다. 문장을 이렇게 바꾸면 더 명확해질 것 같아요.”</p>

<p>피드백은 ‘지적’이 아니라 ‘개선 제안’으로 읽히게 만들면, 실제로 반영 속도도 빨라집니다.</p>
""".strip(),
        },

        # 8) 거절/대안 제시
        {
            "slug": "say-no-politely-with-alternatives",
            "title": "거절해야 할 때: ‘안 됩니다’ 대신 관계를 지키는 말",
            "description": "존중-사유-대안 3단 구성으로 거절을 부드럽게 만드는 방법",
            "content_html": """
<h1>거절해야 할 때: ‘안 됩니다’ 대신 관계를 지키는 말</h1>
<p>거절 자체보다, 거절이 ‘무시’로 읽힐 때 문제가 커집니다. 특히 텍스트에서는 짧은 거절이 쉽게 차갑게 보입니다.</p>

<h2>거절이 거칠게 들리는 이유</h2>
<ul>
  <li><strong>요청을 인정하는 문장이 없음</strong></li>
  <li><strong>사유가 없어서 회피처럼 보임</strong></li>
  <li><strong>대안이 없어서 대화가 끊김</strong></li>
</ul>

<h2>안전한 3단 구조: 존중 → 사유 → 대안</h2>
<ul>
  <li><strong>존중</strong>: “요청 주신 내용 확인했습니다.”</li>
  <li><strong>사유(짧게)</strong>: “현재 일정상 오늘은 어렵습니다.”</li>
  <li><strong>대안</strong>: “대신 내일 오전까지는 가능합니다.”</li>
</ul>

<h2>예시</h2>
<p><strong>전:</strong> “그건 안 됩니다.”<br>
<strong>후:</strong> “요청 주신 내용 확인했습니다. 오늘은 일정상 진행이 어려울 것 같습니다. 대신 내일 오전까지는 가능하니 그 방향으로 진행해도 될까요?”</p>

<p>거절을 ‘끝’으로 만들지 말고, 협업의 ‘범위 조정’으로 보이게 만드는 것이 핵심입니다.</p>
""".strip(),
        },

        # 9) 인사/맺음말(과장 없이)
        {
            "slug": "greetings-that-soften-tone",
            "title": "인사 한 줄이 톤을 바꿉니다: 서두·맺음말이 필요한 순간",
            "description": "모든 메시지에 인사가 필요한 건 아니지만, 오해를 줄이는 최소 표현들",
            "content_html": """
<h1>인사 한 줄이 톤을 바꿉니다: 서두·맺음말이 필요한 순간</h1>
<p>모든 메시지에 인사가 필수는 아닙니다. 하지만 특정 상황에서는 인사나 맺음말이 없을 때 ‘무례’로 읽힐 가능성이 커집니다.</p>

<h2>인사가 없으면 오해가 커지는 상황</h2>
<ul>
  <li><strong>첫 연락</strong>: 상대가 나를 잘 모를 때</li>
  <li><strong>요청/마감이 있는 메시지</strong>: 지시처럼 읽히기 쉬울 때</li>
  <li><strong>외부/고객 연락</strong>: 관계 신뢰가 중요한 상황</li>
</ul>

<h2>과장 없이 넣는 최소 표현</h2>
<ul>
  <li><strong>서두</strong>: “안녕하세요. 문의드립니다.” / “안녕하세요, ○○○입니다.”</li>
  <li><strong>완충</strong>: “가능하실 때 확인 부탁드립니다.”</li>
  <li><strong>마무리</strong>: “감사합니다.” / “확인 부탁드립니다.”</li>
</ul>

<h2>예시</h2>
<p><strong>전:</strong> “첨부 확인하고 회신 주세요.”<br>
<strong>후:</strong> “안녕하세요. 첨부 확인 부탁드립니다. 가능하실 때 회신 주시면 감사하겠습니다.”</p>

<p>인사는 예의가 아니라, 텍스트에서 사라진 ‘톤 정보’를 보충하는 장치라고 생각하면 편합니다.</p>
""".strip(),
        },

        # 10) 장문(벽문장) 줄이기
        {
            "slug": "avoid-walls-of-text",
            "title": "장문 메시지는 일을 더 늦춥니다: 읽히는 구조로 정리하는 법",
            "description": "핵심이 묻히는 장문을 ‘결론-요청-이유’ 구조로 빠르게 정리하는 방법",
            "content_html": """
<h1>장문 메시지는 일을 더 늦춥니다: 읽히는 구조로 정리하는 법</h1>
<p>길게 설명하면 친절해 보일 수 있지만, 실제로는 상대가 핵심을 찾아야 해서 회신이 늦어지는 경우가 많습니다. 특히 메신저에서는 장문이 부담으로 느껴지기 쉽습니다.</p>

<h2>장문이 문제를 만드는 이유</h2>
<ul>
  <li><strong>핵심이 안 보임</strong>: 결론과 요청이 중간에 파묻힙니다.</li>
  <li><strong>상대의 부담 증가</strong>: 해야 할 일을 ‘추출’해야 합니다.</li>
  <li><strong>오해 확률 증가</strong>: 문장이 길수록 해석 여지가 늘어납니다.</li>
</ul>

<h2>가장 안전한 구조: 결론 → 요청 → 이유</h2>
<ul>
  <li><strong>결론(1~2줄)</strong>: 지금 상황과 방향</li>
  <li><strong>요청(1줄)</strong>: 상대가 해줘야 할 행동</li>
  <li><strong>이유(1줄)</strong>: 왜 지금 필요한지</li>
</ul>

<h2>예시</h2>
<p><strong>후(정리된 형태):</strong><br>
“결론: 이번 건은 A 방향으로 진행하려고 합니다.<br>
요청: 오늘 오후 5시 전 확인 부탁드립니다.<br>
이유: 내일 일정에 반영이 필요합니다.”</p>

<p>상대가 ‘읽는 사람’이 아니라 ‘일을 진행시키는 사람’이라는 관점으로 구조를 잡으면, 회신 속도가 눈에 띄게 달라집니다.</p>
""".strip(),
        },
        # 11) 메일 보내기 전 점검
        {
            "slug": "before-send-tone-check",
            "title": "메일 보내기 전, 말투 한 번 더 확인하세요",
            "description": "보내기 버튼을 누르기 전 10초 점검으로 오해를 줄이는 방법. 요청·마감·피드백 메일에서 특히 효과적인 문장 구조와 예시를 정리했습니다.",
            "content_html": """
    <h1>메일 보내기 전, 말투 한 번 더 확인하세요</h1>
    <p>업무 메일은 내용보다 ‘말투’에서 오해가 생기는 경우가 많습니다. 같은 요청이라도 문장 구조가 조금만 달라지면 상대가 느끼는 압박과 협업 태도가 크게 달라집니다.</p>
    
    <h2>왜 ‘보내기 전 점검’이 필요한가</h2>
    <ul>
      <li><strong>표정과 억양이 없다</strong>: 짧은 문장은 쉽게 지시처럼 읽힙니다.</li>
      <li><strong>상대는 맥락을 모른다</strong>: 내가 급한 이유를 상대가 추측해야 합니다.</li>
      <li><strong>회신이 늦어지면 일이 멈춘다</strong>: 오해가 생기면 확인 질문이 늘고, 속도가 떨어집니다.</li>
    </ul>
    
    <h2>10초 점검 체크리스트</h2>
    <ul>
      <li><strong>내가 원하는 행동이 한 문장에 명확한가</strong>: 확인/승인/공유/회신 중 무엇인지</li>
      <li><strong>왜 지금 필요한지 한 줄이 있는가</strong>: 일정, 의사결정, 다음 단계와 연결</li>
      <li><strong>완충 표현이 있는가</strong>: “가능하시면”, “편하실 때”, “확인 부탁드립니다”</li>
      <li><strong>마감이 있다면 최소한으로 제시했는가</strong>: “오늘 중”, “오후 3시 전”처럼 짧게</li>
    </ul>
    
    <h2>가장 안전한 문장 구조</h2>
    <p><strong>상황 1줄 → 요청 1줄 → (필요하면) 시간 1줄</strong></p>
    <ul>
      <li>상황: “내일 일정 반영 때문에 확인이 필요합니다.”</li>
      <li>요청: “가능하실 때 승인 여부를 알려주시면 감사하겠습니다.”</li>
      <li>시간: “가능하시면 오늘 오후 5시 전 확인 부탁드립니다.”</li>
    </ul>
    
    <h2>짧은 예시</h2>
    <p><strong>전:</strong> “오늘 안에 주세요.”<br>
    <strong>후:</strong> “오늘 중 반영이 필요해서 확인 부탁드립니다. 가능하시면 오늘 안에 공유 부탁드립니다.”</p>
    
    <h2>마무리</h2>
    <p>메일을 길게 쓰라는 뜻이 아닙니다. 같은 내용이라도 ‘의도 신호’를 한 줄만 더하면 오해가 줄고, 회신 속도가 빨라집니다. 문장을 보내기 전 10초만 점검해도 협업 비용이 내려갑니다.</p>
    <p>문장을 붙여 넣고 상황에 맞게 말투를 정리하고 싶다면, 렉시노아로 한 번 더 다듬어 보세요.</p>
    """.strip(),
        },

        # 12) 이대로 보내도 괜찮을까요?
        {
            "slug": "is-this-email-ok-to-send",
            "title": "업무 메일, 이대로 보내도 괜찮을까요?",
            "description": "‘무례해 보일까’ ‘압박처럼 들릴까’가 걱정될 때 확인해야 하는 4가지 포인트와, 바로 적용 가능한 대체 문장을 제공합니다.",
            "content_html": """
    <h1>업무 메일, 이대로 보내도 괜찮을까요?</h1>
    <p>업무 메일을 작성하고도 마지막에 불안해지는 이유는 대개 하나입니다. 내용은 맞는데, 상대가 어떻게 받아들일지 확신이 없기 때문입니다.</p>
    
    <h2>불안해지는 메일의 공통점</h2>
    <ul>
      <li><strong>요청이 지시처럼 보인다</strong>: “하세요”, “주세요” 형태가 짧게 끝남</li>
      <li><strong>상대 사정이 지워진다</strong>: 완충 없이 마감만 강조</li>
      <li><strong>맥락이 생략된다</strong>: 상대가 ‘왜 지금’인지 추측해야 함</li>
      <li><strong>다음 단계가 불명확하다</strong>: 확인 후 무엇이 달라지는지 안 보임</li>
    </ul>
    
    <h2>보내기 전 4가지 확인</h2>
    <ul>
      <li><strong>관계</strong>: 상사/동료/외부 파트너에 맞는 톤인가</li>
      <li><strong>상황</strong>: 일정/의사결정/장애 대응 등 급한 이유가 한 줄로 설명되는가</li>
      <li><strong>요청</strong>: 무엇을 해주면 되는지 명확한가</li>
      <li><strong>마감</strong>: 정말 필요할 때만, 최소한으로 제시했는가</li>
    </ul>
    
    <h2>바로 쓰는 대체 문장</h2>
    <ul>
      <li>“확인해 주세요” → “가능하실 때 확인 부탁드립니다.”</li>
      <li>“빨리 부탁드립니다” → “일정 반영 때문에 확인이 필요합니다. 가능하시면 오늘 중 부탁드립니다.”</li>
      <li>“왜 안 됐나요?” → “진행 상황 확인이 필요해서요. 현재 상태 공유 부탁드립니다.”</li>
    </ul>
    
    <h2>예시</h2>
    <p><strong>전:</strong> “자료 아직인가요? 오늘 안에 주세요.”<br>
    <strong>후:</strong> “일정 조율 때문에 진행 상황 확인이 필요합니다. 가능하시면 오늘 중으로 자료 공유 부탁드립니다.”</p>
    
    <h2>마무리</h2>
    <p>‘정중한 표현’ 자체가 목적이 아니라, 상대가 방어적으로 읽지 않게 만드는 것이 목적입니다. 상황과 요청을 한 줄씩만 보완해도 문장의 체감 온도는 달라집니다.</p>
    <p>초안을 빠르게 다듬고 싶다면, 렉시노아로 문장을 넣고 말투를 정리해 보세요.</p>
    """.strip(),
        },

        # 13) 메일 말투 점검 5초
        {
            "slug": "tone-check-in-five-seconds",
            "title": "메일 말투 점검, 5초면 충분합니다",
            "description": "업무 메일에서 오해를 만드는 핵심은 ‘부족한 정보’입니다. 5초 점검 규칙(상황·요청·다음 단계)으로 말투를 안정적으로 만드는 방법을 안내합니다.",
            "content_html": """
    <h1>메일 말투 점검, 5초면 충분합니다</h1>
    <p>메일에서 말투가 거칠게 보이는 이유는 대부분 ‘예의가 부족해서’가 아니라 ‘정보가 부족해서’입니다. 상대는 텍스트만 보고 의도를 추정해야 하므로, 짧은 문장이 오해를 만들기 쉽습니다.</p>
    
    <h2>5초 점검 규칙</h2>
    <ul>
      <li><strong>상황</strong>: 왜 지금 이 메시지를 보내는가</li>
      <li><strong>요청</strong>: 상대가 해야 할 행동은 무엇인가</li>
      <li><strong>다음 단계</strong>: 확인/회신 후 무엇이 진행되는가</li>
    </ul>
    
    <h2>점검 전후 차이</h2>
    <p><strong>전:</strong> “검토해서 회신 주세요.”<br>
    <strong>후:</strong> “오늘 의사결정이 필요해서요. 가능하실 때 검토 후 의견 회신 부탁드립니다. 회신 주시면 그 방향으로 바로 반영하겠습니다.”</p>
    
    <h2>자주 쓰는 문장 3가지 리모델링</h2>
    <ul>
      <li><strong>요청</strong>: “확인 부탁드립니다” → “일정 반영 때문에 확인 부탁드립니다.”</li>
      <li><strong>리마인드</strong>: “확인차 연락드립니다” → “다음 단계 진행을 위해 진행 상황 확인이 필요합니다.”</li>
      <li><strong>승인</strong>: “승인 바랍니다” → “오늘 중 확정이 필요합니다. 가능하시면 승인 부탁드립니다.”</li>
    </ul>
    
    <h2>마무리</h2>
    <p>완벽한 문장을 쓰는 것보다, 오해가 생길 요소를 제거하는 것이 더 중요합니다. 상황·요청·다음 단계를 한 줄씩만 보완하면 말투가 안정되고, 회신도 빨라집니다.</p>
    <p>문장을 빠르게 점검하고 싶다면, 렉시노아로 초안을 다듬어 보세요.</p>
    """.strip(),
        },

        # 14) 직장인 이메일 말투 자동 정리
        {
            "slug": "work-email-tone-polish",
            "title": "직장인 이메일 말투, ‘내용은 그대로’ 두고 부드럽게 만드는 법",
            "description": "내용을 바꾸지 않고도 말투를 부드럽게 만들 수 있습니다. 완충 표현, 이유 한 줄, 요청의 명확화로 오해를 줄이는 실전 방법을 정리했습니다.",
            "content_html": """
    <h1>직장인 이메일 말투, ‘내용은 그대로’ 두고 부드럽게 만드는 법</h1>
    <p>업무에서 중요한 것은 빠르게 전하는 것이지만, 빠름이 곧 거칠음이 되면 협업 비용이 늘어납니다. 핵심은 ‘내용을 바꾸지 않고 말투만 정리’하는 것입니다.</p>
    
    <h2>말투를 부드럽게 만드는 3가지 레버</h2>
    <ul>
      <li><strong>완충 표현</strong>: 부탁의 형태를 만들어 긴장도를 낮춥니다.</li>
      <li><strong>이유 한 줄</strong>: 상대가 ‘왜 지금’인지 이해하면 압박으로 덜 느낍니다.</li>
      <li><strong>요청 명확화</strong>: 상대가 해야 할 행동이 분명하면 불필요한 왕복이 줄어듭니다.</li>
    </ul>
    
    <h2>자주 발생하는 오해 패턴</h2>
    <ul>
      <li>“오늘까지”처럼 결론만 있는 메시지</li>
      <li>“확인”처럼 다음 행동이 없는 회신</li>
      <li>상대 책임을 전제로 읽히는 표현</li>
    </ul>
    
    <h2>전/후 예시</h2>
    <p><strong>전:</strong> “자료 보내주세요. 오늘까지요.”<br>
    <strong>후:</strong> “오늘 중 반영이 필요해서요. 가능하시면 자료를 오늘까지 공유 부탁드립니다.”</p>
    
    <p><strong>전:</strong> “확인했습니다.”<br>
    <strong>후:</strong> “확인했습니다. 말씀하신 방향으로 반영해서 진행하겠습니다.”</p>
    
    <h2>마무리</h2>
    <p>업무에서는 문장을 꾸미는 것보다 ‘오해를 줄이는 구조’를 갖추는 것이 훨씬 효과적입니다. 내용은 유지하되, 상대가 방어적으로 읽지 않게 만드는 신호를 한 줄만 더해보세요.</p>
    <p>초안을 빠르게 정리하려면 렉시노아로 문장을 다듬어 보실 수 있습니다.</p>
    """.strip(),
        },

        # 15) 리마인드(회신 받기)
        {
            "slug": "reminder-that-gets-replies",
            "title": "리마인드 메일, 재촉처럼 안 들리면서 회신 받는 방법",
            "description": "회신이 필요하지만 재촉은 부담스러울 때, ‘맥락-요청-시간’ 3단 구성으로 정중하면서도 효과적으로 답을 받는 문장 템플릿을 제공합니다.",
            "content_html": """
    <h1>리마인드 메일, 재촉처럼 안 들리면서 회신 받는 방법</h1>
    <p>회신이 늦어지면 확인이 필요합니다. 하지만 말투가 거칠어지면 오히려 답이 늦어지거나 관계 비용이 생길 수 있습니다. 리마인드는 ‘재촉’이 아니라 ‘조율’로 읽히게 만들어야 합니다.</p>
    
    <h2>리마인드가 싫게 들리는 순간</h2>
    <ul>
      <li><strong>원하는 행동이 없다</strong>: “확인차 연락드립니다”만 있는 경우</li>
      <li><strong>상대 탓처럼 보인다</strong>: “아직도 안 됐나요?” 같은 표현</li>
      <li><strong>마감만 강조된다</strong>: 이유 없이 “오늘까지”만 반복</li>
    </ul>
    
    <h2>답이 오는 3단 구성</h2>
    <ul>
      <li><strong>맥락 1줄</strong>: “다음 일정 반영 때문에 확인이 필요합니다.”</li>
      <li><strong>요청 1줄</strong>: “가능하실 때 진행 상태 공유 부탁드립니다.”</li>
      <li><strong>시간 1줄(필요 시)</strong>: “가능하시면 오늘 오후 5시 전 부탁드립니다.”</li>
    </ul>
    
    <h2>문장 템플릿</h2>
    <ul>
      <li>“일정 조율 때문에 확인이 필요합니다. 가능하실 때 현재 진행 상태 공유 부탁드립니다.”</li>
      <li>“다음 단계 진행을 위해 승인 여부 확인이 필요합니다. 가능하시면 오늘 중 회신 부탁드립니다.”</li>
      <li>“의사결정이 필요한 부분이 있어요. 편하실 때 의견 부탁드립니다.”</li>
    </ul>
    
    <h2>마무리</h2>
    <p>리마인드에서 중요한 것은 ‘상대가 해야 할 일’을 명확하게 하되, 감정이 섞인 신호를 빼는 것입니다. 맥락과 요청을 한 줄씩만 보강해도 회신율이 달라집니다.</p>
    <p>문장을 상황에 맞게 빠르게 정리하고 싶다면 렉시노아로 다듬어 보세요.</p>
    """.strip(),
        },

        # 16) 통계/흐름 기반(과장 없이)
        {
            "slug": "ai-tone-check-trend",
            "title": "요즘은 메일 보내기 전에 ‘말투 점검’을 한 번 더 합니다",
            "description": "업무 커뮤니케이션이 텍스트 중심으로 바뀌면서 ‘말투 점검’이 생산성의 일부가 됐습니다. 오해를 줄이고 회신 속도를 올리는 실전 기준을 정리했습니다.",
            "content_html": """
    <h1>요즘은 메일 보내기 전에 ‘말투 점검’을 한 번 더 합니다</h1>
    <p>업무 커뮤니케이션이 텍스트 중심으로 옮겨오면서, 말투는 ‘매너’가 아니라 ‘효율’의 문제가 됐습니다. 오해가 생기면 일정이 밀리고, 확인 질문이 늘고, 결국 일이 느려집니다.</p>
    
    <h2>말투 점검이 곧 생산성인 이유</h2>
    <ul>
      <li><strong>오해 비용 감소</strong>: 불필요한 감정 소모와 설명이 줄어듭니다.</li>
      <li><strong>회신 속도 증가</strong>: 요청과 다음 단계가 명확해집니다.</li>
      <li><strong>협업 신뢰 유지</strong>: 문장 하나로 관계가 삐걱거리는 상황을 예방합니다.</li>
    </ul>
    
    <h2>점검 기준은 복잡하지 않습니다</h2>
    <ul>
      <li><strong>상황 한 줄</strong>: 왜 지금 필요한지</li>
      <li><strong>요청 한 줄</strong>: 무엇을 원하고, 어떤 형태의 답이 필요한지</li>
      <li><strong>다음 단계 한 줄</strong>: 회신 후 무엇이 진행되는지</li>
    </ul>
    
    <h2>예시</h2>
    <p><strong>전:</strong> “이거 수정하세요.”<br>
    <strong>후:</strong> “이 부분이 다음 단계에 영향이 있어서 확인이 필요합니다. 가능하시면 해당 부분 수정 후 다시 공유 부탁드립니다.”</p>
    
    <h2>마무리</h2>
    <p>말투 점검은 “더 공손하게”가 아니라 “더 명확하게”에 가깝습니다. 문장 구조를 정리하면 오해가 줄고, 협업이 빨라집니다. 초안을 빠르게 다듬고 싶다면 렉시노아로 말투를 점검해 보세요.</p>
    """.strip(),
        },
    ],

    "en": [
        # 1) Email tone misread
        {
            "slug": "why-your-email-sounds-rude",
            "title": "Why Your Email Sounds Rude (Even When You Don’t Mean It)",
            "description": "Why tone gets lost in email—and how to fix it without overthinking.",
            "content_html": """
<h1>Why Your Email Sounds Rude (Even When You Don’t Mean It)</h1>
<p>Have you ever re-read an email and realized it sounded harsher than you intended?</p>

<h2>The medium removes tone</h2>
<p>Email strips away facial expressions, voice, and timing. What’s left is plain text—easy to misread as cold, demanding, or impatient.</p>

<h2>Why it’s worse at work</h2>
<ul>
  <li><strong>Time pressure</strong> leads to short messages with fewer softeners.</li>
  <li><strong>Hierarchy</strong> makes requests feel like commands.</li>
  <li><strong>Missing context</strong> forces the reader to guess your intent.</li>
</ul>

<h2>A better approach</h2>
<p>Keep the message, add a small signal of intent: a softener, a one-line reason, and a clear action.</p>

<h2>Quick example</h2>
<p><strong>Before:</strong> “Send it today.”<br>
<strong>After:</strong> “We need it to stay on schedule—could you share it today if possible?”</p>
""".strip(),
        },

        # 2) Passive-aggressive phrases
        {
            "slug": "passive-aggressive-email-phrases",
            "title": "Phrases That Can Sound Passive-Aggressive in Email (and What to Say Instead)",
            "description": "Why certain “standard” phrases land badly—and safer alternatives that still get results.",
            "content_html": """
<h1>Phrases That Can Sound Passive-Aggressive in Email (and What to Say Instead)</h1>
<p>Even if your intent is neutral, some email phrases can sound like blame, sarcasm, or pressure—because tone is missing.</p>

<h2>Common phrases that get misread</h2>
<ul>
  <li><strong>“As per my last email…”</strong> (can imply “you didn’t read it”)</li>
  <li><strong>“Please advise.”</strong> (can feel like responsibility-dumping)</li>
  <li><strong>“Friendly reminder…”</strong> (often reads like a nudge-with-attitude)</li>
  <li><strong>“Noted.”</strong> (can feel cold or dismissive)</li>
  <li><strong>“Thanks in advance.”</strong> (can feel like implied obligation)</li>
</ul>

<h2>What works better</h2>
<p>Remove blame, add context, and make the action explicit.</p>
<ul>
  <li>“Resharing this since it’s important for the next step—could you take a look?”</li>
  <li>“When you have a moment, could you recommend A vs B? I’m leaning A because…”</li>
  <li>“We’re coordinating the timeline—could you confirm by end of day if possible?”</li>
  <li>Instead of “Noted,” add the next step: “Got it—I’ll proceed with X.”</li>
</ul>

<h2>Example rewrite</h2>
<p><strong>Before:</strong> “As per my last email, please advise.”<br>
<strong>After:</strong> “Resharing my note below since it affects scheduling. When you have a moment, could you advise on the best next step?”</p>
""".strip(),
        },

        # 3) Follow-up without being annoying
        {
            "slug": "follow-up-without-being-annoying",
            "title": "How to Follow Up Without Sounding Annoying",
            "description": "Why “just checking in” often fails—and a simple structure that gets replies.",
            "content_html": """
<h1>How to Follow Up Without Sounding Annoying</h1>
<p>Follow-ups are necessary. But vague follow-ups create friction: the recipient feels pinged without knowing what you want.</p>

<h2>Why vague follow-ups get ignored (or resented)</h2>
<ul>
  <li><strong>No clear action</strong>: “Just checking in” doesn’t specify what to do.</li>
  <li><strong>Low context</strong>: it feels like inbox-pushing.</li>
  <li><strong>Implicit blame</strong>: “Did you see my email?” can sound accusatory.</li>
</ul>

<h2>A follow-up structure that works</h2>
<ul>
  <li><strong>Context (1 line)</strong>: why you’re asking now</li>
  <li><strong>Action (1 line)</strong>: status, approval, confirmation</li>
  <li><strong>Timing (optional)</strong>: only if needed</li>
</ul>

<h2>Examples</h2>
<ul>
  <li>“We’re finalizing the schedule—could you share a quick status update when you can?”</li>
  <li>“If possible, could you confirm by end of day? I’m coordinating dependencies on my end.”</li>
  <li>“We need a decision between A/B to proceed—when you have a moment, which do you prefer?”</li>
</ul>
""".strip(),
        },

        # 4) Chat tone patterns (Slack/Teams)
        {
            "slug": "chat-tone-feels-cold",
            "title": "3 Chat Habits That Make You Sound Cold (and Easy Fixes)",
            "description": "Short demands, public call-outs, and rapid pings often land harsher than intended—here’s how to soften them.",
            "content_html": """
<h1>3 Chat Habits That Make You Sound Cold (and Easy Fixes)</h1>
<p>In fast-paced chat, messages get short—and short messages lose intent. Small adjustments can prevent unnecessary friction.</p>

<h2>1) One-word demands</h2>
<p><strong>Too blunt:</strong> “Today.”<br>
<strong>Better:</strong> “We need this today to stay on schedule—could you share it if possible?”</p>

<h2>2) Public call-outs</h2>
<p>Pointing out mistakes publicly can trigger defensiveness. Keep channels outcome-focused; move details to a thread or DM.</p>
<ul>
  <li>“I think this might be read as A—can we confirm whether B is correct?”</li>
  <li>“I’ll DM the details—posting the summary here.”</li>
</ul>

<h2>3) Rapid pings</h2>
<p>Multiple short pings feel like pressure. Combine them into one message with context + action.</p>
<p><strong>Better:</strong> “Quick check for scheduling—could you share the current status when you can?”</p>
""".strip(),
        },

        # 5) Urgent requests
        {
            "slug": "urgent-request-without-sounding-rude",
            "title": "How to Make an Urgent Request Without Sounding Rude",
            "description": "Keep urgency while removing pressure by adding a one-line reason and a clear request.",
            "content_html": """
<h1>How to Make an Urgent Request Without Sounding Rude</h1>
<p>Urgency isn’t the problem. Lack of context is. A short urgent message can sound like a demand.</p>

<h2>Why urgent messages land badly</h2>
<ul>
  <li>They can ignore the recipient’s workload</li>
  <li>They can imply blame</li>
  <li>They often read like commands</li>
</ul>

<h2>A simple 3-part structure</h2>
<ul>
  <li><strong>Reason</strong>: why it’s urgent (1 sentence)</li>
  <li><strong>Request</strong>: what you need and by when</li>
  <li><strong>Softener</strong>: “if possible,” “when you can”</li>
</ul>

<h2>Example</h2>
<p><strong>Too harsh:</strong> “Need this today.”<br>
<strong>Better:</strong> “We need this to keep the timeline on track—could you share it today if possible?”</p>
""".strip(),
        },

        # 6) Short replies
        {
            "slug": "short-replies-sound-cold",
            "title": "Why Short Replies Sound Cold (and a One-Sentence Fix)",
            "description": "“Noted” and “OK” feel efficient, but they often hide the next step—add one line and the tone changes.",
            "content_html": """
<h1>Why Short Replies Sound Cold (and a One-Sentence Fix)</h1>
<p>Short replies are efficient. But in text, efficiency can look like indifference—especially when the next step isn’t clear.</p>

<h2>Why it gets misread</h2>
<ul>
  <li><strong>No next step</strong>: the reader wonders what happens now</li>
  <li><strong>No intent signal</strong>: gratitude or acknowledgement is missing</li>
  <li><strong>Conversation stalls</strong>: the other person has to ask again</li>
</ul>

<h2>The fix: add the next step</h2>
<ul>
  <li>“Got it—I'll incorporate this and proceed.”</li>
  <li>“Thanks—I'll update it today and share the revised version.”</li>
  <li>“Understood—I’ll follow up if anything else is needed.”</li>
</ul>

<h2>Example</h2>
<p><strong>Before:</strong> “Noted.”<br>
<strong>After:</strong> “Got it—thanks. I’ll incorporate this and proceed.”</p>
""".strip(),
        },

        # 7) Feedback tone
        {
            "slug": "give-feedback-without-sounding-harsh",
            "title": "How to Give Feedback Without Sounding Harsh",
            "description": "A practical template to keep feedback collaborative: observation → impact → suggestion.",
            "content_html": """
<h1>How to Give Feedback Without Sounding Harsh</h1>
<p>In text, feedback can easily read like judgment. A small structural change makes it feel collaborative.</p>

<h2>What makes feedback feel aggressive</h2>
<ul>
  <li>Absolute statements (“This makes no sense.”)</li>
  <li>“Why did you…” (feels personal)</li>
  <li>No alternative or next step</li>
</ul>

<h2>A safer template: observation → impact → suggestion</h2>
<ul>
  <li><strong>Observation:</strong> “In the doc, A is currently stated as …”</li>
  <li><strong>Impact:</strong> “This might cause confusion in B because …”</li>
  <li><strong>Suggestion:</strong> “Would it help to rephrase it as …?”</li>
</ul>

<h2>Example</h2>
<p><strong>Too harsh:</strong> “This is wrong.”<br>
<strong>Better:</strong> “I think this could be read as A, which might cause confusion in B. Would rephrasing it to C work?”</p>
""".strip(),
        },

        # 8) Saying no
        {
            "slug": "say-no-without-burning-bridges",
            "title": "How to Say No Without Burning Bridges",
            "description": "A simple three-step refusal structure: acknowledge → reason → alternative.",
            "content_html": """
<h1>How to Say No Without Burning Bridges</h1>
<p>Refusing isn’t the issue—making the other person feel dismissed is. In text, short refusals often sound colder than intended.</p>

<h2>Why refusals sound harsh</h2>
<ul>
  <li>No acknowledgement</li>
  <li>No reason (looks like avoidance)</li>
  <li>No alternative (conversation ends abruptly)</li>
</ul>

<h2>The 3-step structure</h2>
<ul>
  <li><strong>Acknowledge:</strong> “Thanks for the request—got it.”</li>
  <li><strong>Reason (brief):</strong> “I can’t fit this in today due to …”</li>
  <li><strong>Alternative:</strong> “I can do it by tomorrow morning / I can handle part of it.”</li>
</ul>

<h2>Example</h2>
<p><strong>Before:</strong> “Can’t do it.”<br>
<strong>After:</strong> “Thanks for the request—unfortunately I can’t fit it in today due to schedule. I can deliver it by tomorrow morning if that works.”</p>
""".strip(),
        },

        # 9) Greetings / sign-offs
        {
            "slug": "greetings-and-signoffs-that-change-tone",
            "title": "How a Simple Greeting Changes Your Email Tone",
            "description": "When greetings/sign-offs matter, and minimal options that feel natural (not overly formal).",
            "content_html": """
<h1>How a Simple Greeting Changes Your Email Tone</h1>
<p>Greetings aren’t always required. But in certain contexts, skipping them makes emails feel abrupt—especially when there’s a request or deadline.</p>

<h2>When it’s worth adding a greeting</h2>
<ul>
  <li>First contact</li>
  <li>External/client communication</li>
  <li>Requests with deadlines</li>
</ul>

<h2>Minimal, natural options</h2>
<ul>
  <li><strong>Openers:</strong> “Hi [Name],” / “Hello,” / “Quick question—”</li>
  <li><strong>Closings:</strong> “Thanks,” / “Appreciate it,” / “Best,”</li>
</ul>

<h2>Example</h2>
<p><strong>Before:</strong> “Review the attachment and reply.”<br>
<strong>After:</strong> “Hi [Name]—could you take a look at the attachment when you have a moment and let me know? Thanks.”</p>
""".strip(),
        },

        # 10) Walls of text
        {
            "slug": "stop-writing-walls-of-text",
            "title": "Why Walls of Text Slow Work Down (and a Simple Fix)",
            "description": "Long emails bury the ask, increase effort, and delay replies—use conclusion → request → reason.",
            "content_html": """
<h1>Why Walls of Text Slow Work Down (and a Simple Fix)</h1>
<p>Long emails feel thorough, but they often slow things down: the recipient has to extract what matters and what you want them to do.</p>

<h2>Why long emails fail</h2>
<ul>
  <li>The ask is buried</li>
  <li>Higher cognitive load</li>
  <li>More room for misinterpretation</li>
</ul>

<h2>The fix: conclusion → request → reason</h2>
<ul>
  <li><strong>Conclusion:</strong> the decision or current state (1–2 lines)</li>
  <li><strong>Request:</strong> what you need from them (1 line)</li>
  <li><strong>Reason:</strong> why it matters (1 line)</li>
</ul>

<h2>Example</h2>
<p><strong>After:</strong><br>
“Conclusion: We should proceed with option A.<br>
Request: Could you approve by 5pm today?<br>
Reason: We need to align dependencies for tomorrow’s launch.”</p>
""".strip(),
        },
 # 11) Before-send check
    {
        "slug": "before-send-tone-check",
        "title": "Before You Hit Send: A 10-Second Tone Check",
        "description": "A simple pre-send checklist to reduce misread tone in work emails—without making your message longer than it needs to be.",
        "content_html": """
<h1>Before You Hit Send: A 10-Second Tone Check</h1>
<p>In work email, misunderstandings often come from tone—not content. The goal isn’t to sound “extra polite.” It’s to prevent your message from reading as cold, demanding, or impatient.</p>

<h2>Why a pre-send check matters</h2>
<ul>
  <li><strong>Email removes voice</strong>: short lines can read like commands.</li>
  <li><strong>Recipients lack context</strong>: they guess your intent.</li>
  <li><strong>Misread tone slows work</strong>: clarifying back-and-forth increases.</li>
</ul>

<h2>The 10-second checklist</h2>
<ul>
  <li><strong>Action</strong>: Is the ask explicit (approve/confirm/share/reply)?</li>
  <li><strong>Reason</strong>: Is there a one-line “why now”?</li>
  <li><strong>Softener</strong>: Do you have “if possible / when you can” where appropriate?</li>
  <li><strong>Timing</strong>: If there’s a deadline, is it minimal and necessary?</li>
</ul>

<h2>A safe structure</h2>
<p><strong>Context → Request → (Optional) Timing</strong></p>

<h2>Example</h2>
<p><strong>Before:</strong> “Send it today.”<br>
<strong>After:</strong> “We need this to stay on schedule—could you share it today if possible?”</p>

<p>If you want to do this quickly every time, Lexinoa can help you polish tone while keeping your original meaning.</p>
""".strip(),
    },

    # 12) Is this OK to send?
    {
        "slug": "is-this-email-ok-to-send",
        "title": "Is This Email OK to Send? 4 Checks for Work Tone",
        "description": "If you’re worried your email sounds too harsh, run these four checks and use the ready-to-copy alternatives.",
        "content_html": """
<h1>Is This Email OK to Send? 4 Checks for Work Tone</h1>
<p>If you hesitate right before sending, it’s usually not because the content is wrong. It’s because you’re unsure how it will land.</p>

<h2>Common reasons emails feel “off”</h2>
<ul>
  <li><strong>Request reads like a command</strong></li>
  <li><strong>No context</strong> (the recipient has to guess why it’s urgent)</li>
  <li><strong>Overemphasis on deadlines</strong></li>
  <li><strong>No next step</strong> (the thread stalls)</li>
</ul>

<h2>Four pre-send checks</h2>
<ul>
  <li><strong>Relationship:</strong> does the tone fit the recipient?</li>
  <li><strong>Situation:</strong> do you include a one-line reason?</li>
  <li><strong>Request:</strong> is the action explicit?</li>
  <li><strong>Deadline:</strong> only if necessary, and keep it minimal.</li>
</ul>

<h2>Quick swaps</h2>
<ul>
  <li>“Check this.” → “Could you take a look when you have a moment?”</li>
  <li>“ASAP.” → “We’re aligning the timeline—could you reply today if possible?”</li>
  <li>“Why isn’t this done?” → “Quick status check so we can plan the next step—where are we at?”</li>
</ul>

<p>If you want to apply these consistently, Lexinoa can rewrite tone while keeping your intent intact.</p>
""".strip(),
    },

    # 13) 5-second tone check
    {
        "slug": "tone-check-in-five-seconds",
        "title": "A 5-Second Tone Check That Prevents Misreads",
        "description": "Most “rude-sounding” emails aren’t rude—they’re missing intent signals. Use this 3-point check: reason, action, next step.",
        "content_html": """
<h1>A 5-Second Tone Check That Prevents Misreads</h1>
<p>Many emails sound harsh not because you’re being rude, but because the message is missing key intent signals.</p>

<h2>The 3-point check</h2>
<ul>
  <li><strong>Reason:</strong> why this matters now</li>
  <li><strong>Action:</strong> what you need the recipient to do</li>
  <li><strong>Next step:</strong> what happens after they respond</li>
</ul>

<h2>Example</h2>
<p><strong>Before:</strong> “Review and reply.”<br>
<strong>After:</strong> “We need to decide today to keep the timeline—could you review and share your recommendation? I’ll proceed based on your reply.”</p>

<p>Want this as a one-click habit? Lexinoa can help you apply it instantly.</p>
""".strip(),
    },

    # 14) Keep meaning, soften tone
    {
        "slug": "keep-meaning-soften-tone",
        "title": "Keep the Meaning, Soften the Tone: A Practical Guide",
        "description": "You don’t need to rewrite your whole email. Add a softener, a one-line reason, and an explicit ask—tone improves immediately.",
        "content_html": """
<h1>Keep the Meaning, Soften the Tone: A Practical Guide</h1>
<p>Speed matters at work. But when speed turns into bluntness, you pay for it later in delays and friction. The fix is to keep your meaning and adjust the delivery.</p>

<h2>Three levers that change tone fast</h2>
<ul>
  <li><strong>Softener:</strong> “when you can,” “if possible,” “could you…”</li>
  <li><strong>One-line reason:</strong> connects urgency to a real constraint</li>
  <li><strong>Explicit ask:</strong> confirm/approve/share/reply</li>
</ul>

<h2>Before/After</h2>
<p><strong>Before:</strong> “Send the file today.”<br>
<strong>After:</strong> “We need it to keep the schedule—could you send the file today if possible?”</p>

<p>Lexinoa helps you do this consistently without overthinking each sentence.</p>
""".strip(),
    },

    # 15) Follow-up that gets replies
    {
        "slug": "reminder-that-gets-replies",
        "title": "Follow-Ups That Get Replies Without Sounding Pushy",
        "description": "Use a simple structure—context, action, timing—to turn follow-ups into coordination instead of pressure.",
        "content_html": """
<h1>Follow-Ups That Get Replies Without Sounding Pushy</h1>
<p>Follow-ups are necessary, but vague pings create friction. The goal is to make your message read as coordination, not blame.</p>

<h2>What makes follow-ups feel pushy</h2>
<ul>
  <li>No clear action</li>
  <li>Implicit blame (“Did you see my email?”)</li>
  <li>Deadline without context</li>
</ul>

<h2>A structure that works</h2>
<ul>
  <li><strong>Context:</strong> why you’re checking now</li>
  <li><strong>Action:</strong> what you need (status/approval/confirmation)</li>
  <li><strong>Timing (optional):</strong> only if necessary</li>
</ul>

<h2>Examples</h2>
<ul>
  <li>“We’re finalizing the schedule—could you share a quick status update when you can?”</li>
  <li>“To keep dependencies aligned, could you confirm by end of day if possible?”</li>
</ul>

<p>Lexinoa can generate a clean follow-up in your preferred tone and level of formality.</p>
""".strip(),
    },

    # 16) Trend / productivity framing
    {
        "slug": "ai-tone-check-trend",
        "title": "Why Tone Checks Are Becoming Part of Productivity",
        "description": "As work communication becomes more text-heavy, tone affects speed. Clear intent signals reduce misreads and increase reply rates.",
        "content_html": """
<h1>Why Tone Checks Are Becoming Part of Productivity</h1>
<p>Tone is not just “politeness.” In text-based work, tone impacts speed: misread intent creates extra threads, delays, and friction.</p>

<h2>How tone affects execution</h2>
<ul>
  <li><strong>Less misinterpretation</strong> → fewer clarification cycles</li>
  <li><strong>Clear asks</strong> → faster replies</li>
  <li><strong>Lower defensiveness</strong> → smoother collaboration</li>
</ul>

<h2>The simple standard</h2>
<ul>
  <li>One-line reason</li>
  <li>Explicit action</li>
  <li>Optional timing only when needed</li>
</ul>

<p>If you want to do this consistently, Lexinoa can help you polish tone quickly while preserving your intent.</p>
""".strip(),
    },
    ],
}


def _lang():
    loc = str(get_locale() or "ko")
    return "en" if loc.startswith("en") else "ko"


def _find_post(lang, slug):
    for p in POSTS.get(lang, []):
        if p["slug"] == slug:
            return p
    return None


@blog_bp.route("/blog")
@blog_bp.route("/en/blog")
def blog_index():
    lang = _lang()
    return render_template(
        "blog/index.html",
        posts=POSTS.get(lang, []),
        lang=lang,
    )


@blog_bp.route("/blog/<slug>")
@blog_bp.route("/en/blog/<slug>")
def blog_post(slug):
    lang = _lang()
    post = _find_post(lang, slug)
    if not post:
        abort(404)

    return render_template(
        "blog/post.html",
        post=post,
        lang=lang,
        canonical_url=request.url,
    )
