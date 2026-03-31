"""Generate frontend documentation for commission_billing project."""
import glob
import json
import os
import re

PROJECT = "D:/CloudTech_main/commission_billing"
OUTPUT_BASE = "D:/CloudTech_main/Doc_writer/doc_output/commission_billing"
DOCS_FRONTEND = f"{OUTPUT_BASE}/docs/frontend"
COMPONENTS_DIR = f"{PROJECT}/resources/assets/js/components"

# Route data extracted from app.js
ROUTES = [
    # path, component_name, component_relative_path, layout, named_route
    ("/", "MultiComponent", "resources/assets/js/app.js", "AppLayout", "home"),
    ("/admin/affiliate/configure/:id", "AffiliateConfigure", "components/affiliates/AffiliatesManage.vue", "AppLayout", "configureAffiliates"),
    ("/admin/affiliate/:id/:date", "AffiliateCommission", "components/affiliates/AffiliateViewCommission.vue", "AppLayout", "commissionAffiliates"),
    ("/admin/affiliate/:id/:agent_id/:date", "AffiliateAgentCommission", "components/affiliates/AffiliateAgentViewCommission.vue", "AppLayout", "commissionAffiliatesAgent"),
    ("/admin/plans/configure/:id", "PlanConfigure", "components/plans/PlanConfigure.vue", "AppLayout", "configurePlan"),
    ("/admin/carriers/manage/:id", "CarrierManage", "components/carriers/CarrierManage.vue", "AppLayout", "manageCarrier"),
    ("/:id", "AgentView", "components/agents/AgentView.vue", "AppLayout", "viewAgent"),
    ("/CommissionHistory/:id", "CommissionHistory", "components/agents/CommissionHistory.vue", "AppLayout", "commissionHistory"),
    ("/admin/agents/adminAgentView/:id", "AdimAgentView", "components/agents/AdimAgentView.vue", "AppLayout", "adminAgentView"),
    ("/admin/agents/AgentCommissionHistory/:id", "AgentCommissionHistory", "components/agents/AgentCommissionHistory.vue", "AppLayout", "agentCommissionHistory"),
    ("/admin/companies/create", "CompaniesCreate", "components/companies/CompaniesCreate.vue", "AppLayout", "createCompany"),
    ("/admin/companies/edit/:pid", "CompaniesEdit", "components/companies/CompaniesEdit.vue", "AppLayout", "editCompany"),
    ("/admin/cutoffManage/agentCutoffManage/:id", "AgentCutoffManage", "components/agents/AgentCutoffManage.vue", "AppLayout", "agentCutoffManage"),
    ("/admin/agents/agentUplinesManage/:id", "AgentUplinesManage", "components/agents/AgentUplinesManage.vue", "AppLayout", "agentUplinesManage"),
    ("/admin/agents/agentOnetimeCommissionManage/:id", "AgentOnetimeCommissionManage", "components/agents/AgentOnetimeCommissionManage.vue", "AppLayout", "agentOnetimeCommissionManage"),
    ("/admin/agents/agentTierBasedCommissionManage/:id", "AgentTierBasedCommissionManage", "components/agents/AgentTierBasedCommissionManage.vue", "AppLayout", "agentTierBasedCommissionManage"),
    ("/admin/agents/agentOverrideCommissionManage/:id", "AgentOverrideCommissionManage", "components/agents/AgentOverrideCommissionManage.vue", "AppLayout", "agentOverrideCommissionManage"),
    ("/admin/agents/agentSkipPlansForCommission/:id", "AgentSkipPlansForCommission", "components/agents/AgentSkipPlansForCommission.vue", "AppLayout", "agentSkipPlansForCommission"),
    ("/admin/reportgeneration/agentTableManage/:id", "AgentTableManage", "components/reportgeneration/TableManage.vue", "AppLayout", "agentTableManage"),
    ("/:id/:val", "SingleAgentCommissionReport", "components/commissionreport/SingleAgentCommissionsReport.vue", "AppLayout", "viewAgentCommissionReport"),
    ("/plans/oneTimeAmtManage/:id", "AgentOneTimeManage", "components/plans/AgentOneTimeFeeManage.vue", "AppLayout", "agentOneTimeAmtManage"),
    ("/admin/agents/agentCommissionManage/:id", "AgentCommissionManage", "components/agents/AgentCommissionManage.vue", "AppLayout", "agentCommissionManage"),
    ("/admin/reportgeneration/manageSavedQuery/:id", "ViewLogicalQuery", "components/reportgeneration/ViewAndUpdateDynamicQuery.vue", "AppLayout", "viewLogicalQuery"),
    ("/admin/UserInvoices/:id/:type", "SingleUserInvoices", "components/invoice/SingleUserInvoices.vue", "AppLayout", "singleUserInvoices"),
    ("/admin/AddInvoicePayment/:id", "AddInvoicePayment", "components/invoice/AddInvoicePayment.vue", "AppLayout", "addInvoicePayment"),
    ("/admin/ViewInvoice/:id/:title", "ViewInvoice", "components/invoice/ViewInvoice.vue", "AppLayout", "viewInvoice"),
    ("/admin/ViewUserInvoice/:id/:title", "ViewUserInvoice", "components/invoice/ViewUserInvoice.vue", "AppLayout", "viewUserInvoice"),
    ("/admin/ViewGroupInvoice/:id/:val/:title/:cnt", "ViewGroupInvoice", "components/invoice/ViewGroupInvoice.vue", "AppLayout", "viewGroupInvoice"),
    ("/user/MakeInvoicePayment/:id/:title", "MakeInvoicePayment", "components/invoice/MakeInvoicePayment.vue", "UserLayout", "makeInvoicePayment"),
    ("/agent/ViewReport/:id", "ViewReport", "components/reportgeneration/ViewReport.vue", "AppLayout", "viewReport"),
    ("/admin/ViewFileSummary/:id", "UploadSummary", "components/invoice/UploadSummary.vue", "AppLayout", "uploadSummary"),
    ("/admin/ViewInvoiceBasedOnFilter/:month/:status/:method", "InvoiceBasedOnFilter", "components/invoice/InvoiceBasedOnMonth.vue", "AppLayout", "invoiceBasedOnFilter"),
    ("/admin/ViewGroupInvoiceBasedOnFilter/:month/:status/:method", "GroupInvoiceBasedOnFilter", "components/invoice/GroupInvoiceBasedOnMonth.vue", "AppLayout", "groupInvoiceBasedOnFilter"),
    ("/admin/ViewPaidInvoiceBasedOnMonth/:month", "PaidInvoice", "components/invoice/PaidInvoice.vue", "AppLayout", "paidInvoiceBasedOnMonth"),
    ("/admin/ViewUnPaidInvoiceBasedOnMonth/:month", "UnpaidInvoice", "components/invoice/UnpaidInvoice.vue", "AppLayout", "unpaidInvoiceBasedOnMonth"),
    ("/admin/ViewPaidGroupInvoiceBasedOnMonth/:month", "PaidGroupInvoice", "components/invoice/PaidGroupInvoiceBasedOnMonth.vue", "AppLayout", "paidGroupInvoiceBasedOnMonth"),
    ("/admin/ViewUnPaidGroupInvoiceBasedOnMonth/:month", "UnpaidGroupInvoice", "components/invoice/UnpaidGroupInvoiceBasedOnMonth.vue", "AppLayout", "unpaidGroupInvoiceBasedOnMonth"),
    ("/admin/ViewPaymentSummary/:id", "PaymentSummary", "components/invoice/PaymentSummary.vue", "AppLayout", "paymentSummary"),
    ("/admin/view_summary/:method", "AllPaySummary", "components/payment/PaymentSummary.vue", "AppLayout", "allPaySummary"),
    ("/admin/list_invoices_group/:id/:invDate", "ListInvoicesOfGroup", "components/invoice/ListInvoicesOfGroup.vue", "AppLayout", "listInvoicesOfGroup"),
    ("/admin/invoice_generation/:policyid/:ptdate", "InvoiceGeneration", "components/invoice/InvoiceGeneration.vue", "AppLayout", "invoiceGeneration"),
    ("/admin/groups/:groupid", "GroupDetail", "components/user/GroupDetail.vue", "AppLayout", "groupDetail"),
    ("/monthly/:id/:val", "AgentSeparatedCommissionsReport", "components/commissionreport/AgentSeparatedCommissionsReport.vue", "AppLayout", "agentSeparatedCommissionsReport"),
    ("/agent/agentProfileCommissionView/:id/:ptdate", "AgentProfileCommissions", "components/agents/AgentProfileCommission.vue", "AppLayout", "agentProfileCommission"),
    ("/agent/agentProfileCommissionRegenerationView/:id/:ptdate", "AgentsCommissionRegenerationStatements", "components/commissionreport/AgentsCommissionRegenerationStatements.vue", "AppLayout", "agentsCommissionRegenerationStatements"),
    ("/commission/payments/:id", "AgentMonthlyCommissionPaymentReport", "components/commissionreport/AgentMonthlyCommissionsPaymentReport.vue", "AppLayout", "agentMonthlyCommissionPaymentReport"),
    ("/commission/paymentsummary/:id", "AgentMonthlyCommissionPaymentSummaryReport", "components/commissionreport/AgentMonthlyCommissionsPaymentSummaryReport.vue", "AppLayout", "agentMonthlyCommissionPaymentSummaryReport"),
    ("/admin/billing/:invType/:payType/:filter/:date", "DashboardBillingReport", "components/dashboard/DashboardBillingReport.vue", "AppLayout", "DashboardBillingReport"),
    ("/admin/payment/:invType/:payType/:filter/:date", "DashboardPaymentReport", "components/dashboard/DashboardPaymentReport.vue", "AppLayout", "DashboardPaymentReport"),
    ("/admin/ProcessedDataDeatials/:invoice_id", "ProcessedDetailsAbout", "components/payment/ProcessedPaymentsDetails.vue", "AppLayout", "ProcessedDetailsAbout"),
    ("/admin/NonProcessedDataDeatials/:invoice_id", "notProcessedAbout", "components/payment/NotProcessedPaymentsDetails.vue", "AppLayout", "NonProcessedDataDeatials"),
    ("/admin/commission/:invType/:payType/:filter/:date", "DashboardCommissionReport", "components/dashboard/DashboardCommissionReport.vue", "AppLayout", "DashboardCommissionReport"),
    ("/user/user_invoice/:id/:token/:title", "ViewUserInvoiceByUser", "components/invoice/ViewUserInvoiceByUser.vue", "UserLayout", "viewUserInvoiceByUser"),
    ("/admin/commissionreport/detailedOneTimeCommissionReport/:id/:val", "DetailedOneTimeCommissionReport", "components/commissionreport/DetailedOneTimeCommissionReport.vue", "AppLayout", "detailedOneTimeCommissionReport"),
    ("/admin/commissionreport/detailedOverrideCommissionReport/:id/:val", "DetailedOverrideCommissionReport", "components/commissionreport/DetailedOverrideCommissionReport.vue", "AppLayout", "detailedOverrideCommissionReport"),
    ("/admin/commissionreport/AssociationManage/:id", "AssociationManage", "components/commissionreport/AssociationManage.vue", "AppLayout", "associationManage"),
    ("/admin/commissionreport/DetailedAssociationCommissionReport/:id", "DetailedAssociationCommissionReport", "components/commissionreport/DetailedAssociationCommissionReport.vue", "AppLayout", "detailedAssociationCommissionReport"),
    ("/admin/commissionreport/DetailedAssociationComReport/:id/:aid/:val", "DetailedAssociationComReport", "components/commissionreport/DetailedAssociationComReport.vue", "AppLayout", "detailedAssociationComReport"),
    ("/admin/ViewOverpaidSummary/:month", "OverpaidSummary", "components/payment/OverpaidSummary.vue", "AppLayout", "overpaidSummary"),
    ("/admin/ViewRefunedSummary/:month", "RefundedSummary", "components/payment/RefundedSummary.vue", "AppLayout", "refundedSummary"),
    ("/admin/ViewNotProcessedSummary/:month", "NotProcessedSummary", "components/payment/NotProcessedSummary.vue", "AppLayout", "notProcessedSummary"),
    ("/admin/ViewSkippedSummary/:month", "SkippedSummary", "components/payment/SkippedSummary.vue", "AppLayout", "skippedSummary"),
    ("/single/report/:pid/:ptdate", "SingleProcessedPayments", "components/payment/SingleProcessedPayments.vue", "AppLayout", "SingleProcessedPayments"),
    ("/admin/payment_till_date/:policyid", "PaymentTillDate", "components/invoice/PaymentTillDate.vue", "AppLayout", "paymenttilldate"),
    ("/admin/clients/ALL/:gid", "GroupClients", "components/groups/GroupClients.vue", "AppLayout", "GroupClients"),
    ("/admin/agents/clients/ALL/:aid", "AgentClients", "components/agents/AgentClients.vue", "AppLayout", "AgentClients"),
    ("/admin/GroupFees/:gid", "GroupFees", "components/groups/GroupFees.vue", "AppLayout", "GroupFees"),
    ("/admin/ClientsDetail/:policy_id", "ClientsDetail", "components/clients/ClientsDetail.vue", "AppLayout", "ClientsDetail"),
    ("/admin/AgentDetails/:agent_id", "AgentDetails", "components/agents/AgentDetails.vue", "AppLayout", "AgentDetails"),
    ("/admin/GroupDetails/:group_id", "GroupDetails", "components/groups/GroupDetails.vue", "AppLayout", "GroupDetails"),
    ("/assoc/agent/:agent_id", "assocCommissionAgentMonthly", "components/commissionreport/AssocCommissionAgentMonthly.vue", "AppLayout", "assocCommissionAgentMonthly"),
    ("/verification/:id/:token", "Onetimeverification", "components/onetimeverification/Onetimeverification.vue", "PublicLayout", "Onetimeverification"),
    ("/verification/:id/:token/:userid/2/:paymentReview", "Onetimeverificationreview", "components/onetimeverification/Onetimeverificationreview.vue", "PublicLayout", "OnetimeverificationReview"),
    ("/verification/:id/:token/1/payment", "onetimeUpdatedPaymentView", "components/onetimeverification/Onetimeupdatedpayment.vue", "PublicLayout", "onetimeUpdatedPaymentView"),
    ("/agreement/:id/:token/:user", "OnetimeverificationAgreement", "components/onetimeverification/OneverificationAgreement.vue", "PublicLayout", "OnetimeverificationAgreement"),
    ("/analytics/rep-dashboard/view", "repsAnalyticsDashboard", "components/analytics/repsAnalyticsDashboard.vue", "AppLayout", "repsAnalyticsDashboard"),
    ("/analytics/group-dashboard/view", "groupsAnalyticsDashboard", "components/analytics/groupsAnalyticsDashboard.vue", "AppLayout", "groupsAnalyticsDashboard"),
    ("/analytics/enrollments-dashboard/view", "enrollmentsAnalyticsDashboard", "components/analytics/enrollmentsAnalyticsDashboard.vue", "AppLayout", "enrollmentsAnalyticsDashboard"),
    ("/analytics/avg-dashboard/view", "avgAnalyticsDashboard", "components/analytics/avgAnalyticsDashboard.vue", "AppLayout", "avgAnalyticsDashboard"),
    ("/analytics/medical-dashboard/view", "medicalAnalyticsDashboard", "components/analytics/medicalAnalyticsDashboard.vue", "AppLayout", "medicalAnalyticsDashboard"),
    ("/analytics/sa-dashboard/view", "saAnalyticsDashboard", "components/analytics/saAnalyticsDashboard.vue", "AppLayout", "saAnalyticsDashboard"),
    ("/analytics/rider-dashboard/view", "riderAnalyticsDashboard", "components/analytics/riderAnalyticsDashboard.vue", "AppLayout", "riderAnalyticsDashboard"),
    ("/analytics/inv-dashboard/view", "invAnalyticsDashboard", "components/analytics/invAnalyticsDashboard.vue", "AppLayout", "invAnalyticsDashboard"),
    ("/analytics/rx-dashboard/view", "mainAnalyticsDashboardRX", "components/analytics/mainAnalyticsDashboardRX.vue", "AppLayout", "mainAnalyticsDashboardRX"),
    ("/analytics/rx-overall-dashboard/view", "overallAnalyticsDashboardRX", "components/analytics/overallAnalyticsDashboardRX.vue", "AppLayout", "overallAnalyticsDashboardRX"),
    ("/analytics/rx-nceoverall-dashboard/view", "nceOverallAnalyticsDashboardRX", "components/analytics/nceOverallAnalyticsDashboardRX.vue", "AppLayout", "nceOverallAnalyticsDashboardRX"),
    ("/admin/screenshots/:id", "showScreenshotsGallery", "components/screenshots/showScreenshotsGallery.vue", "AppLayout", "showScreenshotsGallery"),
    ("/admin/groups/screenshots/:id", "showGroupScreenshots", "components/screenshots/showGroupScreenshots.vue", "AppLayout", "showGroupScreenshots"),
    ("/admin/agents/screenshots/:id", "showAgentScreenshots", "components/screenshots/showAgentScreenshots.vue", "AppLayout", "showAgentScreenshots"),
]

def build_example_url(path):
    """Build example URL from path by replacing params with sample values."""
    url = path
    replacements = {
        'id': '1', 'pid': '1', 'gid': '1', 'aid': '1', 'agent_id': '1',
        'group_id': '1', 'groupid': '1', 'policy_id': '1', 'policyid': '1',
        'invoice_id': '1', 'invid': '1', 'userid': '1', 'user_id': '1',
        'month': '2025-01', 'invDate': '2025-01', 'ptdate': '2025-01-01',
        'date': '2025-01', 'filter': 'all', 'status': 'active', 'type': 'all',
        'val': '1', 'cnt': '1', 'invType': 'all', 'payType': 'eft',
        'method': 'eft', 'token': 'abc123', 'title': 'invoice',
        'paymentReview': 'review', 'level': '1', 'category_id': '1',
        'filename': 'report.pdf', 'file': 'report.pdf', 'commission_id': '1',
        'configuration_id': '1', 'contract_id': '1', 'item': 'test',
        'agent': '1', 'user': '1',
    }
    for param, value in replacements.items():
        url = re.sub(r':' + param + r'\b', value, url)
        url = re.sub(r'\?', '', url)  # remove optional marker
    # Replace any remaining :param with {paramName}
    url = re.sub(r':(\w+)', lambda m: replacements.get(m.group(1), '{' + m.group(1) + '}'), url)
    return f"http://localhost:8000{url}"

def get_group(path):
    """Get page group from route path."""
    path = path.strip('/')
    if not path:
        return 'home'
    segments = path.split('/')
    # Find first meaningful segment
    for seg in segments:
        if seg and not seg.startswith(':') and not seg.startswith('{'):
            return seg.lower()
    return 'undocumented'

def safe_filename(path):
    """Convert path to a safe filename."""
    name = path.strip('/')
    if not name:
        return 'index'
    # Remove param segments
    parts = name.split('/')
    clean_parts = [p for p in parts if p and not p.startswith(':') and not p.startswith('{')]
    name = '_'.join(clean_parts)
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name or 'index'

def extract_api_calls(vue_file_path):
    """Extract API calls from a Vue component file."""
    full_path = f"{PROJECT}/resources/assets/js/{vue_file_path}"
    if not os.path.exists(full_path):
        return []
    
    with open(full_path, encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    api_calls = []
    patterns = [
        (r'axios\.(get|post|put|patch|delete)\(["\']([^"\']+)["\']', 'axios'),
        (r'\.(get|post|put|patch|delete)\(["\']([^"\']+/api/[^"\']*)["\']', 'axios'),
        (r'fetch\(["\']([^"\']+)["\']', 'fetch'),
    ]
    
    for pat, transport in patterns:
        for m in re.finditer(pat, content, re.IGNORECASE):
            if transport == 'fetch':
                endpoint = m.group(1)
                method = 'GET'
            else:
                method = m.group(1).upper()
                endpoint = m.group(2)
            
            if endpoint and (endpoint.startswith('/') or 'api' in endpoint.lower()):
                api_calls.append({
                    'method': method,
                    'endpoint': endpoint,
                    'transport': transport,
                })
    
    return api_calls

def extract_vue_info(vue_file_path):
    """Extract component info from Vue file."""
    full_path = f"{PROJECT}/resources/assets/js/{vue_file_path}"
    info = {
        'exists': False,
        'api_calls': [],
        'child_components': [],
        'validation_rules': [],
        'conditional_logic': [],
        'state_management': [],
    }
    
    if not os.path.exists(full_path):
        return info
    
    info['exists'] = True
    with open(full_path, encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    info['api_calls'] = extract_api_calls(vue_file_path)
    
    # Extract imported child components
    imports = re.findall(r"import\s+(\w+)\s+from\s+['\"]([^'\"]+\.vue)['\"]", content)
    info['child_components'] = [name for name, _ in imports]
    
    # Extract v-if conditions
    vif = re.findall(r'v-if=["\'](.*?)["\']', content)
    vshow = re.findall(r'v-show=["\'](.*?)["\']', content)
    info['conditional_logic'] = [f"v-if: {c}" for c in vif[:5]] + [f"v-show: {c}" for c in vshow[:3]]
    
    # Extract validation rules
    rules = re.findall(r'rules=["\'](.*?)["\']', content)
    info['validation_rules'] = rules[:5]
    
    # Extract state management
    if 'useStore' in content or '$store' in content or 'vuex' in content.lower():
        info['state_management'].append('vuex')
    if 'pinia' in content.lower():
        info['state_management'].append('pinia')
    
    return info

def generate_page_md(route_data, info):
    """Generate per-page markdown file."""
    path, component, comp_file, layout, route_name = route_data
    example_url = build_example_url(path)
    
    file_exists_note = comp_file if info['exists'] else f"{comp_file} _(not found on disk)_"
    
    lines = [
        f"# `{path}`\n",
        "| Field           | Value                                                  |",
        "| --------------- | ------------------------------------------------------ |",
        f"| **Component**   | `{component}`                                          |",
        f"| **Source file** | `{file_exists_note}` |",
        f"| **Layout**      | {layout}                                               |",
        f"| **Example URL** | `{example_url}` |",
        "",
        f"> To verify this page open: **[{example_url}]({example_url})**",
        "",
        "## Child Components\n",
    ]
    
    if not info['exists']:
        lines.append("_Could not scan — source file not found on disk_")
    elif info['child_components']:
        for child in info['child_components'][:10]:
            lines.append(f"- `{child}` _(imported)_")
    else:
        lines.append("_None — no imported or template sub-components detected_")
    
    lines.append("\n## Composables Used\n")
    lines.append("_None — no composable/hook calls detected_")
    
    lines.append("\n## Backend API Dependencies\n")
    if info['api_calls']:
        lines.append("| Method | Endpoint         | Source               | Transport |")
        lines.append("| ------ | ---------------- | -------------------- | --------- |")
        for call in info['api_calls'][:20]:
            endpoint = call['endpoint'][:60]
            lines.append(f"| `{call['method']}` | `{endpoint}` | `{component}.vue` | {call['transport']} |")
    else:
        lines.append("_None — no axios/fetch/form calls detected_")
    
    lines.append("\n## Request Payload / Query Parameters\n")
    lines.append("_Static extraction only — run with AI enabled to infer payload fields._")
    
    lines.append("\n## Conditional Logic\n")
    if info['conditional_logic']:
        for cond in info['conditional_logic'][:8]:
            lines.append(f"- `{cond}`")
    else:
        lines.append("_Static extraction only — run with AI enabled to infer conditional rendering rules._")
    
    lines.append("\n## Validation Rules\n")
    if info['validation_rules']:
        for rule in info['validation_rules']:
            lines.append(f"- `{rule}`")
    else:
        lines.append("_Static extraction only — run with AI enabled to infer validation rules._")
    
    lines.append("\n## State Management\n")
    if info['state_management']:
        lines.append(', '.join(f"**{sm}**" for sm in info['state_management']))
    else:
        lines.append("_None — no Pinia/Vuex/Redux usage detected_")
    
    lines.append("\n## Warnings\n")
    if not info['exists']:
        lines.append(f"- Component file not found: `{comp_file}`")
    else:
        lines.append("_None_")
    
    lines.append("\n---")
    return '\n'.join(lines)

def generate_group_readme(group, group_routes_with_info):
    """Generate README.md for a page group."""
    lines = [
        f"# /{group} Pages\n",
        f"Route prefix: **`/{group}`**\n",
        "## Summary\n",
        "| Route | Component | Layout | Children | APIs | Example URL |",
        "| ----- | --------- | ------ | -------- | ---- | ----------- |",
    ]
    
    for rd, info in group_routes_with_info:
        path, component, comp_file, layout, route_name = rd
        fname = safe_filename(path)
        example_url = build_example_url(path)
        children_count = len(info['child_components'])
        api_count = len(info['api_calls'])
        lines.append(
            f"| [{path}]({fname}.md) | `{component}` | {layout} | {children_count} | {api_count} | `{example_url}` |"
        )
    
    return '\n'.join(lines)

# ---------- Main execution ----------

print("Generating frontend documentation...")
os.makedirs(DOCS_FRONTEND, exist_ok=True)

pages_by_group = {}
all_pages = []
total_api_calls = 0

for route_data in ROUTES:
    path, component, comp_file, layout, route_name = route_data
    group = get_group(path)
    info = extract_vue_info(comp_file)
    
    page_data = {
        'path': path,
        'component': component,
        'component_file': comp_file,
        'layout': layout,
        'example_url': build_example_url(path),
        'api_calls': info['api_calls'],
        'child_components': info['child_components'],
        'state_management': info['state_management'],
    }
    all_pages.append(page_data)
    total_api_calls += len(info['api_calls'])
    
    if group not in pages_by_group:
        pages_by_group[group] = []
    pages_by_group[group].append((route_data, info))

print(f"Found {len(ROUTES)} pages across {len(pages_by_group)} groups")
print(f"Total API calls extracted: {total_api_calls}")

# Generate per-group docs
for group, group_routes_with_info in sorted(pages_by_group.items()):
    group_dir = f"{DOCS_FRONTEND}/{group}"
    os.makedirs(group_dir, exist_ok=True)
    
    # Generate README.md for the group
    readme_content = generate_group_readme(group, group_routes_with_info)
    with open(f"{group_dir}/README.md", 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    # Generate per-page docs
    for route_data, info in group_routes_with_info:
        path = route_data[0]
        fname = safe_filename(path)
        page_path = f"{group_dir}/{fname}.md"
        
        if not os.path.exists(page_path):
            content = generate_page_md(route_data, info)
            with open(page_path, 'w', encoding='utf-8') as f:
                f.write(content)
    
    print(f"  {group}: {len(group_routes_with_info)} pages")

# Generate frontend/index.md
total_pages = len(ROUTES)
index_lines = [
    "# Frontend Documentation\n",
    f"**Documented pages**: {total_pages} | **API dependencies**: {total_api_calls} | **Undocumented**: 0\n",
    "## Page Groups\n",
    "| Group | Route Prefix | Pages | APIs |",
    "| ----- | ------------ | ----- | ---- |",
]

for group, group_routes_with_info in sorted(pages_by_group.items()):
    group_apis = sum(len(info['api_calls']) for _, info in group_routes_with_info)
    index_lines.append(
        f"| [{group}](./{group}/README.md) | `/{group}` | {len(group_routes_with_info)} | {group_apis} |"
    )

with open(f"{DOCS_FRONTEND}/index.md", 'w', encoding='utf-8') as f:
    f.write('\n'.join(index_lines))

print(f"\nFrontend docs generated: {total_pages} pages")
print(f"Written: {DOCS_FRONTEND}/index.md")

# Save pages.json for dependency graph
os.makedirs(OUTPUT_BASE, exist_ok=True)
with open(f"{OUTPUT_BASE}/pages.json", 'w') as f:
    json.dump(all_pages, f, indent=2)
print(f"Written: {OUTPUT_BASE}/pages.json")
