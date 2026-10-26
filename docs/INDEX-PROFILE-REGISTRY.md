# Index Profile Registry Configuration

The Index profile registry is the sole authority for immutable Index profile bundles. The local runtime reads its initial registry from the JSON file named by `CE_INDEX_PROFILES_FILE`.

The file has exactly two top-level members:

- `profiles`: an array of complete profile bundles that conform to [the Index profile schema](contracts/schemas/index-profile.schema.json).
- `current`: an object mapping each profile name to the version selected for new writes, for example `{"technical":"1.0"}`.

Every bundle must pass the full schema and cross-field representation-size checks, and its SHA-256 digest must match the RFC 8785 canonical JSON content with `digest` and lifecycle `status` omitted. Each `name`/ `version` pair must be unique. Every current pointer must identify a configured bundle whose status is `active`. Invalid configuration fails startup; the service must not silently ignore malformed bundles or choose a fallback.

No built-in or implicit `default` profile exists. If `CE_INDEX_PROFILES_FILE` is unset, the registry is empty and profile lookups return `404 profile_not_found`. Configure an explicit registry before relying on profile resolution.

The runtime currently supports read-only resolution:

- `GET /api/v1/index/profiles/{profile_name}/current` resolves the configured current version.
- `GET /api/v1/index/profiles/{profile_name}/versions/{profile_version}` resolves an exact immutable version.

Responses contain `name`, `version`, `digest`, the complete `bundle`, and `request_id`. Unknown versions return `404 profile_not_found`; retired versions return `409 profile_retired` for new work. A profile's component fields and limits are never modified in place. To change them, publish a new version and update the current pointer in a reviewed deployment configuration change.

This is the initial profile-resolution slice, not the complete Index service. It does not yet implement profile publication/retirement operations, index storage, generation management, or Index readiness. Do not treat successful profile resolution as evidence that indexing or retrieval is ready.
