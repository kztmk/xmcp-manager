from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from xmcp_manager.account_store import create_account, load_accounts, save_accounts
from xmcp_manager.app_settings import AppSettingsError, load_app_settings, save_app_settings
from xmcp_manager.client_config import (
    manual_snippet,
    update_selected_clients,
)
from xmcp_manager.models import AppSettings, McpClientId, ServerStateSnapshot
from xmcp_manager.server_manager import ServerManager
from xmcp_manager.tool_allowlist import load_tool_catalog


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
        self._refresh_accounts()
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

    def _refresh_accounts(self) -> None:
        self.account_list.delete(0, tk.END)
        for account in self.accounts_doc.accounts:
            self.account_list.insert(tk.END, f"{account.label} [{account.credential_status.value}]")

    def _add_account(self) -> None:
        account = create_account("@example", "Example")
        self.accounts_doc.accounts.append(account)
        save_accounts(self.accounts_doc)
        self._refresh_accounts()

    def _build_account_tab(self) -> None:
        tab = self.tabs.tab("Account")
        ctk.CTkLabel(tab, text="Account metadata and API Credentials").pack(
            anchor="w",
            padx=12,
            pady=12,
        )
        ctk.CTkLabel(tab, text="Credential editing is implemented in the storage layer.").pack(
            anchor="w", padx=12
        )

    def _build_tools_tab(self) -> None:
        tab = self.tabs.tab("Tools")
        ctk.CTkLabel(tab, text=f"Tool Catalog: {len(self.catalog.tools)} tools loaded").pack(
            anchor="w", padx=12, pady=12
        )
        ctk.CTkLabel(tab, text="Default preset: 広範な書き込み操作").pack(anchor="w", padx=12)

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
        ctk.CTkButton(tab, text="Stop server", command=self.server_manager.stop).pack(
            anchor="w", padx=12, pady=8
        )
        self.log_box = ctk.CTkTextbox(tab)
        self.log_box.pack(fill="both", expand=True, padx=12, pady=8)

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
