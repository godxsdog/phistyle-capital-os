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
        "local",
        "Private local data must stay on a local model route.",
    ),
}


def policy_for_task(task_class: TaskClass) -> tuple[ModelRole, str, str]:
    return TASK_POLICY[task_class]

