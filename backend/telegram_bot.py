"""
MedMind — Telegram Bot Integration
Connects the 5-skill agentic pipeline to Telegram.

Important: this module no longer instantiates its own Orchestrator. The
FastAPI app passes the existing one in via run_bot(orchestrator), so we
share a single ChromaDB connection, embedder, and LLM client.
"""

import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import TELEGRAM_TOKEN

# Module-level reference set by run_bot(); handlers read it at request time.
_orchestrator = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    welcome_text = (
        f"Hello {user_name}! I am MedMind, your private AI Health Advisor.\n\n"
        "You can ask me about symptoms, nutrition, or medical conditions. "
        "I provide source-grounded answers based on trusted medical knowledge.\n\n"
        "*How to use:*\n"
        "- Just type your health question.\n"
        "- Send me a photo of food or a nutrition label for analysis.\n"
        "- Use /profile to set up your health profile for personalized answers.\n\n"
        "*Disclaimer:* I am an AI, not a doctor. In an emergency, contact "
        "medical services immediately."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /profile command — set or view health profile via Telegram."""
    if _orchestrator is None:
        await update.message.reply_text("Bot is still starting up, please wait.")
        return

    user_id = str(update.effective_user.id)
    args_text = " ".join(context.args) if context.args else ""

    if not args_text:
        # Show current profile
        profile = _orchestrator.get_profile(user_id)
        if not profile or all(not v or v in (["nothing"], []) for v in profile.values()):
            await update.message.reply_text(
                "You don't have a profile set up yet.\n\n"
                "*Set your profile:*\n"
                "`/profile name:YourName age:25 weight:70 height:175`\n\n"
                "All fields are optional. You can also set them one at a time:\n"
                "`/profile age:21`",
                parse_mode="Markdown",
            )
            return

        parts = ["*Your Health Profile:*\n"]
        if profile.get("name"):
            parts.append(f"Name: {profile['name']}")
        if profile.get("age"):
            parts.append(f"Age: {profile['age']}")
        if profile.get("weight_kg"):
            parts.append(f"Weight: {profile['weight_kg']} kg")
        if profile.get("height_cm"):
            parts.append(f"Height: {profile['height_cm']} cm")
        if profile.get("conditions") and profile["conditions"] != ["nothing"]:
            parts.append(f"Conditions: {', '.join(profile['conditions'])}")
        if profile.get("medications") and profile["medications"] != ["nothing"]:
            parts.append(f"Medications: {', '.join(str(m) for m in profile['medications'])}")
        if profile.get("allergies") and profile["allergies"] != ["nothing"]:
            parts.append(f"Allergies: {', '.join(profile['allergies'])}")

        parts.append(f"\n_Update with_ `/profile key:value`")
        await update.message.reply_text("\n".join(parts), parse_mode="Markdown")
        return

    # Parse key:value pairs
    import re as _re
    profile = _orchestrator.get_profile(user_id) or {}
    pairs = _re.findall(r"(\w+)\s*:\s*([^\s,]+(?:\s+[^\s:,]+)*?)(?=\s+\w+\s*:|$)", args_text)

    if not pairs:
        await update.message.reply_text(
            "Please use the format: `/profile name:YourName age:25 weight:70 height:175`",
            parse_mode="Markdown",
        )
        return

    for key, value in pairs:
        key = key.lower().strip()
        value = value.strip()

        if key == "name":
            profile["name"] = value
        elif key == "age":
            try:
                profile["age"] = int(value)
            except ValueError:
                pass
        elif key == "weight":
            try:
                profile["weight_kg"] = float(value)
            except ValueError:
                pass
        elif key == "height":
            try:
                profile["height_cm"] = float(value)
            except ValueError:
                pass
        elif key == "conditions":
            profile["conditions"] = [c.strip() for c in value.split(",")]
        elif key == "medications":
            profile["medications"] = [m.strip() for m in value.split(",")]
        elif key == "allergies":
            profile["allergies"] = [a.strip() for a in value.split(",")]
        elif key == "goals":
            profile["goals"] = [g.strip() for g in value.split(",")]

    _orchestrator.save_profile(user_id, profile)
    await update.message.reply_text(
        "Profile updated! I'll use this info to give you personalized answers.",
        parse_mode="Markdown",
    )


def _format_sources(sources: list[dict]) -> str:
    """Render the orchestrator's list-of-dicts sources for Telegram."""
    if not sources:
        return ""
    lines = ["", "*Sources:*"]
    for s in sources:
        label = s.get("label", "")
        title = s.get("title") or s.get("source") or "Source"
        url = s.get("url", "")
        if url:
            lines.append(f"- [{label}] {title} — {url}")
        else:
            lines.append(f"- [{label}] {title}")
    return "\n".join(lines)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text or _orchestrator is None:
        return

    user_id = str(update.effective_user.id)
    user_message = update.message.text

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, _orchestrator.process, user_message, user_id
        )

        answer = response["answer"]
        sources_text = _format_sources(response.get("sources", []))
        if sources_text:
            answer = f"{answer}\n{sources_text}"

        if len(answer) > 4096:
            for i in range(0, len(answer), 4096):
                await update.message.reply_text(
                    answer[i:i + 4096], parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(answer, parse_mode="Markdown")

    except Exception as e:
        print(f"[Telegram] Error: {e}")
        await update.message.reply_text(
            "Sorry, I hit an error processing your request. Please try again."
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _orchestrator is None:
        return

    user_id = str(update.effective_user.id)
    caption = update.message.caption or "Analyze this image"

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            _orchestrator.process,
            caption,
            user_id,
            bytes(photo_bytes),
        )

        answer = response["answer"]
        sources_text = _format_sources(response.get("sources", []))
        if sources_text:
            answer = f"{answer}\n{sources_text}"

        await update.message.reply_text(answer, parse_mode="Markdown")

    except Exception as e:
        print(f"[Telegram] Error: {e}")
        await update.message.reply_text(
            "Sorry, I couldn't process your photo. Make sure it's a clear image."
        )


def run_bot(orchestrator):
    """Start the Telegram bot using the provided shared orchestrator."""
    global _orchestrator

    if not TELEGRAM_TOKEN:
        print("[Telegram] No token found in .env. Telegram bot disabled.")
        return

    _orchestrator = orchestrator

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("profile", handle_profile))
    application.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    )
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("[Telegram] Bot is starting...", flush=True)
    application.run_polling()


if __name__ == "__main__":
    # Standalone mode: build our own orchestrator. The FastAPI server
    # path passes its existing one via run_bot(orchestrator) instead.
    from pipeline.orchestrator import Orchestrator
    run_bot(Orchestrator())
