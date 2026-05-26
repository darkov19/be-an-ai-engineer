## Deferred from: code review of 1-3-candidate-profile-management-and-freshness-monitor.md (2026-05-26)

- **Alt-navigation suppression may be bypassed by capture-phase listeners [ProfileView.tsx:161]**: The global keydown navigation handler might capture hotkeys in the capture phase, bypassing `e.stopPropagation()` in the bubble phase.
