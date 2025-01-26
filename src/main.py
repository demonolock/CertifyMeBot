from telethon import TelegramClient, events, Button
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv('.env')

# Bot Configuration
api_id = os.environ.get('api_id')
api_hash = os.environ.get('api_hash')
bot_token = os.environ.get('bot_token')
gpt_token = os.environ.get('gpt_token')
admin_chat_id = os.environ.get('admin_chat_id')

# Initialize the bot
bot = TelegramClient('certification_bot', api_id, api_hash).start(bot_token=bot_token)

# Initialize OpenAI Client
client = OpenAI(
    api_key=gpt_token,
    base_url="https://api.vsegpt.ru/v1",  # Update this to the correct API base URL if necessary
)

# State Management
user_state = {}

# Certification Options
certifications = {
    "dba1": {"name": "PostgreSQL DBA1"},
    "aws": {"name": "AWS Solution Architect Associate"},
    "databricks": {"name": "Databricks Data Engineer Associate"},
}

# Helper Function to Load Prompts
def load_prompt(cert_key):
    """Load the prompt for a given certification key."""
    try:
        prompt_path = f"./prompt/{cert_key}.txt"
        with open(prompt_path, "r") as file:
            return file.read()
    except FileNotFoundError:
        return f"Prompt for {cert_key} not found. Please make sure the file exists."

# Start Command
@bot.on(events.NewMessage(pattern="/start"))
async def start(event):
    user_id = event.sender_id
    user_state[user_id] = {
        "certification": None,
        "questions_answered": 0,
        "correct_answers": 0,
        "daily_questions": 0,
    }
    buttons = [
        [Button.inline(cert["name"], data=key)] for key, cert in certifications.items()
    ]
    await event.respond(
        "Hello! I can help you prepare for certifications.\n\nSelect a certification to get started:",
        buttons=buttons,
    )


# Certification Selection
@bot.on(events.CallbackQuery)
async def select_certification(event):
    try:
        selected_cert = event.data.decode('utf-8')
        user_id = event.sender_id
        if selected_cert in certifications:
            user_state[user_id]["certification"] = selected_cert
            await event.edit(f"You have selected {certifications[selected_cert]['name']}. Let's start practicing!")
            # Immediately ask the first question
            await ask_question(event)
        else:
            await event.edit("Invalid selection. Please try again.")
    except Exception as e:
        await event.respond(f"Error processing your selection: {str(e)}")

# Ask Question
async def ask_question(event):
    user_id = event.sender_id
    if user_id not in user_state or not user_state[user_id].get("certification"):
        await event.respond("Please select a certification first.")
        return

    cert_key = user_state[user_id]["certification"]
    prompt = load_prompt(cert_key)

    try:
        response = client.chat.completions.create(  # Correct API method
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Ask me a question about this certification."},
            ],
        )
        # Access the question from the response object correctly
        question = response.choices[0].message.content
        user_state[user_id]["last_question"] = question
        user_state[user_id]["daily_questions"] += 1
        await event.respond(f"Question: {question}")
    except AttributeError as e:
        await event.respond("Error: Unable to parse the API response. Please check the API client configuration.")
    except Exception as e:
        await event.respond(f"Error generating question: {str(e)}")


# Answer Handler
@bot.on(events.NewMessage)
async def handle_answer(event):
    user_id = event.sender_id
    if user_id not in user_state or not user_state[user_id].get("last_question"):
        return

    user_answer = event.raw_text
    cert_key = user_state[user_id]["certification"]
    prompt = load_prompt(cert_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "assistant", "content": f"Вопрос: {user_state[user_id]['last_question']}"},
                {"role": "user", "content": f"Answer: {user_answer}"},
                {"role": "assistant", "content": "Evaluate this answer and explain why it's correct or incorrect."},
            ],
        )
        evaluation = response.choices[0].message.content
        user_state[user_id]["questions_answered"] += 1
        if "correct" in evaluation.lower():
            user_state[user_id]["correct_answers"] += 1
        await event.respond(f"{evaluation}")
        await ask_question(event)
    except Exception as e:
        await event.respond(f"Error evaluating answer: {str(e)}")

# Start Bot
print("Bot is running...")
bot.run_until_disconnected()
