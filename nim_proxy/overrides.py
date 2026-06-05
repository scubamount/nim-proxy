"""Per-model override dict.

Schema: { "<provider>/<model>": { "temperature", "top_p", "max_tokens", "extra_body" } }

`extra_body` is merged into the top level of the forwarded request body. This is
required for fields that the OpenAI-compatible client SDK doesn't expose through
its config (e.g. `chat_template_kwargs`, `reasoning_budget` for Nemotron).
"""

MODEL_OVERRIDES: dict = {
    "nvidia/nemotron-3-ultra-550b-a55b": {
        "upstream": "nvidia/nemotron-3-ultra-550b-a55b",
        "temperature": 1,
        "top_p": 0.95,
        "max_tokens": 16384,
        "extra_body": {
            "chat_template_kwargs": {"enable_thinking": False},
        },
    },
    "stepfun-ai/step-3.7-flash": {
        "temperature": 1.0,
        "top_p": 0.95,
        "max_tokens": 16384,
    },
    "deepseek-ai/deepseek-v4-pro": {
        "temperature": 1,
        "top_p": 0.95,
        "max_tokens": 16384,
        "extra_body": {
            "chat_template_kwargs": {"thinking": False},
        },
    },
    "deepseek-ai/deepseek-v4-flash": {
        "temperature": 1,
        "top_p": 0.95,
        "max_tokens": 16384,
        "extra_body": {
            "chat_template_kwargs": {"enable_thinking": True},
        },
    },
    "minimaxai/minimax-m2.7": {
        "upstream": "minimaxai/minimax-m2.7",
        "temperature": 1,
        "top_p": 0.95,
        "max_tokens": 8192,
    },
    "nvidia/minimaxai/minimax-m2.7": {
        "upstream": "minimaxai/minimax-m2.7",
        "temperature": 1,
        "top_p": 0.95,
        "max_tokens": 8192,
    },
    "moonshotai/kimi-k2.6": {
        "upstream": "moonshotai/kimi-k2.6",
        "temperature": 1.0,
        "top_p": 1.0,
        "max_tokens": 16384,
    },
    "nvidia/moonshotai/kimi-k2.6": {
        "upstream": "moonshotai/kimi-k2.6",
        "temperature": 1.0,
        "top_p": 1.0,
        "max_tokens": 16384,
    },
}
