"""The vault app: what runs when a laptop connects with ssh vaultpi.

Reads --laptop, builds the Session, runs login (login.py), then the menu
loop (Add in add.py, Get in get.py), all inside one top-level try that
ends the session cleanly on a timeout, Ctrl+D or a crash.
"""
