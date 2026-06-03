import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_NEGATIVE = (
    "Eres un experto en gestión de reputación online para negocios de hostelería y retail en España.\n"
    "Tu tarea es redactar respuestas a reseñas negativas en Google Maps, TripAdvisor o Booking.\n"
    "La respuesta debe:\n"
    "- Empezar agradeciendo el feedback (no el tono, el feedback)\n"
    "- Reconocer el problema de forma específica sin admitir negligencia legal\n"
    "- Ofrecer una solución concreta o invitar a contactar directamente\n"
    "- Ser breve: máximo 80 palabras\n"
    "- Tono: {tone} (profesional / cercano / formal)\n"
    "- Nunca usar frases genéricas como 'lamentamos los inconvenientes'\n"
    "Responde SOLO con el texto del borrador, sin comillas ni explicaciones."
)

_SYSTEM_POSITIVE = (
    "Eres un experto en gestión de reputación online para negocios de hostelería y retail en España.\n"
    "Tu tarea es redactar respuestas a reseñas positivas en Google Maps, TripAdvisor o Booking.\n"
    "La respuesta debe:\n"
    "- Agradecer de forma genuina y específica (mencionar algo concreto de lo que dijo)\n"
    "- Ser cálida pero no exagerada ni aduladora\n"
    "- Invitar a volver con naturalidad\n"
    "- Ser breve: máximo 60 palabras\n"
    "- Tono: {tone} (profesional / cercano / formal)\n"
    "- Nunca empezar todas las respuestas igual — variar el inicio\n"
    "Responde SOLO con el texto del borrador, sin comillas ni explicaciones."
)

_USER_PROMPT = (
    "Negocio: {business_name}\n"
    "Plataforma: {platform}\n"
    "Rating: {rating}/5\n"
    "Reseña de {author}: \"{review_text}\""
)


class AnthropicClient:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def generate_negative_draft(self, review, business) -> tuple[str, int]:
        """Generate a reply draft for a negative review.

        Returns (draft_text, total_tokens). On failure returns ("", 0).
        """
        tone = getattr(business, "tone", None) or "cercano"
        return await self._generate(
            system=_SYSTEM_NEGATIVE.format(tone=tone),
            review=review,
            business=business,
            temperature=0.7,
            max_tokens=250,
        )

    async def generate_positive_draft(self, review, business) -> tuple[str, int]:
        """Generate a reply draft for a positive review.

        Returns (draft_text, total_tokens). On failure returns ("", 0).
        """
        tone = getattr(business, "tone", None) or "cercano"
        return await self._generate(
            system=_SYSTEM_POSITIVE.format(tone=tone),
            review=review,
            business=business,
            temperature=0.8,
            max_tokens=200,
        )

    async def generate_draft_on_demand(self, review, business) -> tuple[str, int]:
        """Generate a draft on demand via /responder (higher temperature for variety)."""
        tone = getattr(business, "tone", None) or "cercano"
        review_type = getattr(review, "review_type", "negative")
        system = (
            _SYSTEM_NEGATIVE.format(tone=tone)
            if review_type == "negative"
            else _SYSTEM_POSITIVE.format(tone=tone)
        )
        return await self._generate(
            system=system,
            review=review,
            business=business,
            temperature=0.9,
            max_tokens=250,
        )

    async def _generate(
        self,
        system: str,
        review,
        business,
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, int]:
        text = getattr(review, "text", None) or ""
        author = getattr(review, "author_name", "Cliente")
        rating = getattr(review, "rating", 0)
        platform = getattr(review, "platform", "google")
        business_name = getattr(business, "name", "")

        user_prompt = _USER_PROMPT.format(
            business_name=business_name,
            platform=platform,
            rating=rating,
            author=author,
            review_text=text[:500],
        )

        try:
            message = await self._client.messages.create(
                model=_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
            )
            draft = message.content[0].text.strip()
            tokens = message.usage.input_tokens + message.usage.output_tokens
            return draft, tokens
        except Exception:
            logger.exception(
                "AnthropicClient error generating draft for business=%s", business_name
            )
            return "", 0


_client = AnthropicClient()


def get_anthropic_client() -> AnthropicClient:
    return _client
