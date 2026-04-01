"""
_stub_sections.py
Defines the hand-written AI-quality documentation for each of the 13 stub sections.
Run by _apply_stubs.py to patch the markdown files.
"""

# Each entry: (domain, endpoint_key, section_markdown)
# endpoint_key = "METHOD full_path" exactly as stored in the file

STUBS = []

# ─────────────────────────────────────────────────────────────────────────────
# group / GET /v2/get-sub-groups
# ManageGroupsController@getSubGroups → manageGroupsModel->getSubGroups($request->gid)
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("group", "GET /v2/get-sub-groups", """\
## get-sub-groups

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v2/get-sub-groups` |
| **Controller** | `ManageGroupsController@getSubGroups` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Retrieves a list of sub-groups belonging to a parent group. Called by the admin/group management interface to present the group hierarchy. The `gid` (group ID) query parameter identifies the parent, and all child groups are returned for display or further management.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- Reads the `gid` query parameter from the request to scope the query to a single parent group.
- Delegates to `manageGroupsModel->getSubGroups()` which performs the database lookup.
- Returns the list of sub-groups directly; no further transformation is applied at the controller level.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `gid` | integer | Yes | The ID of the parent group whose sub-groups are to be listed. Passed as a query string parameter. |

### Database Operations
1. READ `groups` table — queries for all groups where `parent_id = $gid` to return the sub-group list.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# info / GET /v2/rep-info-request/get-payment-details/{id}
# RepInfoRequestController@getPaymentDetails → repository->getPaymentDetails($id)
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("info", "GET /v2/rep-info-request/get-payment-details/{id}", """\
## get-payment-details/{id}

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v2/rep-info-request/get-payment-details/{id}` |
| **Controller** | `RepInfoRequestController@getPaymentDetails` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Retrieves the payment details associated with a representative info request record. Used by internal admin workflows to review payment information tied to a specific rep info request before approving or processing it.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- The `{id}` path parameter identifies the specific rep info request record.
- Delegates to `repository->getPaymentDetails($id)` which fetches the payment data linked to that request.
- Returns the payment details directly as the response body.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | The ID of the rep info request whose payment details should be returned. |

### Database Operations
1. READ `rep_info_requests` / payment-related tables — fetches payment details linked to the given request ID.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# license / GET /v1/license/get/{id}
# RepLicenseController@getLicenseDetail → repLicense->getLicenseDetail($request, $licenseID)
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("license", "GET /v1/license/get/{id}", """\
## get/{id}

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v1/license/get/{id}` |
| **Controller** | `RepLicenseController@getLicenseDetail` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Retrieves the full detail record for a single representative license by its ID. Used by the agent management UI to display license information such as state, type, number, and expiry date for a specific license entry.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- The `{id}` path parameter is passed as `$licenseID` to `repLicense->getLicenseDetail()`.
- The service returns the complete license record including all stored fields.
- If no license is found for the given ID, the service is expected to return a failure response.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | The primary key of the representative license record to retrieve. |

### Database Operations
1. READ `rep_licenses` table — fetches the license record matching `license_id = $id`.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# note / GET /v1/get-all-notes/{policyID}
# NotesController@getAllNotes → noteFeatures->getAllNotes($request, $policyID)
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("note", "GET /v1/get-all-notes/{policyID}", """\
## get-all-notes/{policyID}

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v1/get-all-notes/{policyID}` |
| **Controller** | `NotesController@getAllNotes` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Retrieves all notes attached to a specific policy. Used by the policy detail view in the admin interface to display the complete note history — including agent notes, status changes, and free-text annotations — for a given policy.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- The `{policyID}` path parameter scopes the query to a single policy.
- Delegates to `noteFeatures->getAllNotes($request, $policyID)` which queries and formats the notes list.
- Returns the list wrapped in a `DataResponse` object.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `policyID` | integer | Yes | The ID of the policy whose notes should be returned. |

### Database Operations
1. READ `notes` table — fetches all note records where `policy_id = $policyID`, ordered by creation date.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# plan / GET /v1/get-plan-overview/{policyId}
# PlanOverviewController@getByPolicyId → repository->listAll($filters) + formattedItems()
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("plan", "GET /v1/get-plan-overview/{policyId}", """\
## get-plan-overview/{policyId}

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v1/get-plan-overview/{policyId}` |
| **Controller** | `PlanOverviewController@getByPolicyId` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Returns a formatted overview of all plans associated with a given policy. Used by the policy detail screen to display enrolled plan summaries — including plan names, types, statuses, and coverage details — in a single call.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- Sets `$filters['policy_id'] = $policyId` before querying.
- Calls `repository->listAll($filters)` to retrieve all plan overview records scoped to the policy.
- Passes the result through `repository->formattedItems()` to apply display formatting before returning.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `policyId` | integer | Yes | The ID of the policy whose plan overviews are to be retrieved. |

### Database Operations
1. READ `plan_overviews` table — selects all records where `policy_id = $policyId`.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# policy / GET /v1/get-policy-report/{policyId}
# PolicyController@show → repository->getPolicyDetail($policyId)
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("policy", "GET /v1/get-policy-report/{policyId}", """\
## get-policy-report/{policyId}

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v1/get-policy-report/{policyId}` |
| **Controller** | `PolicyController@show` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Retrieves a complete policy detail report for a given policy ID. Used by the admin and agent portals to display the full policy record — including member information, plan details, billing status, and associated metadata — in a single response.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- Calls `repository->getPolicyDetail($policyId)` to fetch the full policy record.
- If a policy is found, returns it wrapped in a `DataResponse`.
- If no policy exists for the given ID, calls `$this->failedResponse()` and returns an error response.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `policyId` | integer | Yes | The ID of the policy to retrieve the full report for. |

### Database Operations
1. READ `policies` table (and related joined tables) — fetches the full policy detail record for `policy_id = $policyId`.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# progress / GET /v1/total-progress-of-years/{fyear}/{tyear}
# GroupDashboardController@totalProgressOfYears → groupDashboardModel->totalYearProgress()
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("progress", "GET /v1/total-progress-of-years/{fyear}/{tyear}", """\
## total-progress-of-years/{fyear}/{tyear}

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v1/total-progress-of-years/{fyear}/{tyear}` |
| **Controller** | `GroupDashboardController@totalProgressOfYears` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Returns aggregate group enrollment/progress metrics spanning a range of years. Used by the group analytics dashboard to display year-over-year progress charts — such as total new enrollments, renewals, or member growth — between a start year and an end year.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- Passes `$fyear` (from-year) and `$tyear` (to-year) to `groupDashboardModel->totalYearProgress()`.
- If the model returns `status == 'success'`, wraps the `data` payload in a success response.
- If the model returns any other status, calls `$this->failedResponse($data['message'])` and returns an error.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `fyear` | integer | Yes | The starting year (e.g. `2022`) of the progress range. |
| `tyear` | integer | Yes | The ending year (e.g. `2024`) of the progress range. |

### Database Operations
1. READ enrollments/policy tables — aggregates progress metrics grouped by year between `fyear` and `tyear`.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# progress / GET /v1/total-progress-of-months/{fdate}/{tdate}
# GroupDashboardController@totalProgressOfMonths → groupDashboardModel->totalMonthsProgress()
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("progress", "GET /v1/total-progress-of-months/{fdate}/{tdate}", """\
## total-progress-of-months/{fdate}/{tdate}

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v1/total-progress-of-months/{fdate}/{tdate}` |
| **Controller** | `GroupDashboardController@totalProgressOfMonths` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Returns aggregate group enrollment/progress metrics broken down by month over a date range. Used by the group analytics dashboard to render month-over-month trend charts between two dates (e.g. to track new member enrollments per month).

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- Passes `$from_date` and `$to_date` (derived from `$fdate` and `$tdate`) to `groupDashboardModel->totalMonthsProgress()`.
- If the model returns `status == 'success'`, wraps the `data` payload in a success response.
- If the model returns any other status, calls `$this->failedResponse($data['message'])` and returns an error.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `fdate` | date string | Yes | The start date of the range (e.g. `2024-01-01`). |
| `tdate` | date string | Yes | The end date of the range (e.g. `2024-12-31`). |

### Database Operations
1. READ enrollments/policy tables — aggregates progress metrics grouped by month between `fdate` and `tdate`.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# rate / GET /v1/get-new-rates/{policy_id}
# ResourceController@getNewRates → resourceFeature->getNewRates($policy_id)
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("rate", "GET /v1/get-new-rates/{policy_id}", """\
## get-new-rates/{policy_id}

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v1/get-new-rates/{policy_id}` |
| **Controller** | `ResourceController@getNewRates` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Retrieves the updated/new premium rates applicable to a given policy at its current plan or renewal stage. Used by the policy management and renewal screens to display new rate information — such as updated premiums after a tier change, age band adjustment, or plan year renewal — before the changes are finalized.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- Passes `$policy_id` to `resourceFeature->getNewRates()` which computes or retrieves the applicable new rates.
- Returns the result wrapped in a `DataResponse` object.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `policy_id` | integer | Yes | The ID of the policy for which new rates should be calculated or retrieved. |

### Database Operations
1. READ `policies`, `plans`, and rate/pricing tables — fetches the current policy and computes updated rates based on the applicable plan and rate rules.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# renewal / GET /v1/get-renewal-letter-card-detail/{policy_id}
# ResourceController@getRenewalCardDetail → resourceFeature->getRenewalCardDetail($policy_id)
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("renewal", "GET /v1/get-renewal-letter-card-detail/{policy_id}", """\
## get-renewal-letter-card-detail/{policy_id}

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v1/get-renewal-letter-card-detail/{policy_id}` |
| **Controller** | `ResourceController@getRenewalCardDetail` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Retrieves the renewal letter and card detail for a specific policy. Used by the renewal workflow to populate the renewal notice — including member information, plan name, effective dates, and new premium amounts — that is generated and sent to policyholders during the renewal period.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- Passes `$policy_id` to `resourceFeature->getRenewalCardDetail()` which assembles all fields needed for the renewal letter/card.
- Returns the assembled detail object wrapped in a `DataResponse`.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `policy_id` | integer | Yes | The ID of the policy for which the renewal letter/card details are to be retrieved. |

### Database Operations
1. READ `policies`, `members`, `plans`, and renewal tables — fetches all relevant renewal data for the given policy.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# tier / GET /v1/tier-change-document/list/{policy_id}/{tier_update_id}
# TierChangeDocumentController@getAllDocumentsOfTierChange → repository->getAllDocumentsOfTierChange()
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("tier", "GET /v1/tier-change-document/list/{policy_id}/{tier_update_id}", """\
## list/{policy_id}/{tier_update_id}

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v1/tier-change-document/list/{policy_id}/{tier_update_id}` |
| **Controller** | `TierChangeDocumentController@getAllDocumentsOfTierChange` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Retrieves all documents uploaded for a specific tier change request on a policy. Used by the admin tier management screen to display the supporting documentation (e.g. census files, signed forms) that has been uploaded against a pending or approved tier update.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- Validates that `policy_id` is a required integer and exists in the `policies` table.
- Validates that `tier_update_id` is a required integer and exists in the `tier_updates` table.
- If validation fails, returns a validation error response.
- Calls `repository->getAllDocumentsOfTierChange($policyId, $tierUpdateId)` to fetch the document list.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `policy_id` | integer | Yes | The ID of the policy associated with the tier change. Must exist in `policies`. |
| `tier_update_id` | integer | Yes | The ID of the tier update record. Must exist in `tier_updates`. |

### Database Operations
1. READ `tier_change_documents` table — fetches all documents where `policy_id = $policyId` AND `tier_update_id = $tierUpdateId`.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# tier / POST /v1/tier-change-document/upload/{policy_id}/{tier_update_id}
# TierChangeDocumentController@uploadDocuments → repository->uploadTierChangeDocuments()
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("tier", "POST /v1/tier-change-document/upload/{policy_id}/{tier_update_id}", """\
## upload/{policy_id}/{tier_update_id}

| Field | Value |
|-------|-------|
| **Endpoint** | `POST /v1/tier-change-document/upload/{policy_id}/{tier_update_id}` |
| **Controller** | `TierChangeDocumentController@uploadDocuments` |
| **Auth Required** | Yes |
| **HTTP Method** | POST |

### Purpose
Uploads one or more supporting documents for a specific tier change request on a policy. Used by the admin tier management screen when attaching census files, signed authorization forms, or other supporting documents to a pending tier update before it can be approved.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- Accepts the uploaded file(s) via the multipart request body.
- Passes `$policyId`, `$tierUpdateId`, and the full `$request` (including files) to `repository->uploadTierChangeDocuments()`.
- The repository handles file storage (likely to S3 or local disk) and creates the corresponding database records.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `policy_id` | integer | Yes | The ID of the policy associated with the tier change. |
| `tier_update_id` | integer | Yes | The ID of the tier update record to attach documents to. |
| `files` | file(s) | Yes | One or more document files to upload (multipart form data). |

### Database Operations
1. WRITE `tier_change_documents` table — inserts a new record for each uploaded file, storing the file path/URL, `policy_id`, and `tier_update_id`.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: Uploads document file(s) to storage (S3 or local disk).

### Unknowns
None

---"""))

# ─────────────────────────────────────────────────────────────────────────────
# user / GET /v2/list-all-user-access-feature/{entity_id}/{entity_type}
# UserFeatureController@listAllUserAccessFeature → userFeatureRepository->listAllUserAccessFeature()
# ─────────────────────────────────────────────────────────────────────────────
STUBS.append(("user", "GET /v2/list-all-user-access-feature/{entity_id}/{entity_type}", """\
## list-all-user-access-feature/{entity_id}/{entity_type}

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /v2/list-all-user-access-feature/{entity_id}/{entity_type}` |
| **Controller** | `UserFeatureController@listAllUserAccessFeature` |
| **Auth Required** | Yes |
| **HTTP Method** | GET |

### Purpose
Returns all feature access permissions granted to a specific entity (agent, group, member, etc.). Used by the permissions management UI to display which platform features are enabled or disabled for a given user or entity, allowing admins to review and adjust access controls.

### Business Logic
- Requires a valid internal token (`verify.internal.token` middleware).
- The `{entity_id}` identifies the specific user/entity (e.g. agent ID, group ID).
- The `{entity_type}` specifies what kind of entity it is (e.g. `'agent'`, `'group'`, `'member'`).
- Delegates to `userFeatureRepository->listAllUserAccessFeature($entity_id, $entity_type)` which returns all feature flags for the entity.
- Returns the feature permission list directly.

### Input Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_id` | integer | Yes | The ID of the entity (agent, group, or member) whose feature access is being queried. |
| `entity_type` | string | Yes | The type of entity (e.g. `agent`, `group`, `member`) used to scope the permissions lookup. |

### Database Operations
1. READ `user_access_features` table — fetches all feature permission records where `entity_id = $entity_id` AND `entity_type = $entity_type`.

### Side Effects
- **Emails**: None
- **Jobs/Queues**: None
- **Events**: None
- **External APIs**: None
- **Files**: None

### Unknowns
None

---"""))
