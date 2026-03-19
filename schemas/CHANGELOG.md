# Schema Changelog

## [narrative.v1] - 2026-03-19

### Added
- Initial JSON Schema contract: `schemas/narrative.v1.schema.json`.
- Input contract with required `prompt` and optional `duration_sec`, `style`, `language`.
- Structured output contract with:
  - `synopsis`
  - `characters[]` (1 to 2)
  - `scenes[]` (exactly 1)
  - `shots[]`
  - `asset_refs[]`
  - `audio_plan`
  - `render_plan`
- V1 constraints from SPEC:
  - scene count fixed to 1
  - character count limited to 1-2
  - duration limited to 30-60 seconds
- Traceability fields:
  - `request_id`
  - `schema_version`
  - `provider_trace`

### Notes
- Future schema versions should be added as new files (example: `narrative.v2.schema.json`) and documented in this changelog.
