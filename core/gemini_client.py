import time
from google import genai
from google.genai import types


class GeminiClient:
    """Shared Gemini text-generation client with safe retry handling."""

    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(
        self,
        prompt=None,
        *,
        contents=None,
        json_mode: bool = False,
        config=None,
        retries: int = 1,
    ) -> str:
        request_contents = contents if contents is not None else prompt

        for attempt in range(retries + 1):
            try:
                request_config = config
                if json_mode and request_config is None:
                    request_config = types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=request_contents,
                    config=request_config,
                )

                if not getattr(response, "text", None):
                    raise RuntimeError("Gemini returned an empty response.")

                return response.text

            except Exception as exc:
                error_message = str(exc)
                is_quota_error = (
                    "429" in error_message
                    or "RESOURCE_EXHAUSTED" in error_message
                )

                if not is_quota_error or attempt >= retries:
                    raise

                # Short exponential backoff for transient rate limiting.
                time.sleep(2 ** attempt)

        raise RuntimeError("Gemini request failed.")
