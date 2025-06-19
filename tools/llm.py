import os
import json
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set in your environment.")

client = AsyncOpenAI()

SYSTEM_PROMPT = {"role": "system", "content": "You are a helpful assistant."}

async def call_llm(message: str, messages: list = None) -> str:
    """
    Asynchronously call the OpenAI API using the AsyncOpenAI client.
    """
    if messages is None:
        messages = [SYSTEM_PROMPT]
    else:
        # Only prepend system if not present
        if not any(m.get("role") == "system" for m in messages):
            messages.insert(0, SYSTEM_PROMPT)
    messages.append({"role": "user", "content": message})

    response = await client.chat.completions.create(
        model='o3-2025-04-16',
        messages=messages,
    )
    return response.choices[0].message.content.strip()

# Example of usage:
# result = asyncio.run(call_llm("Hello, world!"))
# print(result)
