from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from xmcp_manager.account_store import (
    SaveMode,
    StoreError,
    create_account,
    delete_account,
    get_credentials_status,
    load_accounts,
    load_credentials_for_start,
    save_accounts,
    save_credentials,
)
from xmcp_manager.app_settings import AppSettingsError, load_app_settings, save_app_settings
from xmcp_manager.client_config import (
    manual_snippet,
    update_selected_clients,
)
from xmcp_manager.models import (
    Account,
    AppSettings,
    CredentialStatus,
    McpClientId,
    ServerStateSnapshot,
    ToolPreset,
    utc_now_iso,
)
from xmcp_manager.server_manager import ServerManager
from xmcp_manager.tool_allowlist import (
    generate_allowlist,
    load_tool_catalog,
    requires_warning,
)


class XMCPManagerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("XMCP Manager")
        self.geometry("980x640")
        ctk.set_appearance_mode("system")
        self.server_manager = ServerManager()
        try:
            self.settings = load_app_settings()
        except AppSettingsError as exc:
            self.settings = AppSettings()
            messagebox.showerror("Recovery required", str(exc))
        self.accounts_doc = load_accounts()
        self.catalog = load_tool_catalog()
        self.selected_account_id: str | None = None
        self._build_ui()
        self.server_manager.subscribe(self._on_server_state)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.header = ctk.CTkLabel(self, text="Server State: stopped")
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=8)

        self.account_frame = ctk.CTkFrame(self, width=240)
        self.account_frame.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))
        self.account_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.account_frame, text="X Accounts").grid(
            row=0,
            column=0,
            sticky="w",
            padx=12,
            pady=8,
        )
        self.account_list = tk.Listbox(self.account_frame, width=28)
        self.account_list.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        self.account_list.bind("<<ListboxSelect>>", self._on_account_selected)
        ctk.CTkButton(self.account_frame, text="+ Add", command=self._add_account).grid(
            row=2, column=0, sticky="ew", padx=12, pady=8
        )

        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        for name in ("Account", "Tools", "Clients", "Server", "Settings"):
            self.tabs.add(name)
        self._build_account_tab()
        self._build_tools_tab()
        self._build_clients_tab()
        self._build_server_tab()
        self._build_settings_tab()
        self._refresh_accounts()

    def _refresh_accounts(self) -> None:
        previous_id = self.selected_account_id
        self.accounts_doc = load_accounts()
        self.account_list.delete(0, tk.END)
        selected_index = 0
        for index, account in enumerate(self.accounts_doc.accounts):
            self.account_list.insert(tk.END, f"{account.label} [{account.credential_status.value}]")
            if account.id == previous_id:
                selected_index = index
        if self.accounts_doc.accounts:
            self.account_list.selection_set(selected_index)
            self.selected_account_id = self.accounts_doc.accounts[selected_index].id
        else:
            self.selected_account_id = None
        self._load_selected_account_into_form()
        self._load_selected_account_into_tools_form()

    def _add_account(self) -> None:
        base = "new-account"
        existing = {account.handle.lower() for account in self.accounts_doc.accounts}
        handle = f"@{base}"
        suffix = 2
        while handle.lower() in existing:
            handle = f"@{base}-{suffix}"
            suffix += 1
        try:
            account = create_account(handle, "")
        except StoreError as exc:
            messagebox.showerror("Account", str(exc))
            return
        self.accounts_doc.accounts.append(account)
        save_accounts(self.accounts_doc)
        self.selected_account_id = account.id
        self._refresh_accounts()

    def _selected_account(self) -> Account | None:
        if self.selected_account_id is None:
            return None
        for account in self.accounts_doc.accounts:
            if account.id == self.selected_account_id:
                return account
        return None

    def _on_account_selected(self, _event: tk.Event[tk.Listbox]) -> None:
        selection = self.account_list.curselection()  # type: ignore[no-untyped-call]
        if not selection:
            return
        index = selection[0]
        if index >= len(self.accounts_doc.accounts):
            return
        self.selected_account_id = self.accounts_doc.accounts[index].id
        self._load_selected_account_into_form()
        self._load_selected_account_into_tools_form()

    def _build_account_tab(self) -> None:
        tab = self.tabs.tab("Account")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)

        metadata = ctk.CTkFrame(tab)
        metadata.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        metadata.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(metadata, text="Account").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8)
        )
        ctk.CTkLabel(metadata, text="Handle").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        self.handle_var = tk.StringVar()
        self.handle_entry = ctk.CTkEntry(metadata, textvariable=self.handle_var)
        self.handle_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=6)
        ctk.CTkLabel(metadata, text="Display name").grid(
            row=2, column=0, sticky="w", padx=12, pady=6
        )
        self.display_name_var = tk.StringVar()
        self.display_name_entry = ctk.CTkEntry(metadata, textvariable=self.display_name_var)
        self.display_name_entry.grid(row=2, column=1, sticky="ew", padx=12, pady=6)
        self.credential_status_label = ctk.CTkLabel(metadata, text="Credentials: -")
        self.credential_status_label.grid(
            row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 4)
        )
        ctk.CTkButton(metadata, text="Save Account", command=self._save_account_metadata).grid(
            row=4, column=0, sticky="ew", padx=12, pady=12
        )
        ctk.CTkButton(
            metadata,
            text="Delete Account",
            fg_color="#8f1d1d",
            hover_color="#6f1515",
            command=self._delete_selected_account,
        ).grid(row=4, column=1, sticky="ew", padx=12, pady=12)

        credentials = ctk.CTkFrame(tab)
        credentials.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        credentials.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(credentials, text="API Credentials").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8)
        )
        ctk.CTkLabel(credentials, text="API Key").grid(
            row=1, column=0, sticky="w", padx=12, pady=6
        )
        self.consumer_key_var = tk.StringVar()
        self.consumer_key_entry = ctk.CTkEntry(
            credentials,
            textvariable=self.consumer_key_var,
            show="*",
            placeholder_text="Leave blank to keep saved value",
        )
        self.consumer_key_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=6)
        ctk.CTkLabel(credentials, text="API Key Secret").grid(
            row=2, column=0, sticky="w", padx=12, pady=6
        )
        self.consumer_secret_var = tk.StringVar()
        self.consumer_secret_entry = ctk.CTkEntry(
            credentials,
            textvariable=self.consumer_secret_var,
            show="*",
            placeholder_text="Leave blank to keep saved value",
        )
        self.consumer_secret_entry.grid(row=2, column=1, sticky="ew", padx=12, pady=6)
        ctk.CTkLabel(credentials, text="Bearer Token").grid(
            row=3, column=0, sticky="w", padx=12, pady=6
        )
        self.bearer_token_var = tk.StringVar()
        self.bearer_token_entry = ctk.CTkEntry(
            credentials,
            textvariable=self.bearer_token_var,
            show="*",
            placeholder_text="Leave blank to keep saved value",
        )
        self.bearer_token_entry.grid(row=3, column=1, sticky="ew", padx=12, pady=6)
        ctk.CTkButton(credentials, text="Save Credentials", command=self._save_credentials).grid(
            row=4, column=0, columnspan=2, sticky="ew", padx=12, pady=12
        )
        self.account_message = ctk.CTkLabel(credentials, text="", justify="left", wraplength=360)
        self.account_message.grid(row=5, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 12))

    def _set_account_form_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in (
            self.handle_entry,
            self.display_name_entry,
            self.consumer_key_entry,
            self.consumer_secret_entry,
            self.bearer_token_entry,
        ):
            widget.configure(state=state)

    def _load_selected_account_into_form(self) -> None:
        if not hasattr(self, "handle_var"):
            return
        account = self._selected_account()
        if account is None:
            self.handle_var.set("")
            self.display_name_var.set("")
            self.consumer_key_var.set("")
            self.consumer_secret_var.set("")
            self.bearer_token_var.set("")
            self.credential_status_label.configure(text="Credentials: -")
            self.account_message.configure(text="Add an account to start.")
            self._set_account_form_enabled(False)
            return
        account.credential_status = get_credentials_status(account.id)
        self.handle_var.set(account.handle)
        self.display_name_var.set(account.display_name)
        self.consumer_key_var.set("")
        self.consumer_secret_var.set("")
        self.bearer_token_var.set("")
        self.credential_status_label.configure(
            text=f"Credentials: {account.credential_status.value}"
        )
        if account.credential_status is CredentialStatus.MISSING:
            message = "No credentials are saved. Enter all three fields before saving."
        elif account.credential_status is CredentialStatus.INVALID:
            message = "Saved credentials are invalid. Re-enter all three fields."
        elif account.credential_status is CredentialStatus.INACCESSIBLE:
            message = "The OS keychain is not accessible. Credentials cannot be used."
        else:
            message = "Saved credentials are available. Blank fields keep existing values."
        self.account_message.configure(text=message)
        self._set_account_form_enabled(True)

    def _save_account_metadata(self) -> None:
        account = self._selected_account()
        if account is None:
            messagebox.showwarning("Account", "Select an account first.")
            return
        handle = self.handle_var.get().strip()
        if not handle:
            messagebox.showwarning("Account", "Handle is required.")
            return
        if not handle.startswith("@"):
            handle = f"@{handle}"
        normalized = handle.lower()
        duplicate = any(
            other.id != account.id and other.handle.lower() == normalized
            for other in self.accounts_doc.accounts
        )
        if duplicate:
            messagebox.showwarning("Account", f"{handle} is already registered.")
            return
        account.handle = handle
        account.display_name = self.display_name_var.get().strip()
        save_accounts(self.accounts_doc)
        self._refresh_accounts()
        messagebox.showinfo("Account", "Account saved.")

    def _save_credentials(self) -> None:
        account = self._selected_account()
        if account is None:
            messagebox.showwarning("Credentials", "Select an account first.")
            return
        account.credential_status = get_credentials_status(account.id)
        mode: SaveMode = (
            "create" if account.credential_status is CredentialStatus.MISSING else "update"
        )
        try:
            save_credentials(
                account.id,
                {
                    "consumerKey": self.consumer_key_var.get(),
                    "consumerSecret": self.consumer_secret_var.get(),
                    "bearerToken": self.bearer_token_var.get(),
                },
                mode=mode,
            )
        except StoreError as exc:
            messagebox.showerror("Credentials", str(exc))
            self._load_selected_account_into_form()
            return
        self._refresh_accounts()
        messagebox.showinfo("Credentials", "Credentials saved to the OS keychain.")

    def _delete_selected_account(self) -> None:
        account = self._selected_account()
        if account is None:
            messagebox.showwarning("Account", "Select an account first.")
            return
        if not messagebox.askyesno("Delete Account", f"Delete {account.label}?"):
            return
        result = delete_account(account.id)
        self.selected_account_id = None
        self._refresh_accounts()
        if result.ok:
            messagebox.showinfo("Account", "Account deleted.")
        else:
            messagebox.showwarning("Account", result.message or "Account deleted with warnings.")

    def _build_tools_tab(self) -> None:
        tab = self.tabs.tab("Tools")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        summary = ctk.CTkFrame(tab)
        summary.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=12)
        summary.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(summary, text="Preset").grid(row=0, column=0, sticky="w", padx=12, pady=12)
        self.tool_preset_var = tk.StringVar(value=ToolPreset.BROAD_WRITE.value)
        self.tool_preset_control = ctk.CTkSegmentedButton(
            summary,
            values=[
                ToolPreset.READ_ONLY.value,
                ToolPreset.BROAD_WRITE.value,
                ToolPreset.FULL_ACCESS.value,
                ToolPreset.CUSTOM.value,
            ],
            variable=self.tool_preset_var,
            command=lambda _value: self._preview_tool_allowlist(),
        )
        self.tool_preset_control.grid(row=0, column=1, sticky="ew", padx=12, pady=12)

        catalog_frame = ctk.CTkFrame(tab)
        catalog_frame.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))
        catalog_frame.grid_rowconfigure(1, weight=1)
        catalog_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            catalog_frame,
            text=f"Tool Catalog: {len(self.catalog.tools)} tools loaded",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=12)
        self.tool_catalog_box = ctk.CTkTextbox(catalog_frame, height=260)
        self.tool_catalog_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._populate_tool_catalog_box()

        custom_frame = ctk.CTkFrame(tab)
        custom_frame.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        custom_frame.grid_rowconfigure(1, weight=1)
        custom_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(custom_frame, text="Custom allowlist").grid(
            row=0, column=0, sticky="w", padx=12, pady=12
        )
        self.custom_tools_box = ctk.CTkTextbox(custom_frame, height=180)
        self.custom_tools_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.tool_preview_label = ctk.CTkLabel(
            custom_frame,
            text="",
            justify="left",
            wraplength=360,
        )
        self.tool_preview_label.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        ctk.CTkButton(
            custom_frame,
            text="Save Tool Settings",
            command=self._save_tool_settings,
        ).grid(
            row=3,
            column=0,
            sticky="ew",
            padx=12,
            pady=(0, 12),
        )

    def _populate_tool_catalog_box(self) -> None:
        if not hasattr(self, "tool_catalog_box"):
            return
        self.tool_catalog_box.configure(state="normal")
        self.tool_catalog_box.delete("1.0", tk.END)
        rows = [
            f"{tool.name}  [{tool.risk_level.value}]  {tool.category}"
            for tool in self.catalog.tools
        ]
        self.tool_catalog_box.insert("1.0", "\n".join(rows))
        self.tool_catalog_box.configure(state="disabled")

    def _parse_custom_tools(self) -> list[str]:
        if not hasattr(self, "custom_tools_box"):
            return []
        raw = self.custom_tools_box.get("1.0", tk.END)
        normalized = raw.replace(",", "\n")
        return [line.strip() for line in normalized.splitlines() if line.strip()]

    def _set_tools_form_enabled(self, enabled: bool) -> None:
        if not hasattr(self, "tool_preset_control"):
            return
        state = "normal" if enabled else "disabled"
        self.tool_preset_control.configure(state=state)
        self.custom_tools_box.configure(state=state)

    def _load_selected_account_into_tools_form(self) -> None:
        if not hasattr(self, "tool_preset_var"):
            return
        account = self._selected_account()
        if account is None:
            self.tool_preset_var.set(ToolPreset.BROAD_WRITE.value)
            self.custom_tools_box.configure(state="normal")
            self.custom_tools_box.delete("1.0", tk.END)
            self.custom_tools_box.configure(state="disabled")
            self.tool_preview_label.configure(text="Add an account to configure tool access.")
            self._set_tools_form_enabled(False)
            return
        self.tool_preset_var.set(account.tool_allowlist_preset.value)
        self.custom_tools_box.configure(state="normal")
        self.custom_tools_box.delete("1.0", tk.END)
        self.custom_tools_box.insert("1.0", "\n".join(account.tool_allowlist))
        self._set_tools_form_enabled(True)
        self._preview_tool_allowlist()

    def _preview_tool_allowlist(self) -> None:
        if not hasattr(self, "tool_preview_label"):
            return
        account = self._selected_account()
        if account is None:
            self.tool_preview_label.configure(text="Add an account to configure tool access.")
            return
        try:
            preset = ToolPreset(self.tool_preset_var.get())
        except ValueError:
            self.tool_preview_label.configure(text="Invalid preset.")
            return
        custom_tools = self._parse_custom_tools()
        allowlist = generate_allowlist(preset, custom_tools, self.catalog)
        warnings = requires_warning(preset, custom_tools, self.catalog)
        lines = []
        if preset is ToolPreset.FULL_ACCESS:
            lines.append("Full access: no X_API_TOOL_ALLOWLIST will be set.")
        else:
            lines.append(f"{len(allowlist.tools)} tools will be allowed.")
        if not allowlist.validation.ok:
            lines.append("Invalid tools: " + ", ".join(allowlist.validation.invalid_tools))
        if warnings.broad_write:
            lines.append("Warning: broad write access includes write/destructive/sensitive tools.")
        if warnings.full_access:
            lines.append("Warning: full access exposes every xmcp tool.")
        if warnings.unknown_custom_tools:
            lines.append("Unknown risk tools: " + ", ".join(warnings.unknown_custom_tools))
        self.tool_preview_label.configure(text="\n".join(lines))

    def _save_tool_settings(self) -> None:
        account = self._selected_account()
        if account is None:
            messagebox.showwarning("Tools", "Select an account first.")
            return
        try:
            preset = ToolPreset(self.tool_preset_var.get())
        except ValueError:
            messagebox.showwarning("Tools", "Select a valid preset.")
            return
        custom_tools = self._parse_custom_tools()
        allowlist = generate_allowlist(preset, custom_tools, self.catalog)
        if not allowlist.validation.ok:
            messagebox.showwarning(
                "Tools",
                "Custom allowlist contains invalid tools: "
                + ", ".join(allowlist.validation.invalid_tools),
            )
            self._preview_tool_allowlist()
            return
        warnings = requires_warning(preset, custom_tools, self.catalog)
        if warnings.full_access and not self.settings.full_access_warning_accepted:
            if not messagebox.askyesno("Tools", "Full access exposes every xmcp tool. Save?"):
                return
            self.settings.full_access_warning_accepted = True
            save_app_settings(self.settings)
        if warnings.broad_write and not self.settings.broad_write_preset_warning_accepted:
            if not messagebox.askyesno(
                "Tools",
                (
                    "Broad write access can post, delete, send DMs, "
                    "and perform other X operations. Save?"
                ),
            ):
                return
            self.settings.broad_write_preset_warning_accepted = True
            save_app_settings(self.settings)
        if warnings.unknown_custom_tools:
            if not messagebox.askyesno(
                "Tools",
                "Custom allowlist includes uncategorized tools: "
                + ", ".join(warnings.unknown_custom_tools)
                + ". Save?",
            ):
                return
        account.tool_allowlist_preset = preset
        account.tool_allowlist = list(dict.fromkeys(custom_tools))
        save_accounts(self.accounts_doc)
        self._preview_tool_allowlist()
        messagebox.showinfo("Tools", "Tool settings saved.")

    def _build_clients_tab(self) -> None:
        tab = self.tabs.tab("Clients")
        self.claude_var = tk.BooleanVar(
            value=McpClientId.CLAUDE_DESKTOP.value in self.settings.selected_mcp_clients
        )
        self.codex_var = tk.BooleanVar(
            value=McpClientId.CODEX_DESKTOP.value in self.settings.selected_mcp_clients
        )
        ctk.CTkCheckBox(tab, text="Claude Desktop", variable=self.claude_var).pack(
            anchor="w", padx=12, pady=8
        )
        ctk.CTkCheckBox(tab, text="Codex Desktop", variable=self.codex_var).pack(
            anchor="w", padx=12, pady=8
        )
        ctk.CTkButton(tab, text="Update MCP client config", command=self._update_clients).pack(
            anchor="w", padx=12, pady=8
        )
        snippet = (
            "Claude Desktop:\n"
            f"{manual_snippet(McpClientId.CLAUDE_DESKTOP.value, self.settings.endpoint_url)}\n\n"
            "Codex Desktop:\n"
            f"{manual_snippet(McpClientId.CODEX_DESKTOP.value, self.settings.endpoint_url)}"
        )
        self.snippet_box = ctk.CTkTextbox(tab, height=220)
        self.snippet_box.pack(fill="both", expand=True, padx=12, pady=8)
        self.snippet_box.insert("1.0", snippet)

    def _selected_clients(self) -> list[str]:
        clients: list[str] = []
        if self.claude_var.get():
            clients.append(McpClientId.CLAUDE_DESKTOP.value)
        if self.codex_var.get():
            clients.append(McpClientId.CODEX_DESKTOP.value)
        return clients

    def _update_clients(self) -> None:
        clients = self._selected_clients()
        if not clients:
            messagebox.showwarning("MCP clients", "Select Claude Desktop or Codex Desktop.")
            return
        self.settings.selected_mcp_clients = clients
        save_app_settings(self.settings)
        result = update_selected_clients(clients, self.settings.endpoint_url)
        message = "\n".join(f"{item.client_id}: {item.message}" for item in result.results)
        if result.ok:
            messagebox.showinfo("MCP clients", message)
        else:
            messagebox.showwarning("MCP clients", message)

    def _build_server_tab(self) -> None:
        tab = self.tabs.tab("Server")
        controls = ctk.CTkFrame(tab)
        controls.pack(fill="x", padx=12, pady=8)
        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)
        self.server_message = ctk.CTkLabel(controls, text="Select an account and start xmcp.")
        self.server_message.grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=8)
        ctk.CTkButton(controls, text="Start server", command=self._start_server).grid(
            row=1, column=0, sticky="ew", padx=12, pady=(0, 12)
        )
        ctk.CTkButton(controls, text="Stop server", command=self._stop_server).grid(
            row=1, column=1, sticky="ew", padx=12, pady=(0, 12)
        )
        self.log_box = ctk.CTkTextbox(tab)
        self.log_box.pack(fill="both", expand=True, padx=12, pady=8)

    def _start_server(self) -> None:
        account = self._selected_account()
        if account is None:
            messagebox.showwarning("Server", "Select an account first.")
            return
        account.credential_status = get_credentials_status(account.id)
        if account.credential_status is not CredentialStatus.OK:
            messagebox.showwarning(
                "Server",
                f"Credentials are {account.credential_status.value}. Save valid credentials first.",
            )
            self._load_selected_account_into_form()
            return
        try:
            credentials = load_credentials_for_start(account.id)
        except StoreError as exc:
            messagebox.showerror("Server", str(exc))
            self._refresh_accounts()
            return
        allowlist = generate_allowlist(
            account.tool_allowlist_preset,
            account.tool_allowlist,
            self.catalog,
        )
        if not allowlist.validation.ok:
            messagebox.showwarning(
                "Server",
                "Custom tool allowlist contains invalid tools: "
                + ", ".join(allowlist.validation.invalid_tools),
            )
            return
        warnings = requires_warning(
            account.tool_allowlist_preset,
            account.tool_allowlist,
            self.catalog,
        )
        if warnings.full_access and not self.settings.full_access_warning_accepted:
            if not messagebox.askyesno(
                "Tool Allowlist",
                "Full access exposes every xmcp tool. Continue?",
            ):
                return
            self.settings.full_access_warning_accepted = True
            save_app_settings(self.settings)
        if warnings.broad_write and not self.settings.broad_write_preset_warning_accepted:
            if not messagebox.askyesno(
                "Tool Allowlist",
                (
                    "Broad write access can post, delete, send DMs, "
                    "and perform other X operations. Continue?"
                ),
            ):
                return
            self.settings.broad_write_preset_warning_accepted = True
            save_app_settings(self.settings)
        if warnings.unknown_custom_tools:
            if not messagebox.askyesno(
                "Tool Allowlist",
                "Custom allowlist includes uncategorized tools: "
                + ", ".join(warnings.unknown_custom_tools)
                + ". Continue?",
            ):
                return
        account.last_used_at = utc_now_iso()
        save_accounts(self.accounts_doc)
        result = self.server_manager.start(
            account,
            credentials,
            allowlist.env_value,
            self.settings,
        )
        if not result.ok:
            messagebox.showwarning("Server", result.message)
        self.server_message.configure(text=result.message)

    def _stop_server(self) -> None:
        result = self.server_manager.stop()
        self.server_message.configure(text=result.message)

    def _build_settings_tab(self) -> None:
        tab = self.tabs.tab("Settings")
        ctk.CTkLabel(tab, text=f"MCP endpoint: {self.settings.endpoint_url}").pack(
            anchor="w", padx=12, pady=12
        )
        ctk.CTkLabel(tab, text=f"OAuth Callback URI: {self.settings.callback_uri}").pack(
            anchor="w", padx=12
        )

    def _on_server_state(self, snapshot: ServerStateSnapshot) -> None:
        self.header.configure(
            text=f"Server State: {snapshot.state.value}"
            + (f"  Account: {snapshot.account_label}" if snapshot.account_label else "")
        )
        if hasattr(self, "log_box"):
            self.log_box.delete("1.0", tk.END)
            self.log_box.insert("1.0", "\n".join(snapshot.logs))


def main() -> None:
    app = XMCPManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
