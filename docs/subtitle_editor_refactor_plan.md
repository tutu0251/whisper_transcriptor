# Subtitle Studio Refactor Spec

## Implementation Markers

Use these markers to track implementation progress:

- `[IDEA]` planned but not started
- `[MOCKUP]` implemented only in the mock/prototype app
- `[PARTIAL]` partially implemented in the real app
- `[DONE]` implemented in the real app
- `[BLOCKED]` known requirement, currently blocked

This file should be updated whenever feature status changes.

## Product Summary

This app should become:

`Subtitle Editor with built-in transcription and fine-tuning`

not:

`Transcriber with a separate subtitle editor tab`

The subtitle editor is the primary product. Transcription and fine-tuning are supporting workflows around subtitle editing.

## Core Product Goal `[PARTIAL]`

Refactor the app so the main experience is centered on:

1. `Subtitle Editor`
2. `Transcriptor`
3. `Fine Tuner`

The user should be able to:

- load media
- load or generate subtitles
- edit subtitle segments directly
- retrigger transcription for selected ranges
- collect corrections for training
- run fine-tuning workflows from edited subtitle data
- run batch training from folders that contain paired media + subtitle files

## Supported Subtitle Formats `[IDEA]`

The product direction is to support **all subtitle formats** through a unified adapter-based architecture.

Immediate priority formats:

- `SRT`
- `SMI`

Expected broader format support:

- `VTT`
- `ASS`
- `SSA`
- `SUB`
- `SBV`
- `LRC`
- and other subtitle/text-timed caption formats as practical

Format support should not create different editing experiences. Users should get the same editor workflow regardless of file format.

Implementation note:

- the architecture should assume broad subtitle-format support from the beginning
- the first real adapters can still be implemented in priority order, starting with `SRT` and `SMI`

## UX Rules `[PARTIAL]`

### Subtitle-Editor Comfort Rule

Subtitle editor users should feel immediately comfortable using this program.

The app should match subtitle-editor expectations in:

- timeline-first editing
- segment list editing
- direct timestamp editing
- keyboard-centered workflows
- playback-synced navigation
- familiar import/export behavior
- subtitle format awareness

The design goal is not only feature parity. It is **comfort parity**.

### Chunking Rule

This is a critical behavior requirement:

- initial auto-transcription may use fixed chunk sizes
- once the user edits subtitle timing, re-transcription must become **segment-aware**
- re-transcription should use the edited subtitle start/end range
- chunk duration for edited subtitles must be variable and follow the subtitle duration

In short:

- first-pass transcription: fixed-window chunking is acceptable
- edited subtitle re-transcription: fixed-window chunking is not acceptable

### Editor-First Rule

Transcription should not feel like a separate mode that owns the UI.

Instead:

- the subtitle editor owns the document
- transcription writes into the subtitle document
- fine-tuning reads corrections from the subtitle document

## Variable Chunking Feature `[IDEA]`

This is a first-class product feature and should be easy to find in this spec.

### Purpose

The app must support variable transcription ranges after subtitle timing is edited.

### Required Behavior

- when the user runs initial auto-transcription for a full file, fixed chunk sizes may be used
- when the user edits subtitle timing, the subtitle's own start/end time becomes the default transcription range for re-transcription
- re-transcription of an edited subtitle must use the subtitle segment's actual duration
- the app must not force edited subtitles back through a fixed global chunk size

### Practical Meaning

Example:

- first-pass auto-transcription may use 3-second or 5-second chunks
- user later edits one subtitle to `00:14.496 -> 00:17.495`
- `re-transcribe current subtitle` must transcribe exactly that edited range

### Architectural Meaning

The transcription system must support both:

- `Fixed-window chunking`
  - for first-pass file transcription

- `Variable segment-duration chunking`
  - for edited subtitle re-transcription
  - for selected waveform range transcription

### UI Meaning

The UI should make this visible through:

- selected subtitle range display
- waveform selection range
- actions such as:
  - `Transcribe Selection`
  - `Re-transcribe Current Subtitle`
  - `Use edited subtitle duration`

## Main Workspace Shape `[MOCKUP]`

The main window should feel like a serious subtitle editor first.

### Primary Areas

- `Media Pane`
  - video/audio player
  - waveform / timeline
  - current playback position
  - editable range selection

- `Subtitle Editor Pane`
  - subtitle segment list
  - inline subtitle editing
  - timing editing
  - search / replace
  - split / merge / insert / delete
  - playback-follow highlighting
  - format-aware editing across subtitle formats

- `Inspector / Tool Pane`
  - transcription actions
  - model selection
  - device selection (`Auto / CPU / CUDA`)
  - compute mode selection
  - fine-tuning status
  - correction statistics

### Supporting Workflows

- `Transcription Tools`
  - transcribe whole file
  - transcribe selected waveform range
  - re-transcribe current subtitle
  - compare AI result vs current subtitle

- `Training Tools`
  - pending corrections
  - dataset preview
  - train now / background train
  - training history
  - batch training from paired media + subtitle folders
  - separate batch training window
  - batch training mode selection (`foreground` / `background`)

## Architecture `[IDEA]`

Use a document-centered architecture.

### Core Domain Objects

- `SubtitleDocument`
  - source of truth for loaded/generated subtitles
  - owns subtitle segments, subtitle format, and document metadata

- `SubtitleSegment`
  - start time
  - end time
  - text
  - confidence
  - language
  - source (`loaded`, `live`, `retranscribed`, `edited`)
  - optional review/training state

- `SubtitleFormat`
  - normalized internal subtitle format abstraction
  - supports many external file formats through adapters

- `MediaSession`
  - current media file
  - waveform/audio cache
  - playback state
  - selected transcription range

- `TrainingSessionState`
  - pending corrections
  - training history
  - active model info

### Services

- `SubtitleDocumentService`
  - import/export subtitle formats
  - normalize segments
  - split/merge/update timing
  - format conversions between document model and file format

- `SubtitleFormatAdapter`
  - `SRTAdapter`
  - `SMIAdapter`
  - additional adapters for other subtitle formats
  - parses file text into `SubtitleDocument`
  - serializes `SubtitleDocument` back into each format

- `TranscriptionService`
  - wraps `Transcriber`
  - transcribe file / selection / segment
  - returns subtitle segments, not raw text blobs
  - supports:
    - fixed-window chunking for first-pass auto-transcription
    - variable segment-duration chunking for edited subtitle re-transcription

- `TrainingService`
  - wraps correction collection + background trainer
  - reads edited subtitle changes as training examples
  - supports batch dataset building from paired media + subtitle folders
  - supports training/fine-tuning a user-selected model from those datasets

- `MediaService`
  - wraps player, extracted audio, seeking, waveform sync

### UI Layer

- `MainWindow`
  - shell only
  - menus, docking, command wiring

- `SubtitleEditorWidget`
  - primary subtitle editing interface
  - table/list of subtitle segments
  - keyboard-friendly editing behavior
  - subtitle-editor-compatible workflow

- `MediaWorkspaceWidget`
  - player + waveform + selection tools

- `TranscriptionToolPanel`
  - model, language, device, compute mode, re-transcribe actions

- `TrainingToolPanel`
  - correction stats, dataset preview, training controls

- `BatchTrainingWindow`
  - separate workflow window for folder-based training
  - scan paired media/subtitle files
  - preview valid/invalid pairs
  - choose model to train
  - choose training execution mode (`foreground` / `background`)
  - launch and monitor batch training

## Data Flow `[IDEA]`

### Load Existing Subtitle File

1. media file opens
2. subtitle file loads into `SubtitleDocument` through a format adapter
3. editor renders the document
4. playback highlights the active subtitle

### Generate New Subtitles

1. user runs transcription
2. `TranscriptionService` produces subtitle segments
3. segments are stored in `SubtitleDocument`
4. editor renders the same document

### Re-Transcribe Edited Subtitle

1. user adjusts subtitle timing or text
2. segment in `SubtitleDocument` is updated
3. user triggers `re-transcribe current subtitle` or `re-transcribe selection`
4. `TranscriptionService` uses the edited start/end time as the transcription range
5. returned text replaces or compares against the current subtitle text

Important:

- this is not the same as first-pass transcription
- this must respect the edited subtitle duration

### Edit + Train

1. user edits subtitle text or timing
2. document updates
3. change is recorded as a correction/training example
4. `TrainingService` prepares or runs fine-tuning

### Batch Train From Folder

1. user selects a folder
2. app scans for paired media + subtitle files
3. valid pairs are converted into a training dataset
4. user selects a target/base model
5. user selects batch training mode (`foreground` or `background`)
6. `TrainingService` runs training or fine-tuning using the discovered pairs

Supported pairing concept:

- media file plus subtitle file with matching base name
- example:
  - `lesson01.mp3` + `lesson01.srt`
  - `lesson02.mp4` + `lesson02.smi`

The workflow should support mixed media types and mixed subtitle formats as long as they can be normalized into the internal subtitle document model.

Batch training modes:

- `Foreground`
  - user stays focused on the batch training workflow
  - progress is shown prominently
  - better for immediate monitoring and review

- `Background`
  - training runs while the user continues subtitle editing or other work
  - progress should still be visible through status and notifications

### Separate Batch Training Window

Batch training should have its own dedicated window instead of being squeezed into the main editor workspace.

Reason:

- folder scanning is a larger workflow
- dataset validation needs more room
- users need a clear training-oriented space
- long-running training tasks should feel separate from subtitle editing

The main editor can launch this window, but the batch training workflow itself should live in its own UI.

## Why This Refactor Is Needed `[DONE]`

Current structure mixes too many responsibilities into `MainWindow` and the transcription panel:

- media playback
- subtitle rendering/editing
- transcription orchestration
- training orchestration
- file-format-specific subtitle handling

That makes the UX fragmented and makes feature growth harder.

The editor-centered approach fixes this by making the subtitle document the shared artifact between:

- subtitle editing
- AI transcription
- fine-tuning

## Roadmap `[PARTIAL]`

### Stage 1: Unify Subtitle Data Model `[IDEA]`

Goal:

- make live transcription and loaded subtitles use one internal document model

Tasks:

- introduce `SubtitleDocument`
- add subtitle format field and metadata
- convert current editors/panels to consume the same segment list
- stop maintaining separate display-only paths for `segments` and `srt_entries`

### Stage 2: Add Multi-Format Subtitle I/O `[IDEA]`

Goal:

- support multiple subtitle formats through a common adapter system

Tasks:

- create `SubtitleFormatAdapter` interface
- move current SRT parsing/export behind `SRTAdapter`
- add `SMIAdapter`
- add more subtitle format adapters incrementally
- normalize both formats into the same internal document model
- preserve format-specific export behavior

### Stage 3: Promote Editor to Primary Workspace `[MOCKUP]`

Goal:

- replace the split between transcription panel and basic SRT editor

Tasks:

- create a richer `SubtitleEditorWidget`
- move editing, search, timing offset, and export into that widget
- keep transcription as actions that modify the editor document
- align behavior, labels, and keyboard flow with familiar subtitle editor UX

### Stage 4: Move Logic Out of MainWindow `[IDEA]`

Goal:

- make `MainWindow` a coordinator rather than a feature container

Tasks:

- extract `TranscriptionService`
- extract `TrainingService`
- extract `MediaWorkspaceController`
- introduce chunking policy logic into `TranscriptionService`

### Stage 5: Segment-Level Editor Tools `[PARTIAL]`

Goal:

- make the app feel like a serious subtitle editor

Tasks:

- split segment
- merge segments
- insert segment at cursor
- ripple timing tools
- next/previous subtitle navigation
- frame- or small-step timing nudges
- keyboard-centered subtitle editing
- use current subtitle timing as the default transcription range for re-transcribe actions

### Stage 6: Fine-Tuning Workspace `[PARTIAL]`

Goal:

- make training a first-class workflow based on edited subtitles

Tasks:

- add training dataset preview
- add correction review queue
- add per-model training history
- add export/import for training examples
- add folder-based batch training flow
- add paired media/subtitle validation
- add model selection for batch fine-tuning
- add dedicated `BatchTrainingWindow`
- add foreground/background mode selection for batch training

## Recommended Implementation Order `[DONE]`

### Best First Slice

1. create `SubtitleDocument`
2. make loaded `SRT` and live transcription both populate it
3. make the UI render from that document only

This gives the biggest architectural win with the least disruption.

### Next Slice

1. introduce format adapters
2. add `SMI` import/export
3. keep the same editor experience regardless of subtitle format
4. expand adapter coverage to additional formats in priority order

### Early Transcription Slice

1. keep fixed chunking for initial auto-transcription
2. add variable-duration subtitle-range transcription for edited segments
3. make `re-transcribe current subtitle` use the segment's actual edited time range

### Early Batch Training Slice

1. allow user to select a folder containing paired media + subtitle files
2. scan and validate pairs by basename
3. normalize subtitle files (`SRT` / `SMI`) into the internal document model
4. build a training dataset from those pairs
5. let user select which model to train/fine-tune
6. let user choose whether batch training runs in foreground or background

## Current Mockup Status `[MOCKUP]`

There is a prototype mockup app for UX testing:

- [mock_subtitle_studio.py](d:/work/whisper_transcriptor/mock_subtitle_studio.py)

### Mockup Includes `[MOCKUP]`

- editor-first layout
- media pane
- waveform / timeline mock
- interactive waveform range selection
- subtitle segment table
- `SRT` and `SMI` awareness
- broader subtitle-format support wording
- `Transcriptor` tool tab
- `Fine Tuner` tool tab
- mock `Settings` dialog
- device selector (`Auto / CPU / CUDA`)
- compute selector (`float32 / float16 / int8`)
- separate batch training window

### Mockup Purpose

The mockup is for:

- testing layout
- testing terminology
- testing comfort for subtitle-editor users
- testing feature grouping before wiring the real backend

It is not a production implementation.

## Open Implementation Priorities `[PARTIAL]`

Highest-priority real implementation areas:

1. shared subtitle document model
2. multi-format subtitle adapters (`SRT`, `SMI`, then broader format coverage)
3. editor-first real UI shell
4. segment-aware re-transcription flow
5. fine-tuning pipeline integration through edited subtitle corrections
6. batch training from paired media + subtitle folders

## Batch Training Feature `[MOCKUP]`

## Current Progress Snapshot

### Real App

- `[DONE]` Existing desktop app with media player, transcription flow, subtitle editing pieces, and training-related components
- `[DONE]` Unit test runner scripts added
- `[DONE]` Offline package installer scripts added
- `[DONE]` `ModelManager` cache-dir fix to avoid tests overwriting repo-local HF model folders
- `[PARTIAL]` Transcription panel display was aligned more closely between loaded SRT and live transcription
- `[PARTIAL]` Subtitle editing exists, but the app is not yet unified around a single subtitle document model
- `[IDEA]` Variable chunking based on edited subtitle duration
- `[IDEA]` Multi-format subtitle adapter system
- `[IDEA]` Separate real batch training window

### Mockup

- `[DONE]` Mock editor-first app shell created
- `[DONE]` Mock settings dialog added
- `[DONE]` Mock waveform range selection added
- `[DONE]` Mock CPU/CUDA and compute selectors added
- `[DONE]` Mock separate batch training window added
- `[DONE]` Mock batch training workflow wording added
- `[DONE]` Mock wording updated for broad subtitle-format support

This is a first-class feature and should remain visible in this spec.

### Purpose

The app must support training or fine-tuning a specific model from a folder that contains paired media and subtitle files.

### Required Behavior

- user selects a folder
- app discovers valid media/subtitle pairs
- app validates pairs before training
- subtitles may be `SRT` or `SMI`
- subtitles are normalized into the internal document model
- user selects a target/base model for training
- user selects a training mode: `foreground` or `background`
- app builds a dataset and runs training/fine-tuning from those files

### Pairing Rule

Pairing should be based on matching base filenames.

Examples:

- `clip001.mp3` + `clip001.srt`
- `clip002.wav` + `clip002.smi`
- `episode_a.mp4` + `episode_a.srt`

### UI Meaning

The training UI should expose:

- `Select Training Folder`
- `Scan Paired Files`
- `Preview Dataset`
- `Choose Model To Train`
- `Choose Training Mode`
- `Start Batch Training`

This workflow should live in a dedicated batch training window launched from the main app.

### Validation Expectations

The batch training flow should report:

- valid pairs found
- missing subtitle files
- missing media files
- unsupported formats
- parse failures
- estimated dataset size / duration
