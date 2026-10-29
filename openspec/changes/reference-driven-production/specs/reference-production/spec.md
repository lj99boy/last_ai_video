## ADDED Requirements

### Requirement: Narrative-led whole-film reference strategy
The workflow SHALL define viewing task, action-response-change, space, sound, reference roles, cut reason and acceptance across all current film beats, without mandatory reference counts or camera-side rules.

#### Scenario: Full-film migration
- **WHEN** work0002 is migrated
- **THEN** S001 through S020 retain the creator-confirmed current duration (68 seconds as of 2026-10-17) and have reference strategy, existing sources and explicit gaps, including the complete original ensemble and framed-wall ending; older duration baselines remain historical evidence

### Requirement: Reviewed reusable resources
The registry SHALL preserve sources, declared role restrictions, character era and age, file fingerprints and review state; missing or rejected sources MUST NOT be silently substituted.

#### Scenario: Wrong-era identity
- **WHEN** a 1636 identity is bound as a 1648 identity without a reviewed era-specific asset
- **THEN** compilation reports a blocking age/era conflict

#### Scenario: Practical assets
- **WHEN** the local reconstruction is delivered
- **THEN** the three current battle identity gaps and critical empty-cart structure have actual inspected media or a documented evidence-based reuse, rather than only planned filenames

### Requirement: Deterministic multimodal compilation
The compiler SHALL resolve all ordered media/Element references, aliases, prompt parts and dependency fingerprints and SHALL reject mode, role, missing-source and cyclic-dependency conflicts without external side effects.

#### Scenario: Multiple media and Element
- **WHEN** a segment uses a character Element plus environment and prop media
- **THEN** all references and ordered Element bindings appear in compiled output and the request fingerprint changes on any dependency change

#### Scenario: First and last frames
- **WHEN** first_last_frame is selected
- **THEN** only one or two ordered image references are accepted and Elements or arbitrary extra references are rejected

### Requirement: Complete readback validation
The executor MUST compare parameters, ordered references, full prompt/promptParts, selected resources, upstream links and recursive Element bindings before accepting saved draft and quote.

#### Scenario: Mutable Element
- **WHEN** an auxiliary or selected source changes while the node ID remains constant
- **THEN** old readiness and quote are rejected

### Requirement: Explicit pinned model capability evidence
New transactions MAY compile parameters beyond the default offline 16:9/720p profile only when the plan pins an actual official model-find file by work-relative path and SHA256. The executor SHALL preserve that contract in the semantic fingerprint, require explicit capability flags, and revalidate current official capabilities before quoting or running.

#### Scenario: Lower resolution with fixed evidence
- **WHEN** a new 480p plan supplies a matching pinned official contract that explicitly supports its mode and parameters
- **THEN** compile and prepare can validate that request without changing the default offline profile, reference checks or paid authorization requirements

#### Scenario: Missing, changed or obsolete contract
- **WHEN** the pinned file is missing, its bytes differ, a required flag is absent, or the live model no longer supports the request
- **THEN** the operation fails before draft creation or paid confirmation as applicable; repinning changed evidence changes the semantic fingerprint and invalidates the old request approval

#### Scenario: Historical 720p plan
- **WHEN** a plan has no model_contract field
- **THEN** the existing offline 720p validation and semantic fingerprints remain unchanged

### Requirement: Authorized bounded official CLI transactions
The adapter SHALL use only official CLI commands, keep stable operation identities, reserve once-count and cumulative maximum cost before run, fail closed on unknown outcomes, preserve immutable approval, and report upload/Element/request authorization deltas.

#### Scenario: Old approval with new assets
- **WHEN** a new role pack replaces the two previously approved images
- **THEN** the original450 approval remains intact while uncovered upload and request changes are reported and cannot execute

#### Scenario: Timeout after submission
- **WHEN** submission outcome is unknown
- **THEN** reserve and once-count remain occupied and recovery queries the original ID without automatic rerun

#### Scenario: Same approval and a new journal
- **WHEN** an already-bound once/cumulative approval is supplied with a different or reset execution journal
- **THEN** mutation is rejected before any cloud operation; approval usage is not reset by changing a file path, while read-only recovery of the original operation remains available

#### Scenario: Copied work root or rolled-back unknown upload
- **WHEN** the same approval is reused from another work root, including with the original journal, or an older journal snapshot omits a previously attempted unknown upload
- **THEN** a host-level authority bound to the original canonical work root, journal and operation identities rejects mutation before CLI calls; recovering the original operation does not allocate a fresh identity or restore allowance

#### Scenario: Retired production inputs
- **WHEN** a production plan is explicitly superseded, retired or denied execution by the current work policy
- **THEN** compilation cannot report it executable and prepare/run fail before cloud mutation, without rewriting historical requests, approvals or ledgers

#### Scenario: Optimized Python and confidential output
- **WHEN** authorization validation runs under python -O or CLI returns sensitive error payloads
- **THEN** gates remain enforced and tokens, signed URLs and raw provider payloads are absent from persisted logs and stdout

### Requirement: Honest validation and migration
The current entrypoint SHALL retire old single-frame execution, retain audit history and distinguish local tests, inspected assets, CLI contract checks, actual generation and original-speed editorial acceptance.

#### Scenario: Local completion
- **WHEN** offline tests and local CLI dry-runs pass
- **THEN** reports state local reconstruction status and do not claim dynamic consistency or whole-film acceptance
