from src.infrastructure.intelligence.image.image_encoding import encode_as_webp
from src.modules.intelligence.domain.services.image_generation_service import ImageGenerationService


class GeminiImagenProvider(ImageGenerationService):
    def __init__(self, model: str, api_key: str) -> None:
        self._model = model
        self._api_key = api_key

    def generate_image(self, prompt: str) -> bytes:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=self._api_key)

        try:
            # 修正：不用移除 "-image"！直接使用完整的 gemini-3.1-flash-image
            # 因為它本身就是改走 :generateContent 管道
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(
                        disable=True,
                    ),
                ),
            )

            # 從多模態 Parts 中提取原始的圖片 bytes，統一縮放並轉成 WebP 再回傳
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        return encode_as_webp(part.inline_data.data)

            raise RuntimeError("Gemini API 成功回應，但未包含任何圖片數據。")

        except Exception as e:
            raise e
