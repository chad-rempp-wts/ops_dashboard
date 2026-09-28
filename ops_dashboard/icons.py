"""Fixed icon markup. Keys only; telemetry never supplies SVG."""

from __future__ import annotations

_ATTRS = (
    'viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
)

_INNER = {
    "frontdoor": (
        '<path d="M6 21V5a2 2 0 0 1 2-2h6v18"></path>'
        '<path d="M14 3h2a2 2 0 0 1 2 2v16"></path>'
        '<path d="M9 12h2"></path><path d="M4 21h16"></path>'
    ),
    "appservice": (
        '<rect x="4" y="3" width="16" height="18" rx="2"></rect>'
        '<path d="M4 8h16M9 13h6M9 17h4"></path>'
    ),
    "svelte": (
        '<ellipse cx="12" cy="14.5" rx="5.2" ry="5.4"></ellipse>'
        '<circle cx="12" cy="8" r="3"></circle>'
        '<circle cx="10.8" cy="7.7" r="0.7" fill="currentColor" stroke="none"></circle>'
        '<circle cx="13.2" cy="7.7" r="0.7" fill="currentColor" stroke="none"></circle>'
        '<path d="M11 9.3h2"></path>'
    ),
    "locator": (
        '<path d="M12 21s6.5-5.6 6.5-10a6.5 6.5 0 1 0-13 0c0 4.4 6.5 10 6.5 10z"></path>'
        '<circle cx="12" cy="11" r="2"></circle>'
    ),
    "webjobs": '<path d="M13 2 4 14h7l-1 8 10-14h-7l0-6z"></path>',
    "signalr": (
        '<circle cx="6" cy="12" r="2"></circle><circle cx="18" cy="7" r="2"></circle>'
        '<circle cx="18" cy="17" r="2"></circle>'
        '<path d="M8 12h6M8.4 11.2 15.2 8.2M8.4 12.8 15.2 15.8"></path>'
    ),
    "sql": (
        '<ellipse cx="12" cy="6" rx="7" ry="3"></ellipse>'
        '<path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6"></path>'
        '<path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"></path>'
    ),
    "search": '<circle cx="11" cy="11" r="6"></circle><path d="M16 16l4 4"></path>',
    "plan": (
        '<rect x="4" y="3" width="16" height="5" rx="1"></rect>'
        '<rect x="4" y="10" width="16" height="5" rx="1"></rect>'
        '<rect x="4" y="17" width="16" height="4" rx="1"></rect>'
        '<path d="M7 5.5h2M7 12.5h2M7 19h2"></path>'
    ),
    "gateway": (
        '<path d="M4 20V9l8-5 8 5v11"></path><path d="M9 20v-6h6v6"></path><path d="M12 9v3"></path>'
    ),
    "container": (
        '<path d="M3 8l9-5 9 5v9l-9 5-9-5V8z"></path><path d="M3 8l9 5 9-5M12 13v9"></path>'
    ),
    "tracker": '<path d="M3 12h4l2-5 4 10 2-5h6"></path>',
    "email": (
        '<rect x="3" y="6" width="18" height="12" rx="1.5"></rect><path d="M4 7l8 6 8-6"></path>'
    ),
    "servicebus": (
        '<rect x="3" y="6" width="18" height="4.5" rx="1"></rect>'
        '<rect x="3" y="13.5" width="18" height="4.5" rx="1"></rect>'
        '<path d="M7 8.2h5M7 15.7h5"></path>'
    ),
    "redis": (
        '<path d="M12 3l8 4-8 4-8-4 8-4z"></path>'
        '<path d="M4 7v4.5l8 4 8-4V7"></path>'
        '<path d="M4 12.5V17l8 4 8-4v-4.5"></path>'
    ),
    "generic": '<rect x="5" y="5" width="14" height="14" rx="2"></rect>',
}

_BADGES = {
    "healthy": '<path d="M4.5 12.5 9.5 17.5 19.5 6.5"></path>',
    "degraded": (
        '<path d="M12 3.5 21.5 20.5H2.5Z"></path><path d="M12 10v4"></path>'
        '<circle cx="12" cy="17" r="0.8" fill="currentColor" stroke="none"></circle>'
    ),
    "critical": '<path d="M6 6l12 12M18 6 6 18"></path>',
    "maintenance": '<path d="M12 2.5 21 12 12 21.5 3 12Z"></path>',
    "unknown": (
        '<path d="M9.2 9.2a2.8 2.8 0 1 1 3.6 2.6c-.8.4-1.3 1-1.3 2"></path>'
        '<circle cx="12" cy="17.4" r="0.8" fill="currentColor" stroke="none"></circle>'
    ),
}

LABELS = {
    "healthy": "Healthy",
    "degraded": "Degraded",
    "critical": "Critical",
    "maintenance": "Maintenance",
    "unknown": "Unknown",
}


def icon_svg(key: str, size: int = 22) -> str:
    inner = _INNER.get(key, _INNER["generic"])
    return f'<svg {_ATTRS} width="{size}" height="{size}">{inner}</svg>'


def badge_svg(state: str) -> str:
    inner = _BADGES.get(state, _BADGES["unknown"])
    return f'<svg {_ATTRS} width="14" height="14">{inner}</svg>'
