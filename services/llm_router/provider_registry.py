from services.llm_router.types import ModelRole, Provider, ProviderType


PROVIDERS: dict[str, Provider] = {
    "fable": Provider(
        id="fable",
        provider_type=ProviderType.FABLE,
        label="Fable 5",
        default_model="fable-5",
        roles=(ModelRole.ORCHESTRATOR, ModelRole.REVIEWER),
        api_key_env="FABLE_API_KEY",
        base_url_env="FABLE_BASE_URL",
    ),
    "deepseek": Provider(
        id="deepseek",
        provider_type=ProviderType.DEEPSEEK,
        label="DeepSeek",
        default_model="deepseek-reasoner",
        roles=(ModelRole.DEEP_REASONER, ModelRole.SUMMARIZER),
        api_key_env="DEEPSEEK_API_KEY",
    ),
    "codex": Provider(
        id="codex",
        provider_type=ProviderType.CODEX,
        label="Codex",
        default_model="codex",
        roles=(ModelRole.CODER, ModelRole.REVIEWER),
    ),
    "mini": Provider(
        id="mini",
        provider_type=ProviderType.MINI,
        label="Mini model",
        default_model="mini",
        roles=(ModelRole.FAST_WORKER, ModelRole.SUMMARIZER),
    ),
    "local_ollama": Provider(
        id="local_ollama",
        provider_type=ProviderType.LOCAL_OLLAMA,
        label="Local Ollama",
        default_model="local-deepseek",
        roles=(ModelRole.DEEP_REASONER, ModelRole.SUMMARIZER, ModelRole.FAST_WORKER),
        local_only=True,
        base_url_env="LOCAL_LLM_BASE_URL",
    ),
    "local_vllm": Provider(
        id="local_vllm",
        provider_type=ProviderType.LOCAL_VLLM,
        label="Local vLLM",
        default_model="local-vllm-model",
        roles=(ModelRole.DEEP_REASONER, ModelRole.SUMMARIZER, ModelRole.FAST_WORKER),
        local_only=True,
        base_url_env="VLLM_BASE_URL",
    ),
    "local_sglang": Provider(
        id="local_sglang",
        provider_type=ProviderType.LOCAL_SGLANG,
        label="Local SGLang",
        default_model="local-sglang-model",
        roles=(ModelRole.DEEP_REASONER, ModelRole.SUMMARIZER, ModelRole.FAST_WORKER),
        local_only=True,
        base_url_env="SGLANG_BASE_URL",
    ),
    "third_party_deepseek": Provider(
        id="third_party_deepseek",
        provider_type=ProviderType.THIRD_PARTY_PROXY,
        label="Third-party DeepSeek proxy",
        default_model="deepseek-proxy",
        roles=(ModelRole.SUMMARIZER, ModelRole.FAST_WORKER),
        api_key_env="THIRD_PARTY_DEEPSEEK_API_KEY",
        base_url_env="THIRD_PARTY_DEEPSEEK_BASE_URL",
    ),
    "speculative_serving": Provider(
        id="speculative_serving",
        provider_type=ProviderType.SPECULATIVE_SERVING,
        label="Speculative local serving",
        default_model="local-speculative-model",
        roles=(ModelRole.DEEP_REASONER, ModelRole.SUMMARIZER, ModelRole.FAST_WORKER),
        local_only=True,
        base_url_env="LOCAL_LLM_BASE_URL",
    ),
    "openai": Provider(
        id="openai",
        provider_type=ProviderType.OPENAI,
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
