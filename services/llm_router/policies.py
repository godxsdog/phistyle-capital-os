from services.llm_router.types import ModelRole, TaskClass


TASK_POLICY: dict[TaskClass, tuple[ModelRole, str, str]] = {
    TaskClass.HIGH_RISK_ARCHITECTURE: (
        ModelRole.ORCHESTRATOR,
        "fable",
        "High-risk architecture should use the strongest orchestrator sparingly.",
    ),
    TaskClass.COMPLEX_REASONING: (
        ModelRole.DEEP_REASONER,
        "deepseek",
        "Complex reasoning should start with a lower-cost deep reasoner or Opus-class model.",
    ),
    TaskClass.CODE_IMPLEMENTATION: (
        ModelRole.CODER,
        "codex",
        "Implementation work should route to Codex.",
    ),
    TaskClass.DOCS_FORMATTING_SUMMARIES: (
        ModelRole.SUMMARIZER,
        "mini",
        "Docs, formatting, and summaries should use a low-cost worker.",
    ),
    TaskClass.LOCAL_PRIVATE_DATA: (
        ModelRole.SUMMARIZER,
        "local_ollama",
        "Private local data must stay on local Ollama or local vLLM routes.",
    ),
    TaskClass.CHEAP_BULK_SUMMARY: (
        ModelRole.SUMMARIZER,
        "local_ollama",
        "Cheap bulk summaries should prefer local Ollama, with third-party proxy only for non-sensitive public text.",
    ),
    TaskClass.SPECULATIVE_SERVING: (
        ModelRole.DEEP_REASONER,
        "speculative_serving",
        "Speculative serving is architecture-only and must be explicitly enabled before execution.",
    ),
}


def policy_for_task(task_class: TaskClass) -> tuple[ModelRole, str, str]:
    return TASK_POLICY[task_class]
