import os
import json
import re
from datetime import datetime

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dateutil import parser

AIPIPE_TOKEN = os.getenv("eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIzZjEwMDAyMTJAZHMuc3R1ZHkuaWl0bS5hYy5pbiIsImlhdCI6MTc4MzU4MDUxNiwiaXNzIjoiaHR0cHM6Ly9haXBpcGUub3JnIiwiYXVkIjoiYWlwaXBlLWFwaSIsImV4cCI6MTc4NDE4NTMxNn0.X_0h1vXbeHFZtXU5IPaT-0IURGSMLA0EogqYAgLoBGs")

API_URL = "https://aipipe.org/openai/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {AIPIPE_TOKEN}",
    "Content-Type": "application/json",
}

MODEL = "gpt-4o-mini"

app = FastAPI(title="Dynamic Schema Extraction")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DynamicRequest(BaseModel):
    text: str
    schema: dict


def parse_json(content):
    content = content.strip()

    if content.startswith("```"):
        content = re.sub(r"^```json", "", content)
        content = content.replace("```", "").strip()

    try:
        return json.loads(content)
    except Exception:
        m = re.search(r"\{.*\}", content, re.S)
        if m:
            return json.loads(m.group())
        return {}


def convert(value, typ):

    if value is None:
        return None

    try:

        if typ == "string":
            return str(value)

        if typ == "integer":
            return int(value)

        if typ == "float":
            return float(value)

        if typ == "boolean":

            if isinstance(value, bool):
                return value

            return str(value).lower() in ["true", "yes", "1"]

        if typ == "date":
            d = parser.parse(str(value), fuzzy=True)
            return d.strftime("%Y-%m-%d")

        if typ == "array[string]":

            if isinstance(value, list):
                return [str(x) for x in value]

            return [str(value)]

        if typ == "array[integer]":

            if isinstance(value, list):
                return [int(x) for x in value]

            return [int(value)]

    except Exception:
        return None

    return None


@app.get("/")
def home():
    return {"status": "running"}


@app.post("/dynamic-extract")
async def dynamic_extract(req: DynamicRequest):

    prompt = f"""
Extract information from the text.

Return ONLY valid JSON.

Rules:

- Return EXACTLY the keys in the schema.
- Do NOT invent fields.
- Missing fields must be null.
- Dates must be YYYY-MM-DD.
- Floats must be JSON numbers.
- Integers must be JSON integers.
- Arrays must be JSON arrays.

Schema:

{json.dumps(req.schema, indent=2)}

Text:

{req.text}
"""

    payload = {
        "model": MODEL,
        "temperature": 0,
        "response_format": {
            "type": "json_object"
        },
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    async with httpx.AsyncClient(timeout=120) as client:

        r = await client.post(
            API_URL,
            headers=HEADERS,
            json=payload
        )

        r.raise_for_status()

        content = r.json()["choices"][0]["message"]["content"]

    raw = parse_json(content)

    result = {}

    for key, typ in req.schema.items():
        result[key] = convert(raw.get(key), typ)

    return result
