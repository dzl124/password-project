"""The vault app: what runs when a laptop connects with ssh vaultpi.

Login (2FA, then the master key), the menu, Add and Get (search, view,
edit, delete), all inside one session that ends cleanly on a timeout,
Ctrl+D or a crash.
"""
