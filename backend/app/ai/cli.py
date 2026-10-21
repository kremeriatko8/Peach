"""Explicit paid commands. Never called by tests or deployment validation."""

import argparse
import json
import os
from dataclasses import asdict
from datetime import date

from app.ai.agenda import PROMPT_VERSION, make_client, parse_agenda
from app.ai.costs import estimate_cost
from app.config import get_settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["hello", "parse"])
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    parser.add_argument("--tz", default="Europe/Kyiv")
    args = parser.parse_args()
    if os.environ.get("PEACH_APPROVE_PAID_INFERENCE") != "yes":
        parser.error("Paid inference requires explicit approval: PEACH_APPROVE_PAID_INFERENCE=yes")
    settings = get_settings()
    if args.command == "hello":
        result = make_client().converse(
            modelId=settings.parser_model,
            inferenceConfig={"maxTokens": 128, "temperature": 0},
            messages=[{"role": "user", "content": [{"text": "Say hello in one sentence."}]}],
        )
        print(
            json.dumps(
                {
                    "answer": "".join(
                        b.get("text", "") for b in result["output"]["message"]["content"]
                    ),
                    "stop_reason": result["stopReason"],
                    "input_tokens": result["usage"]["inputTokens"],
                    "output_tokens": result["usage"]["outputTokens"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        result, usage = parse_agenda(os.environ.get("TEXT", ""), args.today, args.tz)
        print(
            json.dumps(
                {
                    "agenda": result.model_dump(mode="json"),
                    "usage": asdict(usage),
                    "model": settings.parser_model,
                    "prompt_version": PROMPT_VERSION,
                    "estimated_cost_usd": estimate_cost(**asdict(usage)),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
