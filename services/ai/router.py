from services.ai.claude_service import call_claude_and_log
from services.ai.openai_service import call_openai_and_log


def _get_ai_outputs(provider, input_text, selected_categories, selected_tones, honorific_checked, opener_checked,
                    emoji_checked, n_outputs, user_job, user_job_detail):
    """Helper function to call the appropriate AI provider and log the request."""
    outputs = []
    if provider == "openai":
        try:
            outputs = call_openai_and_log(
                input_text,
                selected_categories,
                selected_tones,
                honorific_checked,
                opener_checked,
                emoji_checked,
                n_outputs,
            )

        except Exception:
            outputs = []
    elif provider == "claude":
        outputs = call_claude_and_log(
            input_text,
            selected_categories,
            selected_tones,
            honorific_checked,
            opener_checked,
            emoji_checked,
            n_outputs=n_outputs,
            user_job=user_job,
            user_job_detail=user_job_detail,
        )


    else:  # Default to claude
        try:
            outputs = call_claude_and_log(
                input_text,
                selected_categories,
                selected_tones,
                honorific_checked,
                opener_checked,
                emoji_checked,
                n_outputs,
                user_job,
                user_job_detail,
            )

        except Exception:
            outputs = []
    return outputs