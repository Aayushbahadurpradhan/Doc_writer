"""
Deep PHP controller analyzer for commission_billing.
Extracts: table names, columns, JOINs, WHERE conditions, response fields, request params.
Produces nuerabenefits-quality documentation.
"""
import glob
import json
import os
import re

PROJECT = "D:/CloudTech_main/commission_billing"
OUTPUT_BASE = "D:/CloudTech_main/Doc_writer/doc_output/commission_billing"
DOCS_BACKEND = f"{OUTPUT_BASE}/docs/backend"

# ── Model → table map (from grep output) ──────────────────────────────────────
MODEL_TABLE = {
    "AddDNP": "agent_dnp",
    "AdminToGroupSwitch": "admin_to_group_switch",
    "AdminToMemberSwitch": "admin_to_member_switch",
    "AdminToRepSwitch": "admin_to_rep_switch",
    "AdvanceConfiguration": "advance_configurations",
    "AdvanceConfigurationSub": "advance_configurations_sub",
    "AgentACHPayment": "agent_achpayment",
    "AgentInfo": "agent_info",
    "AgentPlanConfigurations": "agent_plan_configuartions",
    "AgentPlanOverrideConfigurations": "agent_plan_override_configuartions",
    "AgentPn": "agent_pn",
    "AgentPNCheckInfo": "agent_pn_check_info",
    "AgentPNFundingSource": "agent_pn_funding_source",
    "AgentPNInfo": "agent_pn_info",
    "AgentPnLog": "agent_pn_logs",
    "AgentUplineHistory": "agent_upline_history",
    "AgentUplineCutoff": "agent_upline_cutoffs",
    "AgentUplineChange": "agent_upline_changes",
    "AgentCommissionType": "agent_commission_types",
    "AgentAffiliateConfig": "agent_affiliate_configs",
    "Affiliates": "affiliates",
    "AffiliateCommission": "affiliate_commission",
    "AssociationFeeCommission": "association_commissions",
    "AssociationFeeConf": "assoc_commission_confs",
    "Beneficiary": "beneficiaries",
    "BundledPlan": "bundled_plans",
    "CommissionApprovalLog": "commission_approval_log",
    "CommissionDataHistory": "commission_data_history",
    "CommissionPayEmailLog": "commission_pay_email_log",
    "CommissionPayLog": "commission_pay_log",
    "CommissionPaySchedule": "commission_pay_schedule",
    "CommissionPrice": "commission_price",
    "ContractConfiguration": "contract_configuration",
    "ContractConfigurationDetails": "contract_configuration_details",
    "ContractInfo": "contract_info",
    "ContractPlanDetails": "contract_plan_details",
    "ContractTypes": "contract_types",
    "CustomeHomepage": "custom_homepage",
    "Dependent": "dependents",
    "DependentInPolicy": "dependents_in_policy",
    "DependentPolicy": "dependent_policies",
    "DependentUpdate": "dependent_updates",
    "EmailTemplateDesign": "nb_template_design",
    "EmailTemplates": "nb_email_templates",
    "EPCommissionDataHistory": "ep_commission_data_history",
    "GroupEft": "group_eft",
    "GroupInfo": "group_info",
    "GroupPlans": "group_plans",
    "GroupUpdates": "group_updates",
    "ManageAgentScripts": "manage_agent_scripts",
    "MemberRegistrationStorage": "member_registration_storage",
    "NbAssociationConfig": "nb_association_config",
    "NbBankfiles": "nb_bankfiles",
    "NbBankIds": "nb_bankids",
    "NbBounceFeeConfig": "nb_bounce_fee_configs",
    "NbCheckInfo": "nb_check_infos",
    "NbCreditCard": "nb_credit_cards",
    "NbDatesConfig": "nb_dates_config",
    "NbEftInfo": "nb_eft_info",
    "NbEmailQueues": "nb_email_queues",
    "NbEmailSettings": "nb_email_settings_create",
    "NbGroupInvoice": "nb_group_invoices",
    "NbGroupPayment": "nb_group_payments",
    "NbInvoices": "nb_invoices",
    "NbInvoiceSchedules": "nb_invoice_schedules",
    "NbInvoicesItem": "nb_invoice_items",
    "NbKnowledgeFeed": "nb_knowledge_feeds",
    "NbLateFeeConfig": "nb_late_fee_configs",
    "NbOneTimeCommConf": "nb_one_time_comm_confs",
    "NbOverrideCommConf": "nb_override_comm_confs",
    "NbPayerIds": "nb_payerids",
    "NbPayments": "nb_payments",
    "NbSkipAgentPlansCommConf": "nb_skip_agent_plans_comm_confs",
    "NbSkipPlansCommConf": "nb_skip_plans_comm_confs",
    "NbStatementFeeConfig": "nb_statement_fee_configs",
    "NbTemplateDesign": "nb_template_design",
    "NbTireBasedCommConf": "nb_tire_based_comm_confs",
    "NbUserPaymentInfo": "nb_user_payment_infos",
    "NetPrice": "net_price",
    "OneTimeAdjustment": "onetime_adjustments",
    "OnetimeCommissionConfig": "onetime_commission_config",
    "PaymentCC": "payment_cc",
    "PaymentCCMerchant": "payment_cc_merchant",
    "PaymentEft": "payment_eft",
    "PaymentValidationLogFiles": "payment_validation_log_files",
    "PaymentValidationRecords": "payment_validation_records",
    "PlanCommissionPrice": "plan_commission_price",
    "Planconfiguartion": "plan_configuration",
    "PlanNetPrice": "plan_net_price",
    "PlanOverview": "plan_overview",
    "PlanPolicy": "plan_policies",
    "PlanPolicyMember": "plan_policies_member",
    "PlanPremiumPrice": "plan_premium_price",
    "PlanPricing": "plan_pricing",
    "PlanPricingDisplay": "plans_pricing_display",
    "Plans": "plans",
    "Policies": "policies",
    "PolicyUpdates": "policy_updates",
    "PremiumPrice": "premium_price_table",
    "QboLog": "qbo_logs",
    "QboLogRecord": "qbo_log_records",
    "RecurringSelfPayInfo": "recurring_self_payment_info",
    "RepContract": "rep_contract",
    "RepContractDetails": "rep_contract_details",
    "Role": "roles",
    "RoleUsers": "role_users",
    "SchedulePaymentLog": "schedule_payment_log",
    "SpecialCommission": "special_commission",
    "SsoUser": "sso_users",
    "SubGroup": "sub_groups",
    "TierUpdate": "tier_updates",
    "UserInfo": "userinfo",
    "UserInfoPolicyAddress": "userinfo_policy_address",
    "Commission_history": "commission_history",
    "NbFeeManagement": "nb_fee_management",
    "NbFeeManageLog": "nb_fee_manage_logs",
}

# Routes inside auth:api group (majority)
AUTH_REQUIRED_CONTROLLERS = {
    "CompaniesController", "PlansController", "PlanConfigurationController",
    "AgentsController", "CommissionController", "AffiliatesController",
    "InvoiceController", "GroupsController", "UserController", "RolesController",
    "TemplateController", "DynamicReportGeneratorController", "AnalyticsController",
    "RxAnalyticsController", "OnetimeLatefeeController", "MainDashboardController",
    "OnlineController", "PaymentController", "StatesController",
    "CommissionOverviewController", "AutoCommissionPaymentController",
    "AgentPaynoteController", "PaynoteSyncController", "AdvCommissionConfigController",
    "BulkPaymentController", "BlackListAccountController", "MasterSearchController",
    "ManageClientsController", "ChecklistController", "PendingEnrollmentsController",
    "QuickBookController", "KnowledgeBaseController", "ConsolidatedReportController",
    "ContractSheetController", "AccountDashboardController", "RecurringPaymentController",
}
# Open routes (no auth needed)
NO_AUTH_CONTROLLERS = {
    "InvoiceReportsController", "DatabaseController", "GroupSwitchController",
    "MemberSwitchController", "RepSwitchController", "InvoiceGenerationController",
    "CheckLoginParamsController", "PaymentSyncApiController", "PaymentValidationController",
    "AutoRefundOverPayment",
}

# ── Controller file resolution cache ──────────────────────────────────────────
_ctrl_cache = {}

def find_ctrl_file(class_name):
    if class_name in _ctrl_cache:
        return _ctrl_cache[class_name]
    # Strategy 1: direct path conversion
    path = class_name.replace("App\\", "").replace("\\", "/")
    candidate = f"{PROJECT}/app/{path}.php"
    if os.path.exists(candidate):
        _ctrl_cache[class_name] = candidate
        return candidate
    # Strategy 2: walk and score
    basename = class_name.split("\\")[-1]
    candidates = glob.glob(f"{PROJECT}/app/Http/Controllers/**/{basename}.php", recursive=True)
    if candidates:
        def score(p):
            parts = [s.lower() for s in class_name.split("\\")[1:]]
            return sum(1 for s in parts if s in p.lower())
        candidates.sort(key=score, reverse=True)
        _ctrl_cache[class_name] = candidates[0]
        return candidates[0]
    _ctrl_cache[class_name] = None
    return None

def extract_method(content, method_name):
    """Extract method body with balanced braces."""
    pat = re.compile(
        r'(public|protected|private)?\s*function\s+' + re.escape(method_name) + r'\s*\(',
        re.IGNORECASE | re.MULTILINE
    )
    m = pat.search(content)
    if not m:
        # try case-insensitive fallback
        pat2 = re.compile(r'function\s+(' + re.escape(method_name) + r')\s*\(', re.IGNORECASE)
        m = pat2.search(content)
        if not m:
            return None
    brace_pos = content.find('{', m.end())
    if brace_pos == -1 or brace_pos - m.end() > 600:
        return None
    depth, i = 0, brace_pos
    while i < len(content):
        c = content[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return content[brace_pos : i+1]
        i += 1
    return None

# ── Deep query extractor ───────────────────────────────────────────────────────

def extract_queries(body):
    """Extract detailed DB operation info from method body."""
    queries = []

    # 1. DB::table patterns
    tbl_calls = re.finditer(r"DB::table\(['\"](\w+)['\"]\)", body)
    for m in tbl_calls:
        table = m.group(1)
        # get a window after this match
        window_start = m.start()
        window_end = min(len(body), m.start() + 800)
        window = body[window_start:window_end]
        q = _analyze_fluent_chain(table, window, 'db_facade')
        queries.append(q)

    # 2. DB::select / DB::statement (raw SQL)
    for m in re.finditer(r'DB::(?:select|statement|insert|update|delete)\s*\(\s*["\']([^"\']{5,})', body):
        raw_sql = m.group(1).strip()
        # try to extract table from raw SQL
        tbl_m = re.search(r'(?:FROM|INTO|UPDATE|TABLE)\s+`?(\w+)`?', raw_sql, re.IGNORECASE)
        table = tbl_m.group(1) if tbl_m else 'UNKNOWN'
        op = 'SELECT'
        if re.search(r'^INSERT', raw_sql, re.IGNORECASE):
            op = 'INSERT'
        elif re.search(r'^UPDATE', raw_sql, re.IGNORECASE):
            op = 'UPDATE'
        elif re.search(r'^DELETE', raw_sql, re.IGNORECASE):
            op = 'DELETE'
        queries.append({
            'type': 'raw_sql',
            'operation': op,
            'table': table,
            'columns_read': ['*'],
            'columns_written': [],
            'conditions': _extract_where_from_raw(raw_sql),
            'joins': _extract_joins_from_raw(raw_sql),
            'order_group': None,
            'aggregates': None,
            'transaction': False,
            'soft_deletes': False,
            'raw_sql': raw_sql[:300],
        })

    # 3. Eloquent Model::where / Model::find etc.
    model_calls = re.finditer(
        r'(\w+)::(where|find|findOrFail|all|create|firstOrCreate|updateOrCreate|firstOrNew|insert|update|delete|with|select)\s*\(',
        body
    )
    seen_models = set()
    for m in model_calls:
        model = m.group(1)
        op_method = m.group(2).lower()
        if model in ('DB', 'Auth', 'Cache', 'Log', 'Mail', 'App', 'Config', 'Route',
                     'Session', 'Storage', 'Validator', 'Event', 'Queue', 'Artisan',
                     'Hash', 'Http', 'Schema', 'PDFMerger', 'response', 'request'):
            continue
        if model not in MODEL_TABLE and model[0].islower():
            continue
        table = MODEL_TABLE.get(model, _model_to_table_guess(model))
        if table in seen_models:
            continue
        seen_models.add(table)

        window_start = m.start()
        window_end = min(len(body), m.start() + 1000)
        window = body[window_start:window_end]
        q = _analyze_fluent_chain(table, window, 'eloquent', model, op_method)
        queries.append(q)

    # 4. new ModelClass() instantiation — $model = new Foo(); $model->method(...)
    for m in re.finditer(r'new\s+(\w+)\s*\(', body):
        model = m.group(1)
        if model not in MODEL_TABLE:
            continue
        table = MODEL_TABLE[model]
        if table in seen_models:
            continue
        seen_models.add(table)
        # window from instantiation through end of method
        window_start = m.start()
        window_end = min(len(body), m.start() + 1200)
        window = body[window_start:window_end]
        # detect operation from method calls on the instance
        op_method = None
        if re.search(r'->(?:save|create|insert|add)\w*\(', window):
            op_method = 'create'
        elif re.search(r'->(?:delete|remove)\w*\(', window):
            op_method = 'delete'
        elif re.search(r'->(?:update|edit|modify)\w*\(', window):
            op_method = 'update'
        q = _analyze_fluent_chain(table, window, 'eloquent', model, op_method)
        queries.append(q)

    return queries

def _model_to_table_guess(model):
    """Guess table name from model name using Laravel conventions."""
    # Convert CamelCase to snake_case
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', model)
    s = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s).lower()
    # Pluralize
    if s.endswith('y') and len(s) > 2:
        return s[:-1] + 'ies'
    if not s.endswith('s'):
        return s + 's'
    return s

def _analyze_fluent_chain(table, window, qtype, model=None, op_method=None):
    """Analyze a fluent query chain to extract columns, conditions, joins etc."""
    # Determine operation type
    op = 'SELECT'
    if op_method in ('create', 'insert', 'firstOrCreate', 'firstOrNew'):
        op = 'INSERT'
    elif op_method in ('update', 'updateOrCreate', 'save'):
        op = 'UPDATE'
    elif op_method in ('delete', 'forceDelete'):
        op = 'DELETE'
    if re.search(r'->(?:create|insert|save|store)\s*\(', window):
        op = 'INSERT'
    elif re.search(r'->(?:update|increment|decrement)\s*\(', window):
        op = 'UPDATE'
    elif re.search(r'->(?:delete|destroy|forceDelete)\s*\(', window):
        op = 'DELETE'

    # Extract ->select('cols')
    cols_read = []
    sel_m = re.findall(r"->select\s*\(\s*'([^']+)'", window)
    sel_m2 = re.findall(r'->select\s*\(\s*"([^"]+)"', window)
    sel_m3 = re.findall(r'->select\s*\(\s*\[([^\]]+)\]', window)
    for s in sel_m + sel_m2:
        cols_read.extend([c.strip().strip("'\"") for c in s.split(',')])
    for s in sel_m3:
        cols_read.extend([c.strip().strip("'\"") for c in s.split(',')])
    # ->get(['col1', 'col2'])
    get_cols = re.findall(r"->(?:get|pluck)\s*\(\s*\[([^\]]+)\]", window)
    for s in get_cols:
        cols_read.extend([c.strip().strip("'\"") for c in s.split(',')])

    if not cols_read:
        cols_read = ['*']

    # Extract WHERE conditions (deduplicated)
    conditions = []
    seen_conds = set()

    def _add_cond(c):
        key = c.strip().lower()
        if key not in seen_conds:
            seen_conds.add(key)
            conditions.append(c)

    # whereRaw('raw expression')
    for m in re.finditer(r"->whereRaw\s*\(\s*['\"]([^'\"]+)['\"]", window):
        _add_cond(m.group(1)[:100])

    # 3-arg where: ->where('col', 'LIKE', ...) or ->where('col', '=', ...)
    # or ->orWhere('col', 'OP', ...)
    for m in re.finditer(
        r"->(?:or)?[Ww]here\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]{1,20})['\"]",
        window
    ):
        field, where_op = m.group(1), m.group(2).strip().upper()
        if where_op in ('LIKE', 'NOT LIKE', '=', '!=', '<>', '>', '<', '>=', '<='):
            _add_cond(f"{field} {where_op} ?")
        else:
            # 2-arg form: ->where('col', 'literal_value')
            _add_cond(f"{field} = '{where_op}'")

    # 2-arg where with unquoted value: ->where('col', $var) or ->where('col', request(...))
    for m in re.finditer(
        r"->(?:or)?[Ww]here\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*(?!\s*['\"])([^)]{1,40})\)",
        window
    ):
        field = m.group(1)
        val_expr = m.group(2).strip()
        if not any(field.lower() == c.split(' ')[0].lower() for c in conditions):
            _add_cond(f"{field} = {val_expr[:40]}")

    # whereIn('col', [...])
    for m in re.finditer(r"->whereIn\s*\(\s*['\"]([^'\"]+)['\"]", window):
        _add_cond(f"{m.group(1)} IN (?)")

    # whereNotNull / whereNull
    for m in re.finditer(r"->whereNotNull\s*\(\s*['\"]([^'\"]+)['\"]", window):
        _add_cond(f"{m.group(1)} IS NOT NULL")
    for m in re.finditer(r"->whereNull\s*\(\s*['\"]([^'\"]+)['\"]", window):
        _add_cond(f"{m.group(1)} IS NULL")

    # Extract JOINs
    joins = []
    for m in re.finditer(r"->(leftJoin|join|rightJoin|innerJoin)\s*\(\s*['\"](\w+)['\"]", window):
        jtype = {'leftJoin': 'LEFT JOIN', 'join': 'INNER JOIN',
                 'rightJoin': 'RIGHT JOIN', 'innerJoin': 'INNER JOIN'}[m.group(1)]
        join_tbl = m.group(2)
        # look for ON condition
        j_window = window[m.start():m.start()+200]
        on_cols = re.findall(r"['\"]([^'\"]+\.\w+)['\"]", j_window)
        if len(on_cols) >= 2:
            joins.append(f"{jtype} {join_tbl} ON {on_cols[0]} = {on_cols[1]}")
        else:
            joins.append(f"{jtype} {join_tbl}")

    # Columns written
    cols_written = []
    create_data = re.findall(r"->(?:create|insert|update)\s*\(\s*\[([^\]]{10,200})\]", window)
    for s in create_data:
        for kv in re.findall(r"['\"](\w+)['\"]", s):
            if kv not in cols_written:
                cols_written.append(kv)

    # ORDER/GROUP BY
    order_group = None
    ob = re.search(r"->orderBy\s*\(\s*['\"]([^'\"]+)['\"]", window)
    gb = re.search(r"->groupBy\s*\(\s*['\"]([^'\"]+)['\"]", window)
    if ob:
        order_group = f"ORDER BY {ob.group(1)}"
    if gb:
        order_group = (order_group + ", " if order_group else "") + f"GROUP BY {gb.group(1)}"

    # Aggregates
    aggregates = None
    if re.search(r"->count\(", window):
        aggregates = "COUNT(*)"
    elif re.search(r"->sum\s*\(\s*['\"]([^'\"]+)['\"]", window):
        m2 = re.search(r"->sum\s*\(\s*['\"]([^'\"]+)['\"]", window)
        aggregates = f"SUM({m2.group(1)})"

    # Pagination
    is_paginated = bool(re.search(r"->paginate\(", window))
    if is_paginated and op == 'SELECT':
        op = 'SELECT (paginated)'

    # Soft deletes
    soft_deletes = bool(re.search(r"->(?:withTrashed|onlyTrashed|forceDelete)\(", window))
    trashed = bool(re.search(r"deleted_at|softDelete", window))

    # Transaction
    in_transaction = bool(re.search(r"DB::(?:beginTransaction|transaction)\(", window))

    # Build reconstructed SQL
    sql = _build_sql(op, table, cols_read, cols_written, conditions, joins, order_group, aggregates)

    return {
        'type': qtype,
        'operation': op,
        'table': table,
        'columns_read': cols_read[:10],
        'columns_written': cols_written[:10] if cols_written else ['None'],
        'conditions': conditions[:5] if conditions else ['None'],
        'joins': joins if joins else ['None'],
        'order_group': order_group or 'None',
        'aggregates': aggregates or 'None',
        'transaction': in_transaction,
        'soft_deletes': soft_deletes or trashed,
        'raw_sql': sql,
    }

def _extract_where_from_raw(sql):
    m = re.search(r'WHERE\s+(.{5,100}?)(?:ORDER|GROUP|LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
    return [m.group(1).strip()[:100]] if m else ['None']

def _extract_joins_from_raw(sql):
    joins = re.findall(r'(?:LEFT\s+JOIN|JOIN|INNER\s+JOIN)\s+(\w+\s+ON\s+[^\n]+)', sql, re.IGNORECASE)
    return joins[:3] if joins else ['None']

def _build_sql(op, table, cols, cols_written, conditions, joins, order_group, aggregates):
    """Build a reconstructed SQL string."""
    base_op = op.split(' ')[0]
    if base_op == 'SELECT':
        col_str = ', '.join(c for c in cols if c != '*')[:200] or '*'
        if aggregates and aggregates != 'None':
            col_str = f"{aggregates}, {col_str}" if col_str != '*' else aggregates
        sql = f"SELECT {col_str}\nFROM {table}"
        for j in joins:
            if j != 'None':
                sql += f"\n{j}"
        cond_str = [c for c in conditions if c != 'None']
        if cond_str:
            sql += "\nWHERE " + "\n  AND ".join(cond_str)
        if order_group and order_group != 'None':
            sql += f"\n{order_group}"
        if 'paginated' in op:
            sql += "\nLIMIT ? OFFSET ?"
    elif base_op == 'INSERT':
        cols_str = ', '.join(c for c in cols_written if c != 'None')[:200] if cols_written != ['None'] else 'column_list'
        sql = f"INSERT INTO {table} ({cols_str})\nVALUES (?)"
    elif base_op == 'UPDATE':
        set_str = ', '.join(f"{c} = ?" for c in cols_written if c != 'None')[:150] if cols_written != ['None'] else 'column = ?'
        sql = f"UPDATE {table}\nSET {set_str}"
        cond_str = [c for c in conditions if c != 'None']
        if cond_str:
            sql += "\nWHERE " + "\n  AND ".join(cond_str)
    elif base_op == 'DELETE':
        sql = f"DELETE FROM {table}"
        cond_str = [c for c in conditions if c != 'None']
        if cond_str:
            sql += "\nWHERE " + "\n  AND ".join(cond_str)
    else:
        sql = f"-- {op} on {table}"
    return sql

# ── Request param extractor ────────────────────────────────────────────────────

def extract_request_params(body):
    """Extract all request() and $request-> parameters from method body."""
    params = {}
    # request('param') or request->input('param')
    for m in re.finditer(r"request\s*\(\s*['\"](\w+)['\"]", body):
        params[m.group(1)] = 'string'
    for m in re.finditer(r'\$request->input\s*\(\s*[\'"](\w+)[\'"]', body):
        params[m.group(1)] = 'string'
    for m in re.finditer(r'\$request->(\w+)\b', body):
        name = m.group(1)
        if name not in ('all', 'except', 'has', 'filled', 'validate', 'file', 'json',
                        'isMethod', 'method', 'url', 'path', 'header', 'bearerToken',
                        'ip', 'server', 'cookie', 'query', 'post', 'merge', 'replace',
                        'user', 'route', 'session', 'segment', 'segments', 'is'):
            params[name] = 'string'
    # $request->validate rules
    val_m = re.search(r'\$request->validate\s*\(\s*\[([^\]]+)\]', body, re.DOTALL)
    if val_m:
        for rule_m in re.finditer(r"['\"](\w+)['\"]\s*=>\s*['\"]([^'\"]+)['\"]", val_m.group(1)):
            pname = rule_m.group(1)
            rules = rule_m.group(2)
            ptype = 'string'
            if 'integer' in rules or 'numeric' in rules:
                ptype = 'integer'
            if 'email' in rules:
                ptype = 'email'
            if 'boolean' in rules:
                ptype = 'boolean'
            if 'array' in rules:
                ptype = 'array'
            params[pname] = ptype
    return params

# ── Response field extractor ───────────────────────────────────────────────────

def extract_response(body, route):
    """Extract response structure from method body."""
    method = route['action'].lower()
    ctrl_name = route['controller'].split('\\')[-1].replace('Controller', '')

    # Check response()->json([...])
    resp_match = re.search(r'response\(\)->json\(\s*\[([^\]]{5,600})\]', body, re.DOTALL)
    if resp_match:
        fields = _parse_php_array_keys(resp_match.group(1))
        if fields:
            return _build_response_schema(fields, route), 'json'

    # Check return $variable or return array
    # Look for what gets returned
    ret_match = re.search(r'return\s+\$(\w+)\s*;', body)
    if ret_match:
        var_name = ret_match.group(1)
        # Try to find what $var_name was assigned
        assign_m = re.search(
            r'\$' + var_name + r'\s*=\s*(?:response\(\)->json\(|new\s+\w+\(|\[)',
            body
        )

    # Infer from DB select columns
    queries = extract_queries(body)
    if queries:
        q = queries[0]
        cols = q.get('columns_read', ['*'])
        if cols != ['*'] and cols:
            fields = [c.split('.')[-1] for c in cols]
            return _build_response_schema(fields, route), _guess_response_type(body)

    # Infer from operation type
    return _infer_response_schema(ctrl_name, method, route), _guess_response_type(body)

def _parse_php_array_keys(arr_str):
    """Extract keys from PHP array string."""
    keys = re.findall(r"['\"](\w+)['\"]\s*=>", arr_str)
    return keys

def _guess_response_type(body):
    if re.search(r'->paginate\(', body):
        return 'paginated_array'
    if re.search(r'->get\(', body):
        return 'array_of_objects'
    if re.search(r'->first\(', body) or re.search(r'->find\(', body):
        return 'json'
    return 'json'

def _build_response_schema(fields, route):
    """Build a JSON schema object from field names."""
    ctrl = route['controller'].split('\\')[-1].replace('Controller', '').lower()
    schema = {}
    for f in fields[:15]:
        fname = f.strip().strip("'\"").split('.')[-1]
        if not fname or fname.startswith('$'):
            continue
        # Infer type from name
        if re.search(r'_id$|^id$', fname):
            schema[fname] = 'integer'
        elif re.search(r'_at$|date|_date$|time|timestamp', fname):
            schema[fname] = 'datetime|nullable'
        elif re.search(r'^is_|^has_|^can_|^allow', fname):
            schema[fname] = 'boolean'
        elif re.search(r'amount|price|fee|rate|total|balance|cost', fname):
            schema[fname] = 'decimal|float'
        elif re.search(r'count|num_|number|qty', fname):
            schema[fname] = 'integer'
        elif re.search(r'email', fname):
            schema[fname] = 'string|email'
        elif re.search(r'phone|fax|mobile', fname):
            schema[fname] = 'string'
        elif re.search(r'status|type|level|code|flag', fname):
            schema[fname] = 'string|enum'
        else:
            schema[fname] = 'string'
    return schema

def _infer_response_schema(ctrl_name, method, route):
    """Infer response schema from controller/method name."""
    ctrl_lower = ctrl_name.lower()
    # Common response patterns
    base = {}
    if 'agent' in ctrl_lower:
        base = {'agent_id': 'integer', 'agent_fname': 'string', 'agent_lname': 'string',
                'agent_email': 'string|email', 'agent_code': 'string', 'agent_status': 'string|enum',
                'agent_level': 'string', 'created_at': 'datetime'}
    elif 'invoice' in ctrl_lower:
        base = {'invoice_id': 'integer', 'invoice_date': 'datetime', 'invoice_end_date': 'date',
                'invoice_amount': 'decimal', 'invoice_status': 'string|enum',
                'policy_id': 'string', 'invoice_type': 'string'}
    elif 'payment' in ctrl_lower:
        base = {'payment_id': 'integer', 'payment_amount': 'decimal', 'payment_date': 'datetime',
                'payment_status': 'string|enum', 'payment_method': 'string',
                'invoice_id': 'integer', 'policy_id': 'string'}
    elif 'commission' in ctrl_lower:
        base = {'agent_id': 'integer', 'commission_amount': 'decimal', 'commission_date': 'date',
                'plan_id': 'integer', 'policy_id': 'string', 'commission_type': 'string'}
    elif 'group' in ctrl_lower:
        base = {'group_id': 'integer', 'group_name': 'string', 'group_status': 'string',
                'group_type': 'string', 'created_at': 'datetime'}
    elif 'plan' in ctrl_lower:
        base = {'plan_id': 'integer', 'plan_name': 'string', 'plan_type': 'string',
                'plan_status': 'string', 'carrier': 'string', 'premium_amount': 'decimal'}
    elif 'user' in ctrl_lower:
        base = {'user_id': 'integer', 'email': 'string|email', 'name': 'string',
                'role': 'string', 'status': 'string', 'created_at': 'datetime'}
    elif 'company' in ctrl_lower or 'carrier' in ctrl_lower:
        base = {'id': 'integer', 'name': 'string', 'code': 'string',
                'status': 'string', 'created_at': 'datetime'}
    else:
        base = {'id': 'integer', 'status': 'string', 'message': 'string',
                'data': 'object', 'created_at': 'datetime'}

    # Adjust for list vs single
    if re.search(r'(?:render|list|all|index|get)', method, re.IGNORECASE):
        return base  # array of these
    return base

# ── Auth detection (from route middleware context) ─────────────────────────────

def is_auth_required(route):
    mw = route.get('middleware', [])
    if mw and any('auth' in str(m) for m in mw):
        return True
    ctrl_short = route['controller'].split('\\')[-1]
    if ctrl_short in AUTH_REQUIRED_CONTROLLERS:
        return True
    if ctrl_short in NO_AUTH_CONTROLLERS:
        return False
    # check route path for clues
    if 'check.static.token' in str(route.get('middleware', [])):
        return False
    return True  # default: assume auth required for API routes

# ── Business logic inference ───────────────────────────────────────────────────

def infer_business_logic(body, route, queries, params):
    """Generate meaningful bullet points from actual code analysis."""
    points = []
    action = route['action']
    ctrl = route['controller'].split('\\')[-1].replace('Controller', '')

    # Validation
    val_m = re.search(r'\$request->validate\s*\(\s*\[([^\]]{10,300})\]', body, re.DOTALL)
    if val_m:
        rules = val_m.group(1).strip()[:200]
        points.append(f"Validates request: `{rules}`")

    # Auth/permission checks
    if re.search(r"abort\s*\(\s*40[13]", body):
        points.append("Returns 403 Forbidden or 401 Unauthorized if access check fails")
    if re.search(r'Auth::user\(\)|auth\(\)->user\(\)', body):
        points.append("Retrieves the authenticated user from the session/token")

    # Query-based logic
    for q in queries:
        table = q['table']
        op = q['operation']
        cols = [c for c in q['columns_read'] if c != '*'][:5]
        conds = [c for c in q['conditions'] if c != 'None'][:3]
        joins = [j for j in q['joins'] if j != 'None'][:2]

        if op.startswith('SELECT'):
            desc = f"Queries `{table}` table"
            if conds:
                desc += f" filtered by: {', '.join(conds)}"
            if joins:
                desc += f"; joins {', '.join(j.split(' ON ')[0] for j in joins)}"
            if 'paginated' in op:
                desc += " (paginated results)"
            points.append(desc)
        elif op == 'INSERT':
            points.append(f"Inserts a new record into `{table}`")
        elif op == 'UPDATE':
            points.append(f"Updates record(s) in `{table}`")
        elif op == 'DELETE':
            points.append(f"Deletes record(s) from `{table}`")

    # Conditional flags in body
    if re.search(r'->withTrashed\(\)', body):
        points.append("Includes soft-deleted records in query results")
    if re.search(r'->paginate\(', body):
        points.append("Returns paginated results")
    if re.search(r'dispatch\(new\s+(\w+)', body):
        m = re.search(r'dispatch\(new\s+(\w+)', body)
        points.append(f"Dispatches job: `{m.group(1)}`")
    if re.search(r'Mail::|new\s+\w+Mail\(', body):
        points.append("Sends an email notification")
    if re.search(r'event\(new\s+(\w+)', body):
        m = re.search(r'event\(new\s+(\w+)', body)
        points.append(f"Fires event: `{m.group(1)}`")
    if re.search(r'Storage::|file_put_contents|fopen|fwrite', body):
        points.append("Reads or writes file(s) to storage")
    if re.search(r'GuzzleHttp|GuzzleClient|Http::(?:get|post|put|patch|delete)|curl_exec', body):
        ext_url = re.search(r"config\(['\"]([^'\"]{5,40})['\"]\)", body)
        target = ext_url.group(1) if ext_url else 'external service'
        points.append(f"Proxies to external API via HTTP client (`{target}`)")        
    if re.search(r'DB::beginTransaction|DB::transaction', body):
        points.append("Wraps operations in a database transaction for atomicity")

    if not points:
        # simple fallback with action inference
        action_lower = action.lower()
        if any(k in action_lower for k in ['render', 'get', 'fetch', 'list', 'index', 'show']):
            points.append(f"Retrieves and returns data from the database for `{ctrl}` resource")
        elif any(k in action_lower for k in ['save', 'store', 'create', 'add']):
            points.append(f"Validates and persists new `{ctrl}` data to the database")
        elif any(k in action_lower for k in ['update', 'edit', 'change', 'modify']):
            points.append(f"Updates existing `{ctrl}` record(s) in the database")
        elif any(k in action_lower for k in ['delete', 'remove', 'destroy']):
            points.append(f"Removes `{ctrl}` record(s) from the database")
        elif any(k in action_lower for k in ['pay', 'payment', 'process']):
            points.append(f"Processes a payment or financial transaction for `{ctrl}`")
        elif any(k in action_lower for k in ['send', 'email', 'notify']):
            points.append(f"Sends an email or notification related to `{ctrl}`")
        elif any(k in action_lower for k in ['export', 'download', 'generate']):
            points.append(f"Generates or exports a report/document for `{ctrl}`")
        else:
            points.append(f"Handles `{action}` operation for `{ctrl}` — review implementation for details")

    return points

def infer_purpose(route, ctrl_name, queries, params):
    """Generate a meaningful 2-3 sentence purpose description."""
    action = route['action'].lower()
    ctrl = ctrl_name.replace('Controller', '')
    method = route['method']
    path = route['full_path']

    # Detect what resource this is about
    resource = ctrl.lower()
    if 'invoice' in path.lower() or 'invoice' in resource:
        resource_noun = 'invoice'
    elif 'agent' in path.lower() or 'agent' in resource:
        resource_noun = 'agent'
    elif 'payment' in path.lower() or 'payment' in resource:
        resource_noun = 'payment'
    elif 'commission' in path.lower() or 'commission' in resource:
        resource_noun = 'commission'
    elif 'group' in path.lower() or 'group' in resource:
        resource_noun = 'group'
    elif 'plan' in path.lower() or 'plan' in resource:
        resource_noun = 'plan'
    elif 'user' in path.lower() or 'user' in resource:
        resource_noun = 'user'
    elif 'policy' in path.lower() or 'policy' in resource:
        resource_noun = 'policy'
    elif 'report' in action or 'report' in resource:
        resource_noun = 'report'
    else:
        resource_noun = resource.lower() or 'resource'

    who_calls = "by authenticated users" if is_auth_required(route) else "by external systems or open clients"

    if any(k in action for k in ['render', 'get', 'fetch', 'list', 'index']):
        return (f"Retrieves {resource_noun} data from the system. "
                f"Called {who_calls} to display or process {resource_noun} information. "
                f"Returns the requested records based on provided filters or identifiers.")
    elif any(k in action for k in ['store', 'create', 'save', 'add']):
        return (f"Creates or saves a new {resource_noun} record. "
                f"Called {who_calls} when submitting new {resource_noun} data. "
                f"Validates the input and persists the new record to the database.")
    elif any(k in action for k in ['update', 'edit', 'change', 'modify']):
        return (f"Updates an existing {resource_noun} record. "
                f"Called {who_calls} when modifying {resource_noun} data. "
                f"Validates the input and applies changes to the specified record.")
    elif any(k in action for k in ['delete', 'remove', 'destroy']):
        return (f"Deletes or removes a {resource_noun} record from the system. "
                f"Called {who_calls} to permanently remove or soft-delete the record. "
                f"May cascade or restrict based on related records.")
    elif any(k in action for k in ['pay', 'payment', 'process']):
        return (f"Processes a payment transaction for a {resource_noun}. "
                f"Called {who_calls} to initiate or record payment. "
                f"Handles payment logic including validation, processing, and status updates.")
    elif any(k in action for k in ['send', 'email', 'notify']):
        return (f"Sends an email or notification related to {resource_noun}. "
                f"Called {who_calls} to trigger communication. "
                f"Composes and dispatches the message using the configured mail service.")
    elif any(k in action for k in ['export', 'download', 'generate', 'pdf']):
        return (f"Generates or exports {resource_noun} data. "
                f"Called {who_calls} to produce a downloadable file or report. "
                f"Compiles the relevant data and returns it in the requested format.")
    elif any(k in action for k in ['approve', 'reject', 'cancel']):
        return (f"Approves, rejects, or cancels a {resource_noun} record. "
                f"Called {who_calls} to change the approval status. "
                f"Updates the status field and may trigger downstream notifications.")
    elif any(k in action for k in ['sync', 'regenerate', 'reprocess']):
        return (f"Synchronizes or regenerates {resource_noun} data. "
                f"Called {who_calls} to bring data into a consistent state. "
                f"Re-runs the relevant calculation or retrieval process.")
    else:
        return (f"Handles the `{route['action']}` operation for {resource_noun}. "
                f"Called {who_calls} as part of the {ctrl} management workflow. "
                f"Returns a JSON response upon completion.")

# ── Per-route analysis ─────────────────────────────────────────────────────────

def analyze_route_deep(route):
    ctrl_file = find_ctrl_file(route['controller'])
    result = {
        'ctrl_file': ctrl_file,
        'body': None,
        'queries': [],
        'params': {},
        'response_schema': {},
        'response_type': 'json',
        'jobs': [],
        'events': [],
        'sends_email': False,
        'auth_required': is_auth_required(route),
    }

    if ctrl_file and os.path.exists(ctrl_file):
        with open(ctrl_file, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        body = extract_method(content, route['action'])
        if body:
            result['body'] = body
            result['queries'] = extract_queries(body)
            result['params'] = extract_request_params(body)
            schema, rtype = extract_response(body, route)
            result['response_schema'] = schema
            result['response_type'] = rtype
            result['jobs'] = re.findall(r'dispatch\(new\s+(\w+)', body)
            result['events'] = re.findall(r'event\(new\s+(\w+)', body)
            result['sends_email'] = bool(re.search(r'Mail::|new\s+\w+Mail\(|EmailHelper', body))
            # Detect external HTTP calls (Guzzle, Http facade, curl)
            ext_m = re.search(
                r'GuzzleHttp|GuzzleClient|Http::(?:get|post|put|patch|delete)|curl_exec|nuera_url|external_url',
                body
            )
            if ext_m:
                # try to extract the target URL config key
                url_m = re.search(r"config\(['\"]([^'\"]+?)['\"]\)", body)
                result['external_api'] = url_m.group(1) if url_m else 'external service'
            else:
                result['external_api'] = None

    return result

# ── Doc generators ─────────────────────────────────────────────────────────────

def get_heading(r):
    segs = r['path'].split('/')
    for seg in reversed(segs):
        if seg and not seg.startswith('{') and not seg.startswith(':'):
            return seg
    return r['action']

def fmt_sql_block(q):
    """Format a query into the legacy_query.sql block."""
    cols_r = ', '.join(q['columns_read']) if q['columns_read'] != ['*'] else '*'
    cols_w = ', '.join(q['columns_written']) if q.get('columns_written') and q['columns_written'] != ['None'] else 'None'
    conds = '\n  '.join(q['conditions']) if q['conditions'] != ['None'] else 'None'
    joins = '\n  '.join(q['joins']) if q['joins'] != ['None'] else 'None'
    op_base = q['operation'].split(' ')[0]
    return f"""| **Type** | {q['type']} |
| **Operation** | {op_base} |
| **Tables** | {q['table']} |
| **Columns Read** | {cols_r[:100]} |
| **Columns Written** | {cols_w[:100]} |
| **Conditions** | {conds[:150]} |
| **Joins** | {joins[:200]} |
| **Order / Group** | {q.get('order_group', 'None')} |
| **Aggregates** | {q.get('aggregates', 'None')} |
| **Transaction** | {'Yes' if q.get('transaction') else 'No'} |
| **Soft Deletes** | {'Yes' if q.get('soft_deletes') else 'No'} |"""

def gen_api_md(domain, routes):
    lines = [f"# API Reference\n\nTotal: **{len(routes)}**\n\n---\n"]
    for r in routes:
        heading = get_heading(r)
        ctrl_short = r['controller'].split('\\')[-1]
        params = r.get('params', [])
        mw = r.get('middleware', [])
        lines.append(f"## {heading}\n")
        lines.append(f"- **Endpoint** : `{r['method']} {r['full_path']}`")
        lines.append(f"- **Controller** : `{ctrl_short}@{r['action']}`")
        if mw:
            lines.append(f"- **Middleware** : {', '.join(str(m) for m in mw)}")
        if params:
            lines.append("- **Params** : " + ", ".join(f"`{p}`" for p in params))
        lines.append("\n---\n")
    return "\n".join(lines)

def gen_business_md(domain, routes_analyzed):
    lines = ["# Business Logic Documentation\n"]
    for r, info in routes_analyzed:
        heading = get_heading(r)
        ctrl_short = r['controller'].split('\\')[-1]
        ctrl_name = ctrl_short.replace('Controller', '')
        auth_str = "Yes" if info['auth_required'] else "No"

        lines.append(f"## {heading}\n")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| **Endpoint** | `{r['method']} {r['full_path']}` |")
        lines.append(f"| **Controller** | `{ctrl_short}@{r['action']}` |")
        lines.append(f"| **Auth Required** | {auth_str} |")
        lines.append(f"| **HTTP Method** | {r['method']} |")
        lines.append("")

        purpose = infer_purpose(r, ctrl_short, info['queries'], info['params'])
        lines.append("### Purpose")
        lines.append(purpose + "\n")

        lines.append("### Business Logic")
        if info['body']:
            points = infer_business_logic(info['body'], r, info['queries'], info['params'])
        else:
            points = [f"UNKNOWN — controller `{info['ctrl_file'] or r['controller']}` not found or method not extractable"]
        for p in points:
            lines.append(f"- {p}")
        lines.append("")

        lines.append("### Input Parameters")
        url_params = r.get('params', [])
        req_params = info.get('params', {})
        if url_params or req_params:
            lines.append("| Parameter | Type | Required | Description |")
            lines.append("|-----------|------|----------|-------------|")
            for p in url_params:
                desc = _param_desc(p)
                lines.append(f"| `{p}` | string | Yes | {desc} (URL path parameter) |")
            for pname, ptype in list(req_params.items())[:10]:
                if pname not in url_params:
                    desc = _param_desc(pname)
                    lines.append(f"| `{pname}` | {ptype} | UNKNOWN | {desc} |")
        else:
            lines.append("No parameters." if r['method'] == 'GET' else "UNKNOWN — review request body.")
        lines.append("")

        lines.append("### Database Operations")
        if info['queries']:
            for i, q in enumerate(info['queries'][:5], 1):
                op_desc = f"**{q['operation'].split(' ')[0]}** `{q['table']}`"
                if q['conditions'] != ['None']:
                    op_desc += f" — WHERE {', '.join(q['conditions'][:2])}"
                if q['joins'] != ['None']:
                    op_desc += f"; with {len(q['joins'])} JOIN(s)"
                lines.append(f"{i}. {op_desc}")
        elif info['body']:
            lines.append("None detected in method body.")
        else:
            lines.append("None")
        lines.append("")

        lines.append("### Side Effects")
        jobs = info.get('jobs', [])
        events = info.get('events', [])
        lines.append(f"- **Emails**: {'Yes — email dispatched' if info.get('sends_email') else 'None'}")
        lines.append(f"- **Jobs/Queues**: {', '.join(f'`{j}`' for j in jobs) if jobs else 'None'}")
        lines.append(f"- **Events**: {', '.join(f'`{e}`' for e in events) if events else 'None'}")
        ext = info.get('external_api')
        lines.append(f"- **External APIs**: {'Yes — proxies to `' + ext + '`' if ext else 'None'}")
        lines.append("- **Files**: None")

        if not info['ctrl_file']:
            lines.append(f"\n> **Warning**: Controller not found: `{r['controller']}`")

        lines.append("\n---\n")
    return "\n".join(lines)

def gen_responses_md(domain, routes_analyzed):
    lines = ["# API Response Schemas\n\nResponse bodies for each endpoint.\n\n---\n"]
    for r, info in routes_analyzed:
        ctrl_short = r['controller'].split('\\')[-1]
        params = r.get('params', [])
        schema = info.get('response_schema', {})
        rtype = info.get('response_type', 'json')

        lines.append(f"## {r['method']} {r['full_path']}\n")
        lines.append(f"**Endpoint**: `{ctrl_short}@{r['action']}`\n")
        if params:
            lines.append("**Path Parameters**:\n")
            for p in params:
                lines.append(f"- `{p}` — {_param_desc(p)} (from URL path)")
            lines.append("")
        lines.append(f"**Response Type**: `{rtype}`\n")
        lines.append("**Response Fields**:\n")
        lines.append("```json")
        if schema:
            import json as _json
            lines.append(_json.dumps(schema, indent=2))
        else:
            lines.append('{ "data": "UNKNOWN" }')
        lines.append("```\n")

        # Build example
        example = {}
        for k, v in (schema or {}).items():
            if 'integer' in str(v):
                example[k] = 1
            elif 'boolean' in str(v):
                example[k] = True
            elif 'decimal' in str(v) or 'float' in str(v):
                example[k] = 100.00
            elif 'datetime' in str(v):
                example[k] = "2025-01-15T00:00:00Z"
            elif 'date' in str(v):
                example[k] = "2025-01-15"
            elif 'email' in str(v):
                example[k] = "user@example.com"
            else:
                example[k] = "example_value"
        lines.append("**Example Response**:\n")
        lines.append("```json")
        lines.append(json.dumps(example, indent=2) if example else '{ "data": "..." }')
        lines.append("```\n")

        # Description
        ctrl_n = ctrl_short.replace('Controller', '').lower()
        rtype_str = {'array_of_objects': 'a list of', 'paginated_array': 'a paginated list of',
                     'json': 'an object containing', 'nested_json': 'a nested object with'}.get(rtype, 'data for')
        lines.append(f"**Description**: Returns {rtype_str} `{ctrl_n}` data. "
                     f"Fields represent the core attributes of the resource as stored in the database.\n")
        lines.append("---\n")
    return "\n".join(lines)

def gen_legacy_sql(domain, routes_analyzed):
    lines = []
    has_q = False
    for r, info in routes_analyzed:
        ctrl_short = r['controller'].split('\\')[-1]
        heading = get_heading(r)
        qs = info.get('queries', [])
        if not qs:
            continue
        has_q = True
        lines.append(f"-- {'─' * 60}")
        lines.append(f"-- Endpoint  : {r['method']} {r['full_path']}")
        lines.append(f"-- Controller: {ctrl_short}@{r['action']}")
        lines.append(f"-- {'─' * 60}\n")
        for i, q in enumerate(qs[:5], 1):
            op_label = q['operation'].split(' ')[0].lower()
            lines.append(f"### {heading} -- Query {i}: {op_label} {q['table']}\n")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            lines.append(fmt_sql_block(q))
            lines.append("")
            lines.append("```sql")
            lines.append(q.get('raw_sql', f"-- {q['operation']} on {q['table']}"))
            lines.append("```\n")
            lines.append("**Optimization Notes:**")
            notes = _optimization_notes(q)
            for note in notes:
                lines.append(f"- {note}")
            lines.append("")
    if not has_q:
        lines.append("-- No database queries detected")
    return "\n".join(lines)

def _optimization_notes(q):
    notes = []
    if q['columns_read'] == ['*']:
        notes.append("Consider using explicit column selection (`SELECT col1, col2`) instead of `SELECT *` to reduce data transfer")
    conds = [c for c in q['conditions'] if c != 'None']
    if not conds:
        notes.append("No WHERE clause detected — ensure this is intentional to avoid full table scans")
    joins = [j for j in q['joins'] if j != 'None']
    if joins:
        notes.append(f"Verify that indexed columns are used in JOIN conditions for {len(joins)} join(s)")
    if 'paginated' not in q['operation'] and q['operation'].startswith('SELECT'):
        notes.append("Add LIMIT clause or pagination if result set could be large")
    if not notes:
        notes.append("No issues identified")
    return notes

def _param_desc(pname):
    """Infer a human-readable description for a parameter name."""
    mapping = {
        'id': 'Unique identifier of the record',
        'val': 'Date or value filter (YYYY-MM format)',
        'day': 'Day value for filtering',
        'date': 'Date filter',
        'month': 'Month filter (YYYY-MM format)',
        'year': 'Year filter',
        'agent_id': 'Unique agent identifier',
        'aid': 'Agent identifier',
        'group_id': 'Unique group identifier',
        'gid': 'Group identifier',
        'policy_id': 'Policy identifier',
        'pid': 'Plan or policy identifier',
        'plan_id': 'Plan identifier',
        'planid': 'Plan identifier',
        'agentid': 'Agent identifier',
        'userid': 'User identifier',
        'user_id': 'User identifier',
        'inv': 'Invoice type filter',
        'pmt': 'Payment type filter',
        'status': 'Status filter (active/inactive/all)',
        'type': 'Type or category filter',
        'level': 'Commission or agent level',
        'tier': 'Pricing tier',
        'token': 'Authentication or verification token',
        'email': 'Email address',
        'invid': 'Invoice identifier',
        'invoiceId': 'Invoice identifier',
        'ptdate': 'Paid-through date (YYYY-MM-DD)',
        'comtype': 'Commission type',
        'filter': 'Filter parameter',
        'method': 'Payment method filter',
        'table': 'Database table name',
        'whereCol': 'Column to use in WHERE condition',
        'tablename': 'Database table name',
        'agcode': 'Agent code',
        'category_id': 'Category identifier',
        'file': 'File name or path',
        'filename': 'File name',
        'id1': 'First identifier parameter',
        'id2': 'Second identifier parameter',
    }
    return mapping.get(pname, f"The `{pname}` value for filtering or referencing the resource")

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import json

    with open(f"{OUTPUT_BASE}/domains.json") as f:
        domains = json.load(f)

    total_routes = 0
    domain_count = 0
    print(f"Re-generating {len(domains)} domains with deep analysis...")

    for domain, routes in sorted(domains.items()):
        domain_dir = f"{DOCS_BACKEND}/{domain}"
        os.makedirs(domain_dir, exist_ok=True)
        domain_count += 1

        # Analyze each route
        routes_analyzed = []
        for r in routes:
            info = analyze_route_deep(r)
            routes_analyzed.append((r, info))
            total_routes += 1

        # Generate api.md (always regenerate)
        with open(f"{domain_dir}/api.md", 'w', encoding='utf-8') as f:
            f.write(gen_api_md(domain, routes))

        # Force regenerate all files with deep analysis
        with open(f"{domain_dir}/business.md", 'w', encoding='utf-8') as f:
            f.write(gen_business_md(domain, routes_analyzed))

        with open(f"{domain_dir}/responses.md", 'w', encoding='utf-8') as f:
            f.write(gen_responses_md(domain, routes_analyzed))

        with open(f"{domain_dir}/legacy_query.sql", 'w', encoding='utf-8') as f:
            f.write(gen_legacy_sql(domain, routes_analyzed))

        if domain_count % 20 == 0:
            print(f"  Progress: {domain_count}/{len(domains)} domains...")

    # Regenerate index
    index_lines = [
        "# Backend API Index\n",
        f"Total routes: {total_routes} | Domains: {domain_count}\n",
        "## Domains\n",
        "| Domain | Routes | Files |",
        "|--------|--------|-------|",
    ]
    for domain, routes in sorted(domains.items()):
        index_lines.append(
            f"| {domain} | {len(routes)} | [api.md](./{domain}/api.md) · [business.md](./{domain}/business.md) · [responses.md](./{domain}/responses.md) · [legacy_query.sql](./{domain}/legacy_query.sql) |"
        )
    with open(f"{DOCS_BACKEND}/index.md", 'w', encoding='utf-8') as f:
        f.write('\n'.join(index_lines))

    print(f"\nDone! {domain_count} domains, {total_routes} routes re-generated with deep analysis.")
    print(f"Output: {OUTPUT_BASE}")

    print(f"\nDone! {domain_count} domains, {total_routes} routes re-generated with deep analysis.")
    print(f"Output: {OUTPUT_BASE}")
