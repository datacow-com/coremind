"""
Channel-aware storage utilities.

Provides functions to generate channel-prefixed collection/index names
for multi-tenant data isolation.
"""


def channel_collection_name(channel_id: str | None, kb_name: str, version: int = 1) -> str:
    """
    Generate a Qdrant collection name with channel isolation.

    Format: ch_{channel_id}_kb_{kb_name}_v{version}
    If no channel_id, falls back to: kb_{kb_name}_v{version}

    Args:
        channel_id: Optional channel identifier
        kb_name: Knowledge base name
        version: KB version number

    Returns:
        Channel-isolated collection name
    """
    if channel_id:
        return f"ch_{channel_id}_kb_{kb_name}_v{version}"
    return f"kb_{kb_name}_v{version}"


def channel_index_name(channel_id: str | None, kb_name: str) -> str:
    """
    Generate an Elasticsearch index name with channel isolation.

    Format: ch_{channel_id}_kb_{kb_name}_docs
    If no channel_id, falls back to: kb_{kb_name}_docs

    Args:
        channel_id: Optional channel identifier
        kb_name: Knowledge base name

    Returns:
        Channel-isolated index name
    """
    if channel_id:
        return f"ch_{channel_id}_kb_{kb_name}_docs"
    return f"kb_{kb_name}_docs"


def channel_blob_prefix(channel_id: str | None, kb_name: str) -> str:
    """
    Generate a blob storage path prefix with channel isolation.

    Format: channels/{channel_id}/kb/{kb_name}/
    If no channel_id, falls back to: kb/{kb_name}/

    Args:
        channel_id: Optional channel identifier
        kb_name: Knowledge base name

    Returns:
        Channel-isolated blob path prefix
    """
    if channel_id:
        return f"channels/{channel_id}/kb/{kb_name}/"
    return f"kb/{kb_name}/"


def parse_channel_from_collection(collection_name: str) -> tuple[str | None, str, int]:
    """
    Parse channel_id, kb_name, and version from collection name.

    Args:
        collection_name: The collection name to parse

    Returns:
        Tuple of (channel_id, kb_name, version)
    """
    import re

    # Pattern: ch_{channel_id}_kb_{kb_name}_v{version}
    channel_pattern = r"^ch_([^_]+)_kb_(.+)_v(\d+)$"
    # Pattern: kb_{kb_name}_v{version}
    legacy_pattern = r"^kb_(.+)_v(\d+)$"

    match = re.match(channel_pattern, collection_name)
    if match:
        return match.group(1), match.group(2), int(match.group(3))

    match = re.match(legacy_pattern, collection_name)
    if match:
        return None, match.group(1), int(match.group(2))

    # Fallback
    return None, collection_name, 1


def validate_channel_access(
    channel_id: str | None, collection_name: str, strict: bool = True
) -> bool:
    """
    Validate that a collection belongs to the specified channel.

    Args:
        channel_id: The channel attempting access
        collection_name: The collection being accessed
        strict: If True, raise error on mismatch; if False, return bool

    Returns:
        True if access is valid

    Raises:
        PermissionError: If strict=True and channel mismatch
    """
    parsed_channel, _, _ = parse_channel_from_collection(collection_name)

    # If collection has no channel (legacy), allow access
    if parsed_channel is None:
        return True

    # If request has no channel but collection does, deny
    if channel_id is None and parsed_channel is not None:
        if strict:
            raise PermissionError(f"Channel required to access {collection_name}")
        return False

    # Channel mismatch
    if channel_id != parsed_channel:
        if strict:
            raise PermissionError(
                f"Channel {channel_id} cannot access collection of channel {parsed_channel}"
            )
        return False

    return True
