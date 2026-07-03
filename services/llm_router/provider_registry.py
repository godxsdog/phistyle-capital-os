from services.llm_router.types import ModelRole, Provider


PROVIDERS: dict[str, Provider] = {
    "fable": Provider(
        id="fable",
        label="Fable 5",
        default_model="fable-5",
        roles=(ModelRole.ORCHESTRATOR, ModelRole.REVIEWER),
        api_key_env="FABLE_API_KEY",
    ),
    "deepseek": Provider(
        id="deepseek",
        label="DeepSeek",
        default_model="deepseek-reasoner",
        roles=(ModelRole.DEEP_REASONER, ModelRole.SUMMARIZER),
        api_key_env="DEEPSEEK_API_KEY",
    ),
    "codex": Provider(
        id="codex",
        label="Codex",
        default_model="codex",
        roles=(ModelRole.CODER, ModelRole.REVIEWER),
    ),
    "mini": Provider(
        id="mini",
        label="Mini model",
        default_model="mini",
        roles=(ModelRole.FAST_WORKER, ModelRole.SUMMARIZER),
    ),
    "local": Provider(
        id="local",
        label="Local LLM",
        default_model="local-deepseek",
        roles=(ModelRole.DEEP_REASONER, ModelRole.SUMMARIZER, ModelRole.FAST_WORKER),
        local_only=True,
        base_url_env="LOCAL_LLM_BASE_URL",
    ),
    "openai": Provider(
        id="openai",
        label="OpenAI",
        default_model="future-openai-model",
        roles=(
            ModelRole.ORCHESTRATOR,
            ModelRole.DEEP_REASONER,
            ModelRole.CODER,
            ModelRole.FAST_WORKER,
            ModelRole.SUMMARIZER,
            ModelRole.REVIEWER,
        ),
        api_key_env="OPENAI_API_KEY",
    ),
}


def get_provider(provider_id: str) -> Provider:
    return PROVIDERS[provider_id]


def providers_for_role(role: ModelRole) -> list[Provider]:
    return [provider for provider in PROVIDERS.values() if role in provider.roles]

