"""
Tests for the executor's registry dispatch.

These lock in the refactor: they verify the tool registry is complete, that
unknown tools are handled gracefully, and that every tool the planner can mark
sensitive is actually executable. They do NOT invoke real controllers.

Run:  pytest backend/tests/test_executor_dispatch.py -v   (from project root)
  or: pytest tests/test_executor_dispatch.py -v           (from backend/ folder)
"""

import asyncio

from automation import executor
from ai.planner import SENSITIVE_TOOLS


# Canonical set of tools the executor must support (excludes the dead duplicate
# clipboard_history branch that previously existed in the if/elif chain).
EXPECTED_TOOLS = {
    "open_application", "open_project", "open_file",
    "open_browser", "navigate", "search_web", "search_youtube",
    "browser_goto", "browser_click", "browser_click_link", "browser_click_button",
    "browser_type", "browser_search", "browser_fill_form", "browser_submit",
    "browser_read_page", "browser_get_title", "browser_get_links", "browser_screenshot",
    "browser_scroll_down", "browser_scroll_up", "browser_back", "browser_refresh",
    "browser_new_tab", "browser_close_tab", "browser_list_tabs", "browser_close",
    "wait", "wait_for_server", "run_terminal", "open_setting", "compose_email",
    "type_text", "press_key", "click_element",
    "right_click", "double_click", "move_mouse", "scroll", "drag_drop",
    "get_mouse_position", "smart_click", "smart_right_click", "smart_double_click",
    "create_file", "write_to_file", "create_project",
    "read_screen", "analyze_screen", "fill_form", "set_profile", "get_profile",
    "send_whatsapp", "open_whatsapp", "generate_code", "system_info", "kill_process",
    "snap_window", "close_window", "close_all_windows", "switch_window",
    "minimize_all", "list_windows",
    "copy_screen", "get_clipboard", "clipboard_history", "summarize_clipboard",
    "take_screenshot", "open_recent_files", "start_timer", "get_timers",
    "speak", "answer_question",
    "set_brightness", "brightness_up", "brightness_down",
    "volume_up", "volume_down", "mute", "set_volume", "smart_reply",
    "copy_file", "copy_files_by_type", "move_file", "move_files_by_type",
    "rename_file", "delete_file", "delete_by_pattern", "create_folder",
    "create_folder_structure", "zip_folder", "unzip_file", "list_large_files",
    "find_duplicates", "cleanup_desktop",
    "clear_recycle_bin", "check_updates", "show_installed_programs",
    "open_disk_cleanup", "open_device_manager", "check_network_speed", "flush_dns",
    "show_env_variables", "open_services", "check_ports", "get_startup_programs",
    "get_disk_usage", "get_wifi_info", "shutdown", "cancel_shutdown", "restart",
    "start_meeting", "stop_meeting",
    "clipboard_query", "paste_clip",
    "start_focus", "stop_focus", "focus_status",
}


def test_registry_matches_expected_tools():
    assert set(executor.HANDLERS.keys()) == EXPECTED_TOOLS


def test_every_handler_is_callable():
    for tool, handler in executor.HANDLERS.items():
        assert callable(handler), f"handler for {tool} is not callable"


def test_unknown_tool_returns_message():
    result = asyncio.run(executor.execute_task({"tool": "does_not_exist"}))
    assert result == "Unknown tool: does_not_exist"


def test_empty_task_returns_unknown():
    result = asyncio.run(executor.execute_task({}))
    assert result == "Unknown tool: "


def test_planner_sensitive_tools_are_all_executable():
    # Every tool the planner can flag as sensitive must have a real handler,
    # otherwise an approved plan would fail with "Unknown tool".
    missing = SENSITIVE_TOOLS - set(executor.HANDLERS.keys())
    assert not missing, f"Sensitive tools with no executor handler: {missing}"
