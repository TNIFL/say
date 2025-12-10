from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class UiError:
    code: str
    message: str
    severity: str = "error"      # error | warn | info
    action: Optional[str] = None # 사용자 행동 가이드
    http_status: int = 400
    retryable: bool = False

# 핵심·빈출 코드 우선(운영 중 점진 확장)
TOSS_ERROR_MAP_KO: Dict[str, UiError] = {
    "USER_CANCELED": UiError("USER_CANCELED", "결제가 취소되었어요.", "info", http_status=400),
    "PAY_PROCESS_CANCELED": UiError("PAY_PROCESS_CANCELED", "사용자에 의해 결제가 취소되었어요.", "info"),
    "PAY_PROCESS_ABORTED": UiError("PAY_PROCESS_ABORTED", "결제가 진행되지 않았어요.", "info"),
    "DUPLICATED_ORDER_ID": UiError("DUPLICATED_ORDER_ID", "이미 처리된 주문번호예요. 다른 주문번호로 진행해 주세요.", "warn", "다른 주문번호로 진행해 주세요."),
    "ALREADY_COMPLETED_PAYMENT": UiError("ALREADY_COMPLETED_PAYMENT", "이미 완료된 결제예요.", "info"),
    "ALREADY_CANCELED_PAYMENT": UiError("ALREADY_CANCELED_PAYMENT", "이미 취소된 결제예요.", "info"),
    "ALREADY_PROCESSED_PAYMENT": UiError("ALREADY_PROCESSED_PAYMENT", "이미 처리된 결제예요.", "info"),
    "NOT_SUPPORTED_CARD_TYPE": UiError("NOT_SUPPORTED_CARD_TYPE", "지원되지 않는 카드 종류예요.", "warn", "다른 카드로 시도해 주세요."),
    "INVALID_CARD_NUMBER": UiError("INVALID_CARD_NUMBER", "카드번호를 다시 확인해 주세요.", "warn"),
    "INVALID_CARD_PASSWORD": UiError("INVALID_CARD_PASSWORD", "카드 비밀번호를 다시 확인해 주세요.", "warn"),
    "INVALID_CARD_EXPIRATION": UiError("INVALID_CARD_EXPIRATION", "카드 유효기간을 다시 확인해 주세요.", "warn"),
    "INVALID_REJECT_CARD": UiError("INVALID_REJECT_CARD", "카드사에서 승인이 거절되었어요.", "warn", "카드사 문의 후 다시 시도해 주세요."),
    "REJECT_CARD_COMPANY": UiError("REJECT_CARD_COMPANY", "결제 승인이 거절되었어요.", "warn", "카드사 문의 후 다시 시도해 주세요.", http_status=403),
    "BELOW_MINIMUM_AMOUNT": UiError("BELOW_MINIMUM_AMOUNT", "결제 금액이 최소 금액 미만이에요.", "warn"),
    "BELOW_ZERO_AMOUNT": UiError("BELOW_ZERO_AMOUNT", "금액은 0보다 커야 해요.", "warn"),
    "EXCEED_MAX_PAYMENT_AMOUNT": UiError("EXCEED_MAX_PAYMENT_AMOUNT", "하루 결제 가능 금액을 초과했어요.", "warn"),
    "EXCEED_MAX_DAILY_PAYMENT_COUNT": UiError("EXCEED_MAX_DAILY_PAYMENT_COUNT", "하루 결제 가능 횟수를 초과했어요.", "warn"),
    "EXCEED_MAX_AMOUNT": UiError("EXCEED_MAX_AMOUNT", "거래금액 한도를 초과했어요.", "warn"),
    "NOT_FOUND_PAYMENT": UiError("NOT_FOUND_PAYMENT", "결제 내역을 찾을 수 없어요. 이미 취소되었을 수 있어요.", "warn", http_status=404),
    "NOT_FOUND_PAYMENT_SESSION": UiError("NOT_FOUND_PAYMENT_SESSION", "결제 시간이 만료되어 진행 데이터를 찾을 수 없어요.", "warn", http_status=404),
    "UNAUTHORIZED_KEY": UiError("UNAUTHORIZED_KEY", "키 인증에 실패했어요. 관리자에게 문의해 주세요.", "error", http_status=401),
    "FORBIDDEN_REQUEST": UiError("FORBIDDEN_REQUEST", "허용되지 않은 요청이에요.", "error", http_status=403),
    "FORBIDDEN_CONSECUTIVE_REQUEST": UiError("FORBIDDEN_CONSECUTIVE_REQUEST", "반복 요청이 감지되었어요. 잠시 후 다시 시도해 주세요.", "warn", retryable=True, http_status=403),
    "INVALID_REQUEST": UiError("INVALID_REQUEST", "요청 형식이 올바르지 않아요.", "error", http_status=400),
    "INVALID_URL_FORMAT": UiError("INVALID_URL_FORMAT", "URL 형식이 올바르지 않아요.", "warn"),
    "INCORRECT_SUCCESS_URL_FORMAT": UiError("INCORRECT_SUCCESS_URL_FORMAT", "successUrl 형식이 잘못되었어요.", "warn"),
    "INCORRECT_FAIL_URL_FORMAT": UiError("INCORRECT_FAIL_URL_FORMAT", "failUrl 형식이 잘못되었어요.", "warn"),
    "EXCEEDS_TRANSFER_AMOUNT_MAXIMUM": UiError("EXCEEDS_TRANSFER_AMOUNT_MAXIMUM", "계좌이체는 1,000만 원 이하만 가능합니다.", "warn", "금액을 낮춰 다시 시도해 주세요."),
    "NOT_AVAILABLE_BANK": UiError("NOT_AVAILABLE_BANK", "은행 서비스 시간이 아니에요.", "warn", "은행 서비스 가능 시간에 다시 시도해 주세요.", http_status=403),
    "REJECT_ACCOUNT_PAYMENT": UiError("REJECT_ACCOUNT_PAYMENT", "잔액 부족으로 결제에 실패했어요.", "warn"),
    # 500·장애/기관 오류 → 재시도 권장
    "FAILED_PAYMENT_INTERNAL_SYSTEM_PROCESSING": UiError("FAILED_PAYMENT_INTERNAL_SYSTEM_PROCESSING", "결제 기관 장애로 실패했어요.", "error", "잠시 후 다시 시도해 주세요.", http_status=502, retryable=True),
    "FAILED_INTERNAL_SYSTEM_PROCESSING": UiError("FAILED_INTERNAL_SYSTEM_PROCESSING", "일시적인 오류가 발생했어요.", "error", "잠시 후 다시 시도해 주세요.", http_status=503, retryable=True),
    "FAILED_METHOD_HANDLING": UiError("FAILED_METHOD_HANDLING", "선택한 결제수단 처리 중 오류가 발생했어요.", "error", "잠시 후 다시 시도해 주세요.", http_status=502, retryable=True),
    "FAILED_REFUND_PROCESS": UiError("FAILED_REFUND_PROCESS", "환불 요청 처리 중 일시적 오류가 발생했어요.", "error", "잠시 후 다시 시도해 주세요.", http_status=502, retryable=True),
    "COMMON_ERROR": UiError("COMMON_ERROR", "일시적인 오류가 발생했어요.", "error", "잠시 후 다시 시도해 주세요.", http_status=503, retryable=True),
    "UNKNOWN_ERROR": UiError("UNKNOWN_ERROR", "확인되지 않은 오류가 발생했어요.", "error", "잠시 후 다시 시도해 주세요.", http_status=500, retryable=True),
}


def translate_toss_error(code: str, message: str = None, status: int = None) -> UiError:
    c = (code or "").strip() or "UNKNOWN_ERROR"
    ui = TOSS_ERROR_MAP_KO.get(c)
    if ui:
        return ui
    # 안전 기본값: status 힌트로 보정
    http = status or (401 if c.endswith("_KEY") else 400)
    msg = message or "결제 처리 중 오류가 발생했어요."
    retry = True if http >= 500 else False
    return UiError(code=c, message=msg, severity="error", action="잠시 후 다시 시도해 주세요." if retry else None, http_status=http, retryable=retry)
