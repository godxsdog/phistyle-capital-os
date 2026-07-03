async function getHealth(): Promise<string> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  try {
    const response = await fetch(`${apiUrl}/health`, { cache: "no-store" });
    if (!response.ok) {
      return `unavailable (${response.status})`;
    }
    const payload = (await response.json()) as { status?: string };
    return payload.status || "unknown";
  } catch {
    return "unavailable";
  }
}

export default async function Home() {
  const status = await getHealth();
  const isOk = status === "ok";

  return (
    <main>
      <div className="shell">
        <section className="hero">
          <div className="eyebrow">Phase 1 Platform Scaffold</div>
          <h1>PhiStyle OS</h1>
          <p>
            Minimum runnable foundation for the OS shell. Domain apps, AI,
            investment workflows, and legacy integrations are intentionally not
            implemented yet.
          </p>
        </section>

        <section className="status-panel" aria-label="Backend health">
          <div className="status-label">Backend health</div>
          <div className={`status-value ${isOk ? "status-ok" : ""}`}>
            {status}
          </div>
        </section>
      </div>
    </main>
  );
}

