# Story 5.2: Volumetric Brain Visualizer & ECG Telemetry Chart

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a transitioning developer,
I want a central dashboard panel displaying an interactive, rotating 3D SVG brain mesh that highlights skill anomalies in magenta and turns green when they are cleared, accompanied by an SVG-drawn ECG waveform showing active ingestion and learning telemetry,
so that I have a highly engaging visual centerpiece representing my pathway diagnostic status.

## Acceptance Criteria

1. **BrainVisualizer (SVG Skill Node Mesh)**:
   - Render a custom `BrainVisualizer` component inside the central panel of the `/` dashboard.
   - The visualizer must render an SVG mesh of connected skill nodes (e.g., `pgvector`, `RAG`, `Agents`, `Evals`, `Python`, `FastAPI`, `LLMs`, `MLOps`).
   - Node connections are drawn as low-opacity vector lines (`stroke: hsla(180, 10%, 15%, 0.15)` by default).
   - Implement continuous 3D rotation of the SVG skill mesh using CSS 3D transforms (`transform: rotateY(...)` with `transform-style: preserve-3d` and a perspective wrapper).
   - Node status colors must represent profile alignment:
     - **Green (Proven)**: Skill is present in the candidate's profile (`/api/v1/profiles/current`).
     - **Gray (Nominal)**: General market skills that are neither proven nor current gaps.
     - **Pulsing warning magenta (`--glow-magenta`)**: Identified profile anomalies/skill gaps (from `/api/v1/jobs/analytics` `skill_gap` array).
   - Hovering over a node must expand its size/lines and open a diagnostic tooltip containing:
     - The skill name.
     - Cosine similarity fit score or market connection strength indicator.
     - A CTA button/link (e.g., `[RESOLVE ANOMALY]`) to accept its project directive.
   - On viewport widths `< 768px` (mobile), the continuous 3D rotation must deactivate, displaying a static SVG to conserve battery and processing power.
   - Support `prefers-reduced-motion: reduce` query by disabling all continuous rotations and sweeps.

2. **TelemetryChart (ECG wave)**:
   - Render a custom `TelemetryChart` component showing active ingestion volumes and learning telemetry.
   - Draw a smooth, glowing Bezier SVG path (`d` attribute generated from data points) that spikes or flatlines representing commit and parsing telemetry.
   - Render a dotted panning background grid (`opacity: 0.05`) that pans horizontally using infinite CSS animation behind the waveform.
   - Waveform should spike/pulse during active ingestion runs or commit pushes, and flatline when inactive.
   - Commit history can be mocked if backend ledger schemas are in the backlog, while ingestion runs can be queried from `ingestion_runs` or `/api/v1/jobs/analytics`.

3. **Dashboard UI Integration**:
   - Update `DashboardView.tsx` to integrate `BrainVisualizer` and `TelemetryChart`.
   - Organize the layout to fit a three-column grid on desktop:
     - Left column: Telemetry details and system diagnostics.
     - Central column: `BrainVisualizer` and `TelemetryChart` (with bottom logs console).
     - Right column: Active orders/commitments (to be integrated or placeholder).
   - Maintain the sci-fi HUD theme, JetBrains Mono font for numbers/telemetry, and Outfit font for structural UI headers.
   - Ensure AA accessibility compliance (color contrast ratios >= 4.5:1, polite aria-live labels for updating diagnostics).

## Tasks / Subtasks

- [ ] **Task 1: Implement the BrainVisualizer Component (AC: 1)**
  - [ ] Create `frontend/src/components/BrainVisualizer.tsx` and companion module CSS.
  - [ ] Define the SVG node positions (x, y, z coordinates) representing skills (pgvector, RAG, Evals, etc.).
  - [ ] Implement the continuous 3D rotation transform using CSS animation.
  - [ ] Fetch profile and analytics data to dynamically color nodes (green, gray, pulsing magenta).
  - [ ] Add tooltips on hover with node detail metadata and CTA resolver links.
  - [ ] Implement mobile breakpoint check (<768px) and prefers-reduced-motion to disable animations.
- [ ] **Task 2: Implement the TelemetryChart Component (AC: 2)**
  - [ ] Create `frontend/src/components/TelemetryChart.tsx` and companion module CSS.
  - [ ] Draw a custom Bezier SVG path based on telemetry data.
  - [ ] Create the panning background grid using CSS keyframe animations.
  - [ ] Fetch real or mocked database telemetry to feed the graph (spikes on run timestamps, flatlines elsewhere).
- [ ] **Task 3: Update Dashboard Layout & Integrate Widgets (AC: 3)**
  - [ ] Integrate both custom components into `frontend/src/views/DashboardView.tsx`.
  - [ ] Structure the workspace layout using CSS grid columns to host the panels symmetrically.
  - [ ] Ensure that system state flags (nominal, warning, locked) continue to behave correctly (banners are shown, components block correctly if locked).
- [ ] **Task 4: Add Frontend Tests & Verification (AC: 1, 2, 3)**
  - [ ] Add tests in `frontend/src/views/DashboardView.test.tsx` (or a dedicated component test file) asserting correct component rendering and interactive/hover states.
  - [ ] Run `npm run test:frontend` and confirm all tests compile and pass.

## Dev Notes

- **Component Locations**:
  - Components should be located in `frontend/src/components/` with CSS modules beside them.
  - Follow the casing pattern `PascalCase.tsx` and `PascalCase.module.css`.
- **CSS Module & Theme Alignment**:
  - Re-use the existing HUD CSS custom properties in `frontend/src/index.css` (`--glow-cyan`, `--glow-magenta`, `--glow-purple`, `--bg-cosmic`, `--bg-panel`, `--font-mono`, etc.).
  - Hover brackets should contract inward by 2px on focused panels.
- **Data Fetching**:
  - Use TanStack Query or standard fetch hooks to gather profile skills from `GET /api/v1/profiles/current` and skill gaps from `GET /api/v1/jobs/analytics`.

### Project Structure Notes

- Components:
  - `frontend/src/components/BrainVisualizer.tsx`
  - `frontend/src/components/BrainVisualizer.module.css`
  - `frontend/src/components/TelemetryChart.tsx`
  - `frontend/src/components/TelemetryChart.module.css`
- Modified View:
  - `frontend/src/views/DashboardView.tsx`

### References

- [Epics: Story 5.2](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/epics.md#L509-L524)
- [UX Design Specification: BrainVisualizer](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/ux-design-specification.md#L304-L331)
- [UX Design Specification: TelemetryChart](file:///home/darko/Code/be-an-ai-engineer/_bmad-output/planning-artifacts/ux-design-specification.md#L333-L342)
- [CSS HUD Tokens](file:///home/darko/Code/be-an-ai-engineer/frontend/src/index.css#L1-L25)

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (Medium)

### Debug Log References

### Completion Notes List

### File List
