from . import permission_filter, prohibition, structured_output, tenant_boundary, tool_boundary, workflow_agent

PATTERNS = {"structured-output": structured_output, "permission-filter": permission_filter, "tool-boundary": tool_boundary,
            "prohibition": prohibition, "tenant-boundary": tenant_boundary, "workflow-agent": workflow_agent}
