import Link from "next/link";

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

type AppMetadata = {
  id: string;
  name: string;
  category: string;
  status: string;
  sensitivity: string;
  route: string;
  health_endpoint: string;
  owner: string;
  data_scope: string;
};

async function getApps(): Promise<AppMetadata[]> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  try {
    const response = await fetch(`${apiUrl}/apps`, { cache: "no-store" });
    if (!response.ok) {
      return [];
    }
    return (await response.json()) as AppMetadata[];
  } catch {
    return [];
  }
}

export default async function Home() {
  const [status, apps] = await Promise.all([getHealth(), getApps()]);
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

        <section className="action-band" aria-label="Capital decision dashboard">
          <div>
            <div className="section-kicker">Capital</div>
            <h2>Decision dashboard</h2>
            <p>Create Capital investment decision records, run the advisory pipeline, and record explicit human review.</p>
          </div>
          <div className="form-actions">
            <Link className="button button-primary" href="/capital/decisions">
              Capital Decisions
            </Link>
            <Link className="button" href="/capital/history">
              Trade History
            </Link>
          </div>
        </section>

        <section className="app-section" aria-label="Registered apps">
          <div>
            <div className="section-kicker">App Registry</div>
            <h2>Registered apps</h2>
          </div>

          <div className="app-grid">
            {apps.map((app) => (
              <article className="app-card" key={app.id}>
                <div className="app-card-header">
                  <div>
                    <strong>{app.name}</strong>
                    <span>{app.category}</span>
                  </div>
                  <span className={`status-pill status-${app.status}`}>
                    {app.status}
                  </span>
                </div>
                <dl>
                  <div>
                    <dt>Sensitivity</dt>
                    <dd>{app.sensitivity}</dd>
                  </div>
                  <div>
                    <dt>Owner</dt>
                    <dd>{app.owner}</dd>
                  </div>
                  <div>
                    <dt>Data scope</dt>
                    <dd>{app.data_scope}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
