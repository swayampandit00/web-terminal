# hello_plugin.py
def register(shell):
    """
    This plugin adds a simple 'greet' command:
    Usage: greet <name>
    """
    def greet_cmd(args):
        if not args:
            print("Usage: greet <name>")
            return
        name = " ".join(args)
        print(f"Hello, {name}! 👋 - from hello_plugin")

    # attach to shell by injecting into object's namespace via closure
    # We'll add a small dispatcher entry to the shell by setting an attribute
    # and monkey-patching shell.loop isn't ideal; instead we'll add a helper function
    # The main shell falls back to system commands, so we bind to shell.greet_available
    if not hasattr(shell, "plugin_commands"):
        shell.plugin_commands = {}
    shell.plugin_commands["greet"] = greet_cmd

    # patch the shell.loop to check plugin_commands before falling back (simple approach)
    orig_loop = shell.loop
    def patched_loop():
        print("hello_plugin activated.")
        # monkey-patch: on each command, check plugin_commands
        import types
        def new_loop_inner():
            # reuse original loop code by calling orig_loop but plugin check must happen earlier;
            # to keep plugin simple, we provide a small helper function on shell that main loop can call.
            return orig_loop()
        shell.plugin_commands = getattr(shell, "plugin_commands", {})
        return new_loop_inner()
    # we won't replace shell.loop to avoid complex patching; plugin registered function accessible:
    # main shell will not auto-call plugin; instead plugin provides shell.plugin_commands to be used by user
