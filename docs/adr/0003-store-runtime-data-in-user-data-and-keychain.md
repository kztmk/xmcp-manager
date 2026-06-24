# Store runtime data in user data and keychain

XMCP Manager stores non-secret account metadata in the OS user data directory and stores API credentials in the OS keychain. This avoids writing runtime state into the application bundle or executable directory and keeps secrets out of local JSON files.
