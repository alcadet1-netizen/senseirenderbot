# Explicit sage reply context

Both `сенсей мудрец` and `мудрец сенсей` use one handler path and AI method, including no trailing question when a readable reply/quote exists. Invocation may appear in text or caption. Case, multiline text, punctuation and existing Sensei spelling aliases are accepted.

## Context and privacy
Only Telegram-provided selected quote, reply text/caption, and up to three already-attached reply objects are included. No API history fetch or audio transcription. Explicit photo requests may download and analyze one selected image as described below. Author names/IDs are not added to the AI prompt. Context is capped at 6000 characters, requester wording at 2000. Context is marked as untrusted data, not instructions. Missing context for a bare/vague request produces local usage help rather than an invented analysis. Actual model adherence requires staging/manual evaluation.

## Delivery and reliability
- One shared path avoids different behavior between aliases. Dispatch tests assert a single model call and response.
- Existing Mongo throttle adds a 5-second per-chat/per-user pause for substantive AI requests. As elsewhere, throttle backend uses the existing nonfinancial fail-open policy.
- Generation has a 45-second timeout, ordinary failures produce a safe message without credentials or raw provider exceptions. Typing-indicator failure does not block an answer.
- Plain text, no content protection or link preview. Output capped at 7000 Python characters, split at word/paragraph boundaries within 3500 UTF-16 units per message.
- Uses explicit ReplyParameters with allow_sending_without_reply=false. Deleted targets, inaccessible chats/topics, permissions, network/flood errors stop delivery quietly; no standalone fallback and no retry of an ambiguous send. After a failed chunk, subsequent chunks are not sent.
- Telegram does not provide universal deletion notifications or arbitrary message-existence queries. A supplied reply snapshot can outlive deletion of the source. This feature cannot promise proactive deletion detection, only bounded context and safe handling of Telegram delivery errors.

Local tests cover matching, quote/caption context, omitted identities, truncation, inaccessible replies, deleted targets, ambiguous network delivery, throttling, emoji length and aiogram dispatch. No live Telegram or provider calls were made for validation.


## Explicit image analysis
- Send a photo with a sage invocation in its caption, or reply to a photo with either alias. JPEG/PNG/WebP documents are accepted too. Unprompted photos in groups are not automatically uploaded.
- If the invocation itself contains an image, it takes priority over the replied image. Only one image is analyzed; this is not whole-album analysis.
- Configure `GROQ_VISION_MODEL` to a currently available Groq image-capable model; `GROQ_API_KEY` is reused. No model ID is guessed and no keys are requested in chat. Empty configuration disables image uploads and returns a clear notice. Verify model availability/permissions with staging, not unit mocks.
- Downloads stay in a bounded in-memory buffer (5 MiB), with timeouts. JPEG/PNG/WebP only, static images up to 20 megapixels; corrupt/bomb/animated images are rejected. Processing applies EXIF orientation, scales to at most 1600x1600, and emits metadata-free JPEG at up to 4 MiB. The model receives a base64 image, never the Telegram file URL or bot token. Readability of very small text may be lost during scaling; the prompt asks the model to acknowledge uncertainty.
- Image data is sent to the configured external Groq provider for this explicit user request. No image content or provider error body is logged or persisted by the new path. Existing message/activity logging may still record captions under existing policy.
- Vision errors are sanitized and do not silently fall back to text-only fake image analysis. Deleted/unavailable files produce a safe retry-with-new-photo message. Output uses the same strict reply delivery handling as text answers.
