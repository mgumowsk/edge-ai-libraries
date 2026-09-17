# C4 Model — ViPPET Benchmark Suite

> Date: 2026-09-16
> Component: `tools/visual-pipeline-and-platform-evaluation-tool` — Benchmark Suite

The Benchmark Suite merges the former in-app benchmark (`BenchmarkManager`, `/benchmarks` API, UI)
and the pytest performance suite (`vippet/tests/performance/`) into one component: a **Benchmark
Engine** in the backend, used by the web UI and by a new **`vippet-bench` CLI**.

---

## Level 1: System Context

```mermaid
graph TB
    Developer["👤 AI Developer<br/>[Person]<br/>Runs benchmarks from<br/>the web UI"]
    Operator["👤 Benchmark Operator / CI<br/>[Person / System]<br/>Runs automated benchmark<br/>campaigns, adds own pipelines,<br/>consumes reports"]

    ViPPET["📦 ViPPET<br/>[Software System]<br/>Plans, executes and reports<br/>pipeline × device × streams<br/>benchmarks"]

    MetricsManager["📦 Metrics Manager<br/>[Software System]<br/>CPU/GPU/NPU/memory/power<br/>telemetry"]
    DLStreamer["📦 DLStreamer / GStreamer<br/>[Software System]<br/>Inference pipeline runtime"]

    Developer -->|"Starts suites & custom runs,<br/>views results (web UI)"| ViPPET
    Operator -->|"vippet-bench CLI:<br/>YAML config, dry-run,<br/>HTML/CSV/JSON reports"| ViPPET
    ViPPET -->|"Collects hardware KPIs<br/>during each test"| MetricsManager
    ViPPET -->|"Executes pipelines"| DLStreamer

    style ViPPET fill:#1168bd,color:#fff
    style MetricsManager fill:#438dd5,color:#fff
    style DLStreamer fill:#999,color:#fff
```

---

## Level 2: Container Diagram

```mermaid
graph TB
    Developer["👤 AI Developer"]
    Operator["👤 Operator / CI"]

    subgraph ViPPET_System["ViPPET [Software System]"]
        UI["🖥️ vippet-ui<br/>[Container: React 19 SPA]<br/>Benchmarks feature: suites,<br/>custom runs, history, exports"]

        CLI["⌨️ vippet-bench<br/>[Container: Python 3.12 CLI]<br/>Pre-flight, YAML config,<br/>dry-run, results directory,<br/>exit codes"]

        API["⚙️ vippet backend<br/>[Container: FastAPI]<br/>Benchmark Engine: planning,<br/>execution, KPI aggregation,<br/>scoring, exports"]

        DB[("🗄️ vippet.db<br/>[Container: SQLite]<br/>Suites, runs,<br/>per-test KPIs")]
    end

    MetricsManager["📦 Metrics Manager"]

    Developer -->|"HTTPS :80"| UI
    Operator -->|"python -m benchmark"| CLI
    UI -->|"REST /api/v1/benchmarks/*"| API
    CLI -->|"REST /api/v1/benchmarks/*,<br/>/status, /devices, /system-info"| API
    API -->|"Reads/writes runs"| DB
    API -->|"Pulls telemetry"| MetricsManager

    style UI fill:#438dd5,color:#fff
    style CLI fill:#438dd5,color:#fff
    style API fill:#438dd5,color:#fff
    style DB fill:#438dd5,color:#fff
    style MetricsManager fill:#1168bd,color:#fff
```

### Container Descriptions

| Container | Technology | Responsibility |
|-----------|-----------|----------------|
| **vippet backend** | Python 3.12, FastAPI, SQLAlchemy | Single execution path for all benchmark runs: builds test matrix, validates hardware/models, runs cases with retries, collects KPIs, persists, exports JSON/CSV/HTML |
| **vippet-bench** | Python 3.12, httpx, PyYAML | Headless client: config → run spec, pre-flight checks, dry-run, polls progress, saves reports to `results/bench_<ts>/`, returns exit code |
| **vippet-ui** | React 19, RTK Query | Existing Benchmarks feature; starts runs and shows history via the same API |
| **vippet.db** | SQLite | Run history shared by UI and CLI |

---

## Level 3: Component Diagram — Benchmark Engine (vippet backend)

```mermaid
graph TB
    UI["vippet-ui"]
    CLI["vippet-bench"]
    MM["Metrics Manager"]
    DB[("vippet.db")]

    subgraph Engine["Benchmark Engine [Container: vippet backend]"]
        Routes["🔀 Benchmarks API<br/>[Component: FastAPI Router]<br/>plan, runs, jobs,<br/>exports, system-info"]

        Planner["🧭 BenchmarkPlanner<br/>[Component]<br/>Run spec → test matrix;<br/>device, model and customer<br/>pipeline validation"]

        Manager["🎛️ BenchmarkManager<br/>[Component: Singleton]<br/>Sequential execution,<br/>retries, timeouts, cancel"]

        Collector["📡 KpiCollector<br/>[Component]<br/>HW KPI sampling per test,<br/>avg / min / max"]

        Exporter["📤 Exporters<br/>[Component]<br/>JSON, CSV, HTML report"]

        TestsMgr["📊 TestsManager<br/>[Component: existing]<br/>Runs one pipeline job"]
    end

    UI --> Routes
    CLI --> Routes
    Routes --> Planner
    Routes --> Manager
    Routes --> Exporter
    Manager -->|"executes plan"| Planner
    Manager -->|"per test case"| TestsMgr
    Manager --> Collector
    Collector --> MM
    Manager -->|"persist results"| DB
    Exporter -->|"read runs"| DB

    style Routes fill:#85bbf0,color:#000
    style Planner fill:#85bbf0,color:#000
    style Manager fill:#85bbf0,color:#000
    style Collector fill:#85bbf0,color:#000
    style Exporter fill:#85bbf0,color:#000
    style TestsMgr fill:#d9d9d9,color:#000
```

### Component Descriptions

| Component | File(s) | Responsibility |
|-----------|---------|----------------|
| **Benchmarks API** | `api/routes/benchmarks.py`, `api/routes/jobs.py`, `api/routes/system.py` | `POST /benchmarks/plan` (dry-run), `POST /benchmarks/runs`, job status, `GET …/export?format=json\|csv\|html`, `GET /system-info` |
| **BenchmarkPlanner** | `managers/benchmark_planner.py` | Builds pipeline × variant × streams matrix from a run spec; skips variants without matching hardware or with missing models; resolves customer pipelines by id/name |
| **BenchmarkManager** | `managers/benchmark_manager.py` | Runs the plan sequentially; retry policy, per-job timeout, cancellation; records attempts and errors |
| **KpiCollector** | `managers/benchmark_metrics.py` | Samples Metrics Manager during each test window; aggregates CPU/GPU/NPU/memory/power KPIs |
| **Exporters** | `managers/benchmark_export.py`, `reporting/html_report.py` | Run → JSON / CSV / HTML (HTML renderer is stdlib-only so the CLI can regenerate reports offline) |
| **TestsManager** | `managers/tests_manager.py` | Existing; executes a single performance job via `PipelineRunner` |

---

## Key Data Flow — Automated run

```mermaid
sequenceDiagram
    participant CLI as vippet-bench
    participant API as Benchmarks API
    participant BM as BenchmarkManager
    participant TM as TestsManager
    participant MM as Metrics Manager

    CLI->>API: GET /health, /status (pre-flight)
    CLI->>API: POST /benchmarks/plan
    API-->>CLI: test matrix + skipped (dry-run stops here)
    CLI->>API: POST /benchmarks/runs
    loop each test case (with retries)
        BM->>TM: run performance job
        BM->>MM: sample KPIs
    end
    CLI->>API: GET /jobs/benchmarks/{id} (poll)
    CLI->>API: GET /benchmarks/runs/{id}/export?format=json|csv|html
    CLI->>CLI: write results/bench_<ts>/, exit 0 / 1 / 2
```
