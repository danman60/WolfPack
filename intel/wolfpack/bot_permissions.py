"""Permissions management for WolfPack Bot.

Manages tool permissions (tier1=read, tier2=write) for LLM bot.
"""

# Permission configuration
PERMISSIONS = {
    "tier1": True,  # Read-only operations always enabled
    "tier2": False,  # Write operations disabled by default
}


def check_permission(permission: str) -> bool:
    """Check if a permission is enabled.
    
    Args:
        permission: Permission name (e.g., "approve_trade", "tier2")
    
    Returns:
        True if permission is granted, False otherwise
    """
    # If it's a tier, check tier permission
    if permission in PERMISSIONS:
        return PERMISSIONS[permission]
    
    # For specific tool permissions, map to tier
    tier2_permissions = [
        "approve_trade", "reject_trade", "place_order",
        "cancel_order", "close_position", "set_stop_loss",
        "autobot_start", "autobot_stop", "autobot_configure"
    ]
    
    if permission in tier2_permissions:
        return PERMISSIONS["tier2"]
    
    # Default to tier1 for read operations
    return PERMISSIONS["tier1"]


def enable_tier2() -> None:
    """Enable tier2 permissions (trade execution, AutoBot control)."""
    PERMISSIONS["tier2"] = True


def disable_tier2() -> None:
    """Disable tier2 permissions."""
    PERMISSIONS["tier2"] = False


def get_permissions_status() -> dict:
    """Get current permissions status."""
    return {
        "tier1": PERMISSIONS["tier1"],
        "tier2": PERMISSIONS["tier2"],
    }


def get_permission_tools(tools: list, user_id: str | None = None) -> list:
    """Filter tools list to those accessible given current permission state.

    Args:
        tools: Full list of tool definitions (with 'permission' key)
        user_id: Optional user ID (reserved for per-user permissions in future)

    Returns:
        Filtered list of tools the user is allowed to call
    """
    result = []
    for tool in tools:
        tier = tool.get("permission", "tier1")
        if PERMISSIONS.get(tier, False):
            result.append(tool)
    return result


def get_tool_permission(tool_name: str) -> str:
    """Get permission tier for a tool.
    
    Args:
        tool_name: Name of the tool
    
    Returns:
        Permission tier ("tier1" or "tier2")
    """
    from wolfpack.bot_tools import TOOLS
    for tool in TOOLS:
        if tool["name"] == tool_name:
            return tool.get("permission", "tier2")
    return "tier2"
