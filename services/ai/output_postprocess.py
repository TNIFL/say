def _ensure_exact_count(outputs, count):
    """
    결과 개수 정확히 맞추기:
      - 공백/빈값 제거
      - (count>1) 중복 제거
      - 모자라면 마지막 문장 복제
      - 많으면 앞에서 count개만
    """
    out = [(o or "").strip() for o in (outputs or []) if (o or "").strip()]
    if count > 1:
        seen, uniq = set(), []
        for o in out:
            k = " ".join(o.lower().split())
            if k in seen:
                continue
            seen.add(k)
            uniq.append(o)
        out = uniq
    if len(out) < count:
        while len(out) < count:
            out.append(out[-1] if out else "(빈 결과)")
    else:
        out = out[:count]
    return out