# End-to-End UI Test Coverage Plan

This plan enumerates the behavior-driven scenarios we intend to automate with
`pytest-bdd` to exercise the arranger application from the main window down to
its injected services. Each work item references the harness capabilities under
`tests/e2e/harness.py` and captures any additional fakes or hooks required to
keep the scenarios deterministic and headless-friendly.

## 1. Harness Readiness

| Task | Description | Dependencies |
| --- | --- | --- |
| Preferences + updates doubles | Extend `E2EHarness` so the preferences, update
service, and project service interactions can be stubbed without hitting the
filesystem or spawning background threads. | New fakes mirroring
`FakeScoreService`; hooks in `create_e2e_harness` |
| Dialog + messagebox hooks | Support sequencing open/save dialogs, messagebox
responses, and PDF option prompts from Given steps. | Existing
`FakeFileDialogAdapter` and `MessageboxRecorder`; extend with queue control |
| Web + clipboard interceptors | Capture calls to `webbrowser.open` and Tk
clipboard access to assert side effects without leaving the test environment. |
Monkeypatches in the harness |

## 2. File Selection & Preview Rendering

| Scenario | Behaviour | Required Support |
| --- | --- | --- |
| Successful preview render | Already covered in
`tests/e2e/features/main_app.feature`. Ensure harness queues two preview
responses (auto render + manual command). | `FakeScoreService` preview queue |
| Cancelled file open | Simulate a `None` path from the open dialog and assert
status + dialogs remain unchanged. | Dialog queue helper |
| Preview failure | Queue an error result to verify error message handling and
status update pathways. | Error branch in `FakeScoreService` |
| Auto-render guard | Ensure repeated `render_previews` calls without new input
are no-ops and show the cached status message. | Harness state inspection |

## 3. Conversion & Export

| Scenario | Behaviour | Required Support |
| --- | --- | --- |
| Successful conversion | Already scripted; assert conversion plan contents and
status message. | Provided |
| Cancelled save dialog | Queue `None` save path and ensure command aborts
without invoking the service. | Dialog queue |
| Conversion failure | Force `FakeScoreService` to raise and confirm the error
messagebox interaction. | Error injection hook |
| PDF export options | Capture options chosen through the stubbed PDF dialog and
assert they are passed to the conversion plan. | Shared `pdf_options` object |

## 4. Project Persistence

| Scenario | Behaviour | Required Support |
| --- | --- | --- |
| Save current project | Use a fake project service to persist preview data and
confirm recent-projects list updates. | New `FakeProjectService` |
| Load existing project | Assert preview variables repopulate and automatic
render triggers once. | Harness inspection of score service queues |
| Load failure | Simulate `Result.error` to verify messageboxes and status text. |
Fake project service |
| Recent projects menu | Validate that loading populates the submenu in sorted
order using the preferences stub. | Preferences hooks |

## 5. Preview Playback Controls

| Scenario | Behaviour | Required Support |
| --- | --- | --- |
| Toggle play original/arranged | Ensure the harness captures attempted audio
playback without launching threads. | `NullAudioRenderer` already injected |
| Adjust tempo and loop range | Assert view-model state updates and persistence
through preference stub. | Harness exposes view-model |
| Auto-scroll mode cycle | Confirm preference stub receives updated value and
UI state toggles correctly. | Preferences hooks |

## 6. Transform Settings & Reimport

| Scenario | Behaviour | Required Support |
| --- | --- | --- |
| Apply transpose offset | Confirm reimport occurs and arranged preview data is
refreshed. | Score service queue for new preview |
| Cancel transpose | Ensure state reverts without extra service calls. | Harness
insight into queue lengths |
| Instrument change | Validate range defaults and fingering selector update in
response to instrument selection. | Fingering + instrument stubs |

## 7. Fingering Editor Workflow

| Scenario | Behaviour | Required Support |
| --- | --- | --- |
| Enter edit mode | Confirm UI state flips and undo/redo disabled. | Fake
fingering editor service |
| Apply changes | Assert new layout is sent to the service and preview refreshes. |
Service stub verifying calls |
| Cancel edit | Ensure no service calls occur and state resets. | Harness state |
| Half-hole toggle | Verify mixin state updates without widget interaction. |
View-model inspection |

## 8. Support & Updates

| Scenario | Behaviour | Required Support |
| --- | --- | --- |
| Check for updates success | Stub update service to return an available version
and ensure status + messageboxes match expectations. | Fake update service |
| Check for updates failure | Simulate network error and assert graceful
handling. | Error injection |
| Toggle auto update channel | Confirm preference stub is updated and persisted. |
Preferences hooks |
| Open support links | Capture `webbrowser.open` arguments for documentation,
feedback, and release notes entries. | Web stub |

## 9. Window Lifecycle

| Scenario | Behaviour | Required Support |
| --- | --- | --- |
| Teardown after activity | Drive playback, edit mode, and project loading before
destroying the window, ensuring background tasks are cancelled without Tk
errors. | Existing harness teardown helpers |

## Implementation Milestones

1. **Harness expansion** – implement missing fakes, stub points, and helper
methods so Given steps can express environment setup declaratively.
2. **Feature files** – organise `.feature` documents by theme (`main_app`,
`projects`, `preview_playback`, `fingering`, `updates_support`). Each scenario
should state intent clearly and map to reusable step definitions.
3. **Step libraries** – group step definitions by domain (e.g., file operations,
preview playback, fingering editor) to keep modules cohesive and avoid one giant
steps file.
4. **CI execution** – ensure `pytest -m gui` or equivalent runs these scenarios in
CI, and mark longer-running flows appropriately so they remain opt-in locally.
5. **Ongoing maintenance** – when features evolve, update both the harness
fakes and the relevant scenarios so behaviour remains documented and tested.

This plan keeps the e2e layer focused on observable behaviour while leveraging
headless-friendly doubles to stay deterministic and fast.
