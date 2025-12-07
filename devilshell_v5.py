#!/usr/bin/env python3
# DevilShell v5+ (history + autocomplete + windows editor fallback + sample plugin support)
import os
import sys
import json
import socket
import subprocess
import datetime
import platform
import getpass
try:
    import readline
    import rlcompleter
    READLINE_AVAILABLE = True
except ImportError:
    readline = None
    rlcompleter = None
    READLINE_AVAILABLE = False
import base64
import hashlib
from colorama import init, Fore, Style
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet

init(autoreset=True)

# ---------------------------
# Config
# ---------------------------
SHELL_NAME = "devilshell"
USERS_FILE = "users.json"
LOG_FILE = "devilshell.log"
PLUGINS_DIR = "plugins"
HISTORY_FILE = os.path.expanduser("~/.devilshell_history")
DEFAULT_THEME = "X"
PASSWORD_ITERATIONS = 200_000

DEFAULT_USERS = {"admin": "devil123", "guest": "0000"}

# ---------------------------
# Utility functions (same as before)
# ---------------------------
def generate_salt():
    return base64.urlsafe_b64encode(os.urandom(16)).decode()

def hash_password(password: str, salt: str) -> str:
    pwd = password.encode()
    saltb = base64.urlsafe_b64decode(salt.encode())
    dk = hashlib.pbkdf2_hmac("sha256", pwd, saltb, PASSWORD_ITERATIONS)
    return dk.hex()

def verify_password(password: str, salt: str, hashed_hex: str) -> bool:
    return hash_password(password, salt) == hashed_hex

def derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as KDF
    kdf = KDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PASSWORD_ITERATIONS,
    )
    key = kdf.derive(passphrase.encode())
    return base64.urlsafe_b64encode(key)

# ---------------------------
# Users management
# ---------------------------
def load_users():
    if not os.path.exists(USERS_FILE):
        users = {}
        for uname, pwd in DEFAULT_USERS.items():
            salt = generate_salt()
            users[uname] = {"salt": salt, "hash": hash_password(pwd, salt), "theme": DEFAULT_THEME}
        save_users(users)
        return users
    else:
        with open(USERS_FILE, "r") as f:
            return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# ---------------------------
# Logging
# ---------------------------
def log_cmd(user: str, cmd: str):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.datetime.now().isoformat()} | {user or 'anon'} | {cmd}\n")

# ---------------------------
# Banner / Themes
# ---------------------------
BANNERS = {
    "X": Fore.GREEN + """
██████╗ ███████╗██╗   ██╗██╗██╗     ███████╗
██   █║ ██╔════╝██║   ██║██║██║     ██╔════╝
██   █║ █████╗  ██║   ██║██║██║     █████╗  
██   █║ ██╔══╝  ╚██╗ ██╔╝██║██║     ██╔══╝  
██████║ ███████╗ ╚████╔╝ ██║███████╗███████╗
╚═════╝ ╚══════╝  ╚═══╝  ╚═╝╚══════╝╚══════╝
        Welcome to DevilShell - Hacker Mode
""",
    "Y": Fore.RED + "Welcome to DevilShell - Devil Mode\n",
    "Z": Fore.MAGENTA + "Welcome to DevilShell - Cyberpunk Mode\n"
}

def print_banner(theme_code):
    banner = BANNERS.get(theme_code, BANNERS["X"])
    print(banner + Style.RESET_ALL)

# ---------------------------
# Plugins
# ---------------------------
LOADED_PLUGINS = {}
def load_plugins(shell):
    LOADED_PLUGINS.clear()
    if not os.path.exists(PLUGINS_DIR):
        os.makedirs(PLUGINS_DIR)
    sys.path.insert(0, os.path.abspath(PLUGINS_DIR))
    for fname in os.listdir(PLUGINS_DIR):
        if fname.endswith(".py"):
            modname = fname[:-3]
            try:
                if modname in sys.modules:
                    del sys.modules[modname]
                mod = __import__(modname)
                if hasattr(mod, "register"):
                    mod.register(shell)
                    LOADED_PLUGINS[modname] = mod
            except Exception as e:
                print(Fore.RED + f"Plugin load error {modname}: {e}")

def list_plugins():
    return list(LOADED_PLUGINS.keys())

# ---------------------------
# Readline: history + completer
# ---------------------------
BUILTIN_COMMANDS = [
    "help", "exit", "clear", "time", "sysinfo", "echo", "ls", "cd", "calc", "ip", "ping",
    "run", "edit", "scan", "install", "tool-install", "logs", "passwd", "theme", "plugin", "encrypt", "decrypt",
    "plugin reload", "plugin list", "theme set", "theme list",
    "dir", "cls", "copy", "del", "mkdir", "rmdir", "type", "find", "findstr", "tasklist", "taskkill", "shutdown", "set", "path",
    "apt", "pkg", "wget", "curl", "git", "nano", "vim", "htop", "ps", "kill", "grep", "tar", "unzip", "zip", "chmod", "chown", "sed", "awk",
    "pwd", "mv", "touch", "ln", "man", "uname", "whoami", "head", "tail", "diff", "comm", "cmp", "sort", "export", "ssh", "service", "df", "mount", "ifconfig", "traceroute", "ufw", "iptables", "sudo", "sudo -su", "sudosu", "cal", "alias", "dd", "whereis", "whatis", "top", "useradd", "usermod", "less", "killall", "pacman", "yum", "rpm", "cp", "rm", "cat",
    "basename", "dirname", "stat", "uniq", "wc", "nl", "tee", "cut", "paste", "split", "join", "od", "file", "sha1sum", "sha256sum", "md5sum",
    "base64", "strings", "xxd", "iconv", "col", "column", "fold", "fmt", "rev", "dos2unix", "unix2dos",
    "gzip", "gunzip", "bz2", "pbzip2", "xz", "7z", "ar", "cpio",
    "du", "fsck", "mkfs", "blkid", "fdisk", "parted", "free", "swapon", "swapoff", "rsync", "dump", "restore",
    "nice", "renice", "bg", "fg", "jobs", "nohup", "systemctl", "journalctl", "uptime", "dmesg", "hostnamectl", "loginctl", "strace", "lsof", "watch", "restart", "status",
    "netstat", "ss", "nslookup", "dig", "arp", "route", "nmap", "tcpdump", "telnet", "ftp", "scp", "iptables-save", "iptables-restore", "openssl", "hostname", "dnsdomainname",
    "groupadd", "groupdel", "groupmod", "id", "su", "logout", "chsh", "chgrp", "newgrp", "umask", "groups",
    "snap", "dnf", "pip", "pip3", "brew",
    "lspci", "lsusb", "dmidecode", "hdparm", "smartctl", "inxi", "meminfo", "cpuinfo",
    "perf", "vmstat", "iostat", "sar", "mpstat", "iotop",
    "history", "source", "eval", "test", "complete", "unalias", "which", "select", "pushd", "popd", "printf",
    "docker", "docker ps", "docker run", "docker logs",
    "kubectl", "kubectl get pods",
    # Hacking tools
    "msfconsole", "metasploit", "sqlmap", "hydra", "john", "aircrack-ng", "wireshark", "burp", "nikto", "dirb", "gobuster", "ettercap", "snort", "suricata", "openvas", "nessus", "maltego", "recon-ng", "theharvester", "shodan", "exploitdb", "searchsploit", "beef", "setoolkit", "veil", "empire", "cobaltstrike", "bloodhound", "responder", "impacket", "crackmapexec", "evil-winrm", "chisel", "ligolo", "proxychains", "tor", "torsocks", "macchanger", "driftnet", "ettercap-graphical", "yersinia", "scapy", "hping3", "fping", "arping", "masscan", "zmap", "unicornscan", "amass", "sublist3r", "dnsrecon", "dnsenum", "fierce", "dnsmap", "dnswalk", "host", "whois", "mtr", "hping", "tcptraceroute", "lbd", "wafw00f", "whatweb", "dirbuster", "wfuzz", "cewl", "cme", "enum4linux", "smbclient", "smbmap", "nbtscan", "onesixtyone", "snmpwalk", "patator", "medusa", "ncrack", "hashcat", "rainbowcrack", "ophcrack", "cudahashcat", "pyrit", "reaver", "bully", "pixie-dust", "fluxion", "wifite", "kismet", "airodump-ng", "aireplay-ng", "airmon-ng", "mdk3", "mdk4", "hostapd", "dnsmasq", "dhcpd", "sslstrip", "sslsplit", "mitmf", "bettercap", "inveigh", "smbrelayx", "ntlmrelayx", "secretsdump", "mimikatz", "lsadump", "dcsync", "psexec", "wmiexec", "atexec", "smbexec", "dcomexec", "rdp", "vnc", "tightvnc", "x11vnc", "novnc", "guacamole", "freerdp", "rdesktop", "xfreerdp", "remmina", "putty", "openssh", "dropbear", "paramiko", "fabric", "ansible", "puppet", "chef", "salt", "terraform", "cloudformation", "arm-templates", "packer", "vagrant", "volatility", "autopsy", "sleuthkit", "scalpel", "foremost", "binwalk", "radare2", "ghidra", "ida", "binaryninja", "hopper", "cutter", "angr", "z3", "boolector", "cvc4", "yices", "alloy", "tla", "spin", "uppaal", "nuXmv", "nusmv", "cadence", "systemverilog", "verilog", "vhdl", "spice", "ltspice", "ngspice", "qucs", "kicad", "eagle", "altium", "proteus", "multisim", "logisim", "digital", "verilogger", "modelsim", "vivado", "quartus", "ise", "diamond", "libero", "synplify", "precision", "encounter", "innovus", "tempus", "starrc", "calibre", "icv", "pegasus", "vcs", "verilator", "iverilog", "yosys", "nextpnr", "arachne-pnr", "ice40", "ecp5", "gowin", "lattice", "xilinx", "altera", "intel", "amd", "nvidia", "cuda", "opencl", "vulkan", "opengl", "directx", "metal", "webgl", "webgpu", "wasm", "emscripten", "asmjs", "pypy", "jython", "ironpython", "micropython", "circuitpython", "rustpython", "cpython", "anaconda", "miniconda", "mamba", "poetry", "pipenv", "virtualenv", "conda", "venv", "pyenv", "nvm", "rvm", "rbenv", "nodenv", "goenv", "luaenv", "phpenv", "perlenv", "scalaenv", "clojureenv", "erlangenv", "elixirenv", "haskellenv", "nimenv", "zigenv", "deno", "bun", "yarn", "pnpm", "lerna", "nx", "rush", "turborepo", "monorepo", "polyrepo", "microservices", "serverless", "lambda", "functions", "edge", "cdn", "cloudflare", "fastly", "akamai", "cloudfront", "verizon", "limelight", "incapsula", "sucuri", "stackpath", "bunnynet", "render", "railway", "fly", "vercel", "netlify", "surge", "now", "heroku", "dokku", "caprover", "coolify", "porter", "tails", "qubes", "whonix", "subgraph", "parrot", "kali", "blackarch", "archstrike", "pentoo", "backbox", "dracos", "samurai", "matriux", "networksecuritytoolkit", "caine", "deft", "sift", "paladin", "remnux", "floss"
]

COMMAND_USAGES = {
    "help": "Show this help message",
    "exit": "Exit the shell",
    "clear": "Clear the screen",
    "time": "Show current date and time",
    "sysinfo": "Show system information",
    "echo": "Echo text to output",
    "ls": "List directory contents",
    "cd": "Change directory or show current",
    "calc": "Simple calculator (enter expression)",
    "ip": "Show IP configuration",
    "ping": "Ping a host",
    "run": "Run a Python file",
    "edit": "Edit a file",
    "scan": "Port scan a host",
    "install": "Install Python package",
    "tool-install": "Install system tool",
    "logs": "Show command logs",
    "passwd": "Change user password",
    "theme": "Theme commands (list, set)",
    "plugin": "Plugin commands (list, reload)",
    "encrypt": "Encrypt a file",
    "decrypt": "Decrypt a file",
    "plugin reload": "Reload plugins",
    "plugin list": "List loaded plugins",
    "theme set": "Set theme (X/Y/Z)",
    "theme list": "List available themes",
    "dir": "List directory contents (Windows)",
    "cls": "Clear the screen",
    "copy": "Copy file",
    "del": "Delete file(s)",
    "mkdir": "Create directory",
    "rmdir": "Remove directory",
    "type": "Display file contents",
    "find": "Find files by pattern",
    "findstr": "Find string in file",
    "tasklist": "List running processes",
    "taskkill": "Kill process by PID",
    "shutdown": "Shutdown system",
    "set": "Set environment variable",
    "path": "Show PATH environment variable",
    "pwd": "Print working directory",
    "mv": "Move or rename file",
    "touch": "Create empty file",
    "ln": "Create symbolic link",
    "man": "Display manual page",
    "uname": "Print system information",
    "whoami": "Print current user",
    "head": "Display first lines of file",
    "tail": "Display last lines of file",
    "diff": "Compare files",
    "comm": "Compare sorted files",
    "cmp": "Compare files byte by byte",
    "sort": "Sort lines of text",
    "export": "Set environment variable",
    "ssh": "Secure shell connection",
    "service": "Manage system services",
    "df": "Display disk space usage",
    "mount": "Mount file systems",
    "ifconfig": "Configure network interfaces",
    "traceroute": "Trace packet route",
    "ufw": "Uncomplicated Firewall",
    "iptables": "Administration tool for IPv4 packet filtering",
    "sudo": "Execute command as superuser",
    "sudo -su": "Switch to superuser",
    "sudosu": "Switch to superuser",
    "cal": "Display calendar",
    "alias": "Define or display aliases",
    "dd": "Convert and copy a file",
    "whereis": "Locate binary, source, and manual page files",
    "whatis": "Display one-line manual page descriptions",
    "top": "Display Linux processes",
    "useradd": "Create a new user",
    "usermod": "Modify a user account",
    "less": "View file contents",
    "killall": "Kill processes by name",
    "pacman": "Package manager utility",
    "yum": "Yellowdog Updater Modified",
    "rpm": "RPM Package Manager",
    "cp": "Copy files and directories",
    "rm": "Remove files or directories",
    "cat": "Concatenate and display files",
    "wget": "Non-interactive network downloader",
    "curl": "Transfer data from or to a server",
    "htop": "Interactive process viewer",
    "ps": "Report a snapshot of current processes",
    "kill": "Send signal to a process",
    "grep": "Print lines matching a pattern",
    "tar": "Archiving utility",
    "unzip": "Extract compressed files",
    "zip": "Package and compress files",
    "chmod": "Change file mode bits",
    "chown": "Change file owner and group",
    "sed": "Stream editor",
    "awk": "Pattern scanning and processing language",
    "git": "Distributed version control system",
    "nano": "Text editor",
    "vim": "Text editor",
    "apt": "Package management",
    "pkg": "Package manager",
    "basename": "Strip directory and suffix from filenames",
    "dirname": "Strip last component from file name",
    "stat": "Display file or file system status",
    "uniq": "Report or omit repeated lines",
    "wc": "Print newline, word, and byte counts",
    "nl": "Number lines of files",
    "tee": "Read from standard input and write to standard output",
    "cut": "Remove sections from each line of files",
    "paste": "Merge lines of files",
    "split": "Split a file into pieces",
    "join": "Join lines of two files on a common field",
    "od": "Dump files in octal and other formats",
    "file": "Determine file type",
    "sha1sum": "Compute SHA1 message digest",
    "sha256sum": "Compute SHA256 message digest",
    "md5sum": "Compute MD5 message digest",
    "base64": "Base64 encode/decode",
    "strings": "Print the strings of printable characters in files",
    "xxd": "Make a hexdump or do the reverse",
    "iconv": "Convert text from one character encoding to another",
    "col": "Filter reverse line feeds from input",
    "column": "Columnate lists",
    "fold": "Wrap each input line to fit in specified width",
    "fmt": "Simple optimal text formatter",
    "rev": "Reverse lines of a file",
    "dos2unix": "Convert text file from DOS to Unix format",
    "unix2dos": "Convert text file from Unix to DOS format",
    "gzip": "Compress or expand files",
    "gunzip": "Compress or expand files",
    "bz2": "Block-sorting file compressor",
    "pbzip2": "Parallel bzip2 file compressor",
    "xz": "Compress or decompress .xz and .lzma files",
    "7z": "File archiver with high compression ratio",
    "ar": "Create, modify, and extract from archives",
    "cpio": "Copy files to and from archives",
    "du": "Estimate file space usage",
    "fsck": "File system consistency check and repair",
    "mkfs": "Build a Linux file system",
    "blkid": "Locate/print block device attributes",
    "fdisk": "Manipulate disk partition table",
    "parted": "Partition manipulation program",
    "free": "Display amount of free and used memory",
    "swapon": "Enable/disable devices and files for paging and swapping",
    "swapoff": "Enable/disable devices and files for paging and swapping",
    "rsync": "Remote file and directory synchronization",
    "dump": "Ext2/3/4 filesystem backup",
    "restore": "Restore files or file systems from backups",
    "nice": "Run a program with modified scheduling priority",
    "renice": "Alter priority of running processes",
    "bg": "Send jobs to background",
    "fg": "Bring jobs to foreground",
    "jobs": "List active jobs",
    "nohup": "Run a command immune to hangups",
    "systemctl": "Control the systemd system and service manager",
    "journalctl": "Query the systemd journal",
    "uptime": "Tell how long the system has been running",
    "dmesg": "Print or control the kernel ring buffer",
    "hostnamectl": "Control the system hostname",
    "loginctl": "Control the systemd login manager",
    "strace": "Trace system calls and signals",
    "lsof": "List open files",
    "watch": "Execute a program periodically",
    "restart": "Restart a service",
    "status": "Show status of a service",
    "netstat": "Print network connections, routing tables, interface statistics",
    "ss": "Socket statistics",
    "nslookup": "Query Internet name servers interactively",
    "dig": "DNS lookup utility",
    "arp": "Manipulate the system ARP cache",
    "route": "Show/manipulate the IP routing table",
    "nmap": "Network exploration tool and security/port scanner",
    "tcpdump": "Dump traffic on a network",
    "telnet": "User interface to the TELNET protocol",
    "ftp": "File Transfer Protocol client",
    "scp": "Secure copy (remote file copy program)",
    "iptables-save": "Dump iptables rules",
    "iptables-restore": "Restore iptables rules",
    "openssl": "OpenSSL command line tool",
    "hostname": "Show or set the system's host name",
    "dnsdomainname": "Show the system's DNS domain name",
    "groupadd": "Create a new group",
    "groupdel": "Delete a group",
    "groupmod": "Modify a group",
    "id": "Print user and group information",
    "su": "Change user ID or become superuser",
    "logout": "Exit a login shell",
    "chsh": "Change login shell",
    "chgrp": "Change group ownership",
    "newgrp": "Log in to a new group",
    "umask": "Set file mode creation mask",
    "groups": "Print group memberships",
    "snap": "Tool to interact with snaps",
    "dnf": "Package manager",
    "pip": "Python package installer",
    "pip3": "Python package installer",
    "brew": "Package manager for macOS",
    "lspci": "List PCI devices",
    "lsusb": "List USB devices",
    "dmidecode": "DMI table decoder",
    "hdparm": "Get/set SATA/IDE device parameters",
    "smartctl": "Control and monitor utility for SMART disks",
    "inxi": "Full featured system information script",
    "meminfo": "Display memory information",
    "cpuinfo": "Display CPU information",
    "perf": "Performance analysis tools for Linux",
    "vmstat": "Report virtual memory statistics",
    "iostat": "Report CPU and I/O statistics",
    "sar": "Collect, report, or save system activity information",
    "mpstat": "Report processors related statistics",
    "iotop": "Simple top-like I/O monitor",
    "history": "Command history",
    "source": "Execute commands from a file",
    "eval": "Evaluate several commands/arguments",
    "test": "Evaluate conditional expression",
    "complete": "Specify how arguments are to be completed",
    "unalias": "Remove each NAME from the list of defined aliases",
    "which": "Locate a command",
    "select": "Accept keyboard input",
    "pushd": "Save and then change the current directory",
    "popd": "Restore the previous value of the current directory",
    "printf": "Format and print data",
    "docker": "Docker container platform",
    "docker ps": "List containers",
    "docker run": "Run a command in a new container",
    "docker logs": "Fetch the logs of a container",
    "kubectl": "Kubernetes command-line tool",
    "kubectl get pods": "List pods"
}



def init_history():
    if READLINE_AVAILABLE:
        try:
            readline.read_history_file(HISTORY_FILE)
        except FileNotFoundError:
            open(HISTORY_FILE, "a").close()
        readline.set_history_length(1000)
    else:
        print("Readline not available: history disabled.")

def save_history():
    if READLINE_AVAILABLE:
        try:
            readline.write_history_file(HISTORY_FILE)
        except Exception:
            pass

def completer(text, state):
    # complete builtins and file system
    options = [c for c in BUILTIN_COMMANDS if c.startswith(text)]
    # also add filenames
    if os.path.exists("."):
        files = [f for f in os.listdir(".") if f.startswith(text)]
        options += files
    options = sorted(set(options))
    if state < len(options):
        return options[state]
    else:
        return None

if READLINE_AVAILABLE:
    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
else:
    print("Readline not available: tab completion disabled.")

# ---------------------------
# DevilShell class (core)
# ---------------------------
class DevilShell:
    def __init__(self):
        self.users = load_users()
        self.current_user = None
        self.theme = DEFAULT_THEME
        self.cwd = os.getcwd()
        load_plugins(self)

    # Authentication
    def authenticate(self):
        print(Fore.CYAN + "=== DevilShell Login ===")
        for attempt in range(8):
            uname = input("Username: ").strip()
            if uname == "":
                print("Provide username.")
                continue
            if uname not in self.users:
                print(Fore.YELLOW + "User not found. Create new user? (y/n)")
                c = input("> ").lower()
                if c == "y":
                    self.create_user(uname)
                    print("User created. Please login.")
                    continue
                else:
                    continue
            salt = self.users[uname]["salt"]
            stored_hash = self.users[uname]["hash"]
            pwd = getpass.getpass("Password: ")
            if verify_password(pwd, salt, stored_hash):
                self.current_user = uname
                self.theme = self.users[uname].get("theme", DEFAULT_THEME)
                print(Fore.GREEN + f"Welcome, {uname}!")
                return True
            else:
                print(Fore.RED + "Wrong password.")
        print(Fore.RED + "Too many failed attempts.")
        return False

    def create_user(self, uname):
        while True:
            pwd = getpass.getpass("Set password for new user: ")
            pwd2 = getpass.getpass("Confirm password: ")
            if pwd != pwd2:
                print("Passwords don't match.")
            elif pwd.strip() == "":
                print("Password cannot be empty.")
            else:
                break
        salt = generate_salt()
        self.users[uname] = {"salt": salt, "hash": hash_password(pwd, salt), "theme": DEFAULT_THEME}
        save_users(self.users)
        print(Fore.GREEN + f"User {uname} created.")

    def change_password(self):
        uname = self.current_user
        if not uname:
            print("No user logged in.")
            return
        cur = getpass.getpass("Current password: ")
        if not verify_password(cur, self.users[uname]["salt"], self.users[uname]["hash"]):
            print("Current password incorrect.")
            return
        while True:
            new1 = getpass.getpass("New password: ")
            new2 = getpass.getpass("Confirm new: ")
            if new1 != new2:
                print("Mismatch. Try again.")
            elif new1.strip() == "":
                print("Cannot be empty.")
            else:
                break
        salt = generate_salt()
        self.users[uname]["salt"] = salt
        self.users[uname]["hash"] = hash_password(new1, salt)
        save_users(self.users)
        print(Fore.GREEN + "Password changed successfully.")

    def set_theme(self, code):
        code = code.upper()
        if code not in BANNERS:
            print("Unknown theme. Available:", ", ".join(BANNERS.keys()))
            return
        self.theme = code
        if self.current_user:
            self.users[self.current_user]["theme"] = code
            save_users(self.users)
        print(Fore.CYAN + f"Theme set to {code}")

    # Encryption helpers
    def encrypt_file(self, filepath):
        if not os.path.exists(filepath):
            print("File not found.")
            return
        passphrase = getpass.getpass("Enter passphrase to encrypt with: ")
        salt = os.urandom(16)
        key = derive_fernet_key(passphrase, salt)
        fernet = Fernet(key)
        with open(filepath, "rb") as f:
            data = f.read()
        token = fernet.encrypt(data)
        out_path = filepath + ".enc"
        with open(out_path, "wb") as f_out:
            f_out.write(salt + token)
        print(Fore.GREEN + f"Encrypted -> {out_path}")

    def decrypt_file(self, enc_path):
        if not os.path.exists(enc_path):
            print("File not found.")
            return
        passphrase = getpass.getpass("Enter passphrase to decrypt with: ")
        with open(enc_path, "rb") as f:
            content = f.read()
        if len(content) < 16:
            print("Invalid encrypted file.")
            return
        salt = content[:16]
        token = content[16:]
        key = derive_fernet_key(passphrase, salt)
        fernet = Fernet(key)
        try:
            data = fernet.decrypt(token)
        except Exception:
            print(Fore.RED + "Decryption failed. Wrong passphrase or corrupted file.")
            return
        out_path = enc_path + ".dec"
        with open(out_path, "wb") as f_out:
            f_out.write(data)
        print(Fore.GREEN + f"Decrypted -> {out_path}")

    # Port scan
    def port_scan(self, host):
        try:
            ip = socket.gethostbyname(host)
        except Exception as e:
            print("Resolve error:", e)
            return
        top_ports = [21,22,23,25,53,80,110,139,143,443,445,3306,3389]
        print(Fore.YELLOW + f"Scanning {host} ({ip}) ...")
        for p in top_ports:
            s = socket.socket()
            s.settimeout(0.4)
            try:
                if s.connect_ex((ip,p)) == 0:
                    print(Fore.GREEN + f"[OPEN] {p}")
            except Exception:
                pass
            s.close()

    def reload_plugins(self):
        load_plugins(self)
        print("Plugins loaded:", list_plugins())

    def execute_single_command(self, cmdline):
        import io
        import sys
        old_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        try:
            parts = cmdline.split()
            if not parts:
                return ""
            cmd = parts[0].lower()
            if cmd == "help":
                print(Fore.CYAN + "=== DevilShell Commands ===")
                print(Fore.GREEN + "Available commands (sorted alphabetically):")
                unique_commands = sorted(set(BUILTIN_COMMANDS))
                for cmd_name in unique_commands:
                    usage = COMMAND_USAGES.get(cmd_name, "No usage available")
                    print(f"  {cmd_name}: {usage}")
                print(Fore.YELLOW + "\nTip: Use tab for autocomplete, or type any OS command directly.")
                print(Style.RESET_ALL)
            elif cmd == "exit":
                print("Exit command not available in single mode.")
            elif cmd == "clear":
                print("Screen cleared.")  # Simulate
            elif cmd == "time":
                print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            elif cmd == "sysinfo":
                print("OS:", platform.system(), platform.release())
                print("CPU:", platform.processor())
                print("PWD:", os.getcwd())
            elif cmd == "echo":
                print(" ".join(parts[1:]))
            elif cmd == "ls":
                print("\n".join(os.listdir()))
            elif cmd == "cd":
                if len(parts) > 1:
                    try:
                        os.chdir(parts[1])
                        print(f"Changed to {os.getcwd()}")
                    except Exception as e:
                        print("cd error:", e)
                else:
                    print(os.getcwd())
            elif cmd == "calc":
                try:
                    expr = input("calc> ")  # But in single mode, can't input, so skip or error
                    print("Calc not supported in single command mode.")
                except:
                    print("Calc error.")
            elif cmd == "ip":
                self.show_ip()
            elif cmd == "ping":
                if len(parts) > 1:
                    target = parts[1]
                    try:
                        result = subprocess.run(f"ping -c 4 {target}" if os.name != "nt" else f"ping {target}", shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print(f"ping error: {e}")
                else:
                    print("Usage: ping <host>")
            elif cmd == "run":
                if len(parts) > 1:
                    self.run_python(parts[1])
                else:
                    print("run <file.py>")
            elif cmd == "edit":
                print("Edit not supported in web mode.")
            elif cmd == "scan":
                if len(parts) > 1:
                    self.port_scan(parts[1])
                else:
                    print("scan <host>")
            elif cmd == "install":
                if len(parts) > 1:
                    self.install_pkg(parts[1])
                else:
                    print("install <pkg>")
            elif cmd == "tool-install":
                if len(parts) > 1:
                    self.install_tool(parts[1])
                else:
                    print("tool-install <tool>")
            elif cmd == "logs":
                self.show_logs()
            elif cmd == "passwd":
                print("Password change not supported in web mode.")
            elif cmd == "theme":
                if len(parts) == 1:
                    print("theme list | theme set <X/Y/Z>")
                elif parts[1] == "list":
                    print("Available themes:", ", ".join(BANNERS.keys()))
                elif parts[1] == "set" and len(parts) > 2:
                    self.set_theme(parts[2])
                else:
                    print("Invalid theme command.")
            elif cmd == "plugin":
                if len(parts) == 1:
                    print("plugin list | plugin reload")
                elif parts[1] == "list":
                    print("Loaded:", list_plugins())
                elif parts[1] == "reload":
                    self.reload_plugins()
                else:
                    print("Unknown plugin command.")
            elif cmd == "encrypt":
                print("Encrypt not supported in web mode.")
            elif cmd == "decrypt":
                print("Decrypt not supported in web mode.")
            elif cmd == "dir":
                try:
                    files = os.listdir(".")
                    for f in files:
                        print(f)
                except Exception as e:
                    print("dir error:", e)
            elif cmd == "cls":
                print("Screen cleared.")
            elif cmd == "copy":
                if len(parts) >= 3:
                    src, dst = parts[1], parts[2]
                    try:
                        import shutil
                        shutil.copy(src, dst)
                        print(f"Copied {src} to {dst}")
                    except Exception as e:
                        print("copy error:", e)
                else:
                    print("copy <src> <dst>")
            elif cmd == "del":
                if len(parts) > 1:
                    for f in parts[1:]:
                        try:
                            os.remove(f)
                            print(f"Deleted {f}")
                        except Exception as e:
                            print(f"del error for {f}:", e)
                else:
                    print("del <file1> [file2] ...")
            elif cmd == "mkdir":
                if len(parts) > 1:
                    try:
                        os.mkdir(parts[1])
                        print(f"Created directory {parts[1]}")
                    except Exception as e:
                        print("mkdir error:", e)
                else:
                    print("mkdir <dir>")
            elif cmd == "rmdir":
                if len(parts) > 1:
                    try:
                        os.rmdir(parts[1])
                        print(f"Removed directory {parts[1]}")
                    except Exception as e:
                        print("rmdir error:", e)
                else:
                    print("rmdir <dir>")
            elif cmd == "type":
                if len(parts) > 1:
                    try:
                        with open(parts[1], "r") as f:
                            print(f.read())
                    except Exception as e:
                        print("type error:", e)
                else:
                    print("type <file>")
            elif cmd == "find":
                if len(parts) > 1:
                    pattern = parts[1]
                    try:
                        import fnmatch
                        for root, dirs, files in os.walk("."):
                            for f in files:
                                if fnmatch.fnmatch(f, pattern):
                                    print(os.path.join(root, f))
                    except Exception as e:
                        print("find error:", e)
                else:
                    print("find <pattern>")
            elif cmd == "findstr":
                if len(parts) >= 3:
                    string, file = parts[1], parts[2]
                    try:
                        with open(file, "r") as f:
                            lines = f.readlines()
                            for i, line in enumerate(lines, 1):
                                if string in line:
                                    print(f"{file}:{i}:{line.strip()}")
                    except Exception as e:
                        print("findstr error:", e)
                else:
                    print("findstr <string> <file>")
            elif cmd == "tasklist":
                try:
                    result = subprocess.run("tasklist" if os.name == "nt" else "ps aux", shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("tasklist error:", e)
            elif cmd == "taskkill":
                if len(parts) > 1:
                    pid = parts[1]
                    try:
                        result = subprocess.run(f"taskkill /PID {pid} /F" if os.name == "nt" else f"kill -9 {pid}", shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("taskkill error:", e)
                else:
                    print("taskkill <pid>")
            elif cmd == "shutdown":
                print("Shutdown not allowed in web mode.")
            elif cmd == "set":
                if len(parts) == 1:
                    for k, v in os.environ.items():
                        print(f"{k}={v}")
                elif len(parts) >= 3:
                    var, val = parts[1], " ".join(parts[2:])
                    os.environ[var] = val
                    print(f"Set {var}={val}")
                else:
                    print("set [VAR=VALUE]")
            elif cmd == "path":
                print(os.environ.get("PATH", ""))
            elif cmd == "pwd":
                print(os.getcwd())
            elif cmd == "mv":
                if len(parts) >= 3:
                    src, dst = parts[1], parts[2]
                    try:
                        import shutil
                        shutil.move(src, dst)
                        print(f"Moved {src} to {dst}")
                    except Exception as e:
                        print("mv error:", e)
                else:
                    print("mv <src> <dst>")
            elif cmd == "touch":
                if len(parts) > 1:
                    try:
                        open(parts[1], 'a').close()
                        print(f"Touched {parts[1]}")
                    except Exception as e:
                        print("touch error:", e)
                else:
                    print("touch <file>")
            elif cmd == "ln":
                if len(parts) >= 3:
                    target, link = parts[1], parts[2]
                    try:
                        os.symlink(target, link)
                        print(f"Linked {link} -> {target}")
                    except Exception as e:
                        print("ln error:", e)
                else:
                    print("ln <target> <link>")
            elif cmd == "man":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("man " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("man error:", e)
                else:
                    print("man <command>")
            elif cmd == "uname":
                print(platform.uname())
            elif cmd == "whoami":
                print(getpass.getuser())
            elif cmd == "head":
                if len(parts) > 1:
                    file = parts[1]
                    n = 10
                    if len(parts) > 2 and parts[2].isdigit():
                        n = int(parts[2])
                    try:
                        with open(file, "r") as f:
                            lines = f.readlines()[:n]
                            print("".join(lines))
                    except Exception as e:
                        print("head error:", e)
                else:
                    print("head <file> [n]")
            elif cmd == "tail":
                if len(parts) > 1:
                    file = parts[1]
                    n = 10
                    if len(parts) > 2 and parts[2].isdigit():
                        n = int(parts[2])
                    try:
                        with open(file, "r") as f:
                            lines = f.readlines()[-n:]
                            print("".join(lines))
                    except Exception as e:
                        print("tail error:", e)
                else:
                    print("tail <file> [n]")
            elif cmd == "diff":
                if len(parts) >= 3:
                    try:
                        result = subprocess.run("diff " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("diff error:", e)
                else:
                    print("diff <file1> <file2>")
            elif cmd == "comm":
                if len(parts) >= 3:
                    try:
                        result = subprocess.run("comm " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("comm error:", e)
                else:
                    print("comm <file1> <file2>")
            elif cmd == "cmp":
                if len(parts) >= 3:
                    try:
                        result = subprocess.run("cmp " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("cmp error:", e)
                else:
                    print("cmp <file1> <file2>")
            elif cmd == "sort":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("sort " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("sort error:", e)
                else:
                    print("sort <file>")
            elif cmd == "export":
                if len(parts) >= 2:
                    var_val = " ".join(parts[1:])
                    if "=" in var_val:
                        var, val = var_val.split("=", 1)
                        os.environ[var] = val
                        print(f"Exported {var}={val}")
                    else:
                        print("export VAR=VALUE")
                else:
                    print("export VAR=VALUE")
            elif cmd == "ssh":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("ssh " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("ssh error:", e)
                else:
                    print("ssh <user@host>")
            elif cmd == "service":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("service " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("service error:", e)
                else:
                    print("service <service> <action>")
            elif cmd == "df":
                try:
                    result = subprocess.run("df", shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("df error:", e)
            elif cmd == "mount":
                try:
                    result = subprocess.run("mount", shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("mount error:", e)
            elif cmd == "traceroute":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("traceroute " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("traceroute error:", e)
                else:
                    print("traceroute <host>")
            elif cmd == "ufw":
                try:
                    result = subprocess.run("ufw " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("ufw error:", e)
            elif cmd == "iptables":
                try:
                    result = subprocess.run("iptables " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("iptables error:", e)
            elif cmd == "sudo":
                print("Sudo not supported in web mode.")
            elif cmd == "sudosu":
                print("Sudosu not supported in web mode.")
            elif cmd == "cal":
                try:
                    result = subprocess.run("cal " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("cal error:", e)
            elif cmd == "alias":
                if len(parts) == 1:
                    print("Aliases: (not implemented yet)")
                else:
                    print("alias <name>=<command> (not implemented yet)")
            elif cmd == "dd":
                try:
                    result = subprocess.run("dd " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("dd error:", e)
            elif cmd == "whereis":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("whereis " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("whereis error:", e)
                else:
                    print("whereis <command>")
            elif cmd == "whatis":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("whatis " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("whatis error:", e)
                else:
                    print("whatis <command>")
            elif cmd == "top":
                try:
                    result = subprocess.run("top", shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("top error:", e)
            elif cmd == "useradd":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("useradd " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("useradd error:", e)
                else:
                    print("useradd <username>")
            elif cmd == "usermod":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("usermod " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("usermod error:", e)
                else:
                    print("usermod <options> <username>")
            elif cmd == "less":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("less " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("less not available, using cat instead.")
                        if len(parts) > 1:
                            try:
                                with open(parts[1], "r") as f:
                                    print(f.read())
                            except Exception as e:
                                print("cat error:", e)
                else:
                    print("less <file>")
            elif cmd == "killall":
                if len(parts) > 1:
                    name = parts[1]
                    try:
                        result = subprocess.run(f"killall {name}", shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("killall error:", e)
                else:
                    print("killall <process_name>")
            elif cmd == "pacman":
                try:
                    result = subprocess.run("pacman " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("pacman error:", e)
            elif cmd == "yum":
                try:
                    result = subprocess.run("yum " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("yum error:", e)
            elif cmd == "rpm":
                try:
                    result = subprocess.run("rpm " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("rpm error:", e)
            elif cmd == "cp":
                if len(parts) >= 3:
                    src, dst = parts[1], parts[2]
                    try:
                        import shutil
                        shutil.copy(src, dst)
                        print(f"Copied {src} to {dst}")
                    except Exception as e:
                        print("cp error:", e)
                else:
                    print("cp <src> <dst>")
            elif cmd == "rm":
                if len(parts) > 1:
                    for f in parts[1:]:
                        try:
                            os.remove(f)
                            print(f"Deleted {f}")
                        except Exception as e:
                            print(f"rm error for {f}:", e)
                else:
                    print("rm <file1> [file2] ...")
            elif cmd == "cat":
                if len(parts) > 1:
                    try:
                        with open(parts[1], "r") as f:
                            print(f.read())
                    except Exception as e:
                        print("cat error:", e)
                else:
                    print("cat <file>")
            elif cmd == "ifconfig":
                try:
                    cmd_to_run = "ipconfig" if os.name == "nt" else "ifconfig"
                    result = subprocess.run(cmd_to_run, shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("ifconfig error:", e)
            elif cmd == "wget":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("wget " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("wget error:", e)
                else:
                    print("wget <url>")
            elif cmd == "curl":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("curl " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("curl error:", e)
                else:
                    print("curl <url>")
            elif cmd == "htop":
                try:
                    result = subprocess.run("htop", shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("htop error:", e)
            elif cmd == "ps":
                try:
                    result = subprocess.run("ps aux", shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print("ps error:", e)
            elif cmd == "kill":
                if len(parts) > 1:
                    pid = parts[1]
                    try:
                        result = subprocess.run(f"kill -9 {pid}", shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("kill error:", e)
                else:
                    print("kill <pid>")
            elif cmd == "grep":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("grep " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("grep error:", e)
                else:
                    print("grep <pattern>")
            elif cmd == "tar":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("tar " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("tar error:", e)
                else:
                    print("tar <options>")
            elif cmd == "unzip":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("unzip " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("unzip error:", e)
                else:
                    print("unzip <file>")
            elif cmd == "zip":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("zip " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("zip error:", e)
                else:
                    print("zip <file>")
            elif cmd == "chmod":
                if len(parts) > 2:
                    try:
                        result = subprocess.run("chmod " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("chmod error:", e)
                else:
                    print("chmod <mode> <file>")
            elif cmd == "chown":
                if len(parts) > 2:
                    try:
                        result = subprocess.run("chown " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("chown error:", e)
                else:
                    print("chown <user> <file>")
            elif cmd == "sed":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("sed " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("sed error:", e)
                else:
                    print("sed <expression>")
            elif cmd == "awk":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("awk " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("awk error:", e)
                else:
                    print("awk <program>")
            elif cmd == "git":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("git " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("git error:", e)
                else:
                    print("git <command>")
            elif cmd == "nano":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("nano " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("nano error:", e)
                else:
                    print("nano <file>")
            elif cmd == "vim":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("vim " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("vim error:", e)
                else:
                    print("vim <file>")
            elif cmd == "apt":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("apt " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("apt error:", e)
                else:
                    print("apt <command>")
            elif cmd == "pkg":
                if len(parts) > 1:
                    try:
                        result = subprocess.run("pkg " + " ".join(parts[1:]), shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("pkg error:", e)
                else:
                    print("pkg <command>")
            else:
                # fallback to OS shell
                try:
                    result = subprocess.run(cmdline, shell=True, capture_output=True, text=True)
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                except FileNotFoundError:
                    if cmd == "nmap":
                        print("nmap is not installed. Please install it from https://nmap.org/download.html or use 'tool-install nmap' in shell mode.")
                    else:
                        print("Command not found:", cmd)
                except Exception as e:
                    print("Command error:", e)
        except Exception as e:
            print("Error executing command:", e)
        finally:
            sys.stdout = old_stdout
        return captured_output.getvalue()

    def run_python(self, file):
        if not os.path.exists(file):
            print("File not found.")
            return
        try:
            result = subprocess.run(f"python {file}", shell=True, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
        except Exception as e:
            print(f"Error running Python file: {e}")

    def edit_file(self, file):
        # prefer nano on unix; on Windows try notepad or code
        if os.name == "nt":
            # try code, then notepad
            if shutil_which("code"):
                try:
                    result = subprocess.run(f'code "{file}"', shell=True, capture_output=True, text=True)
                    print(result.stdout if result.stdout else "Code editor opened")
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print(f"Error opening code: {e}")
            else:
                try:
                    result = subprocess.run(f'notepad "{file}"', shell=True, capture_output=True, text=True)
                    print(result.stdout if result.stdout else "Notepad opened")
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print(f"Error opening notepad: {e}")
        else:
            # unix: prefer nano, else vi
            if shutil_which("nano"):
                try:
                    result = subprocess.run(f"nano {file}", shell=True, capture_output=True, text=True)
                    print(result.stdout if result.stdout else "Nano editor opened")
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print(f"Error opening nano: {e}")
            elif shutil_which("vi"):
                try:
                    result = subprocess.run(f"vi {file}", shell=True, capture_output=True, text=True)
                    print(result.stdout if result.stdout else "Vi editor opened")
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print(f"Error opening vi: {e}")
            else:
                # fallback to opening with default editor via xdg-open
                try:
                    result = subprocess.run(f"xdg-open {file}", shell=True, capture_output=True, text=True)
                    print(result.stdout if result.stdout else "File opened with default editor")
                    if result.stderr:
                        print(result.stderr)
                except Exception as e:
                    print(f"Error opening file: {e}")

    def install_pkg(self, pkg):
        try:
            result = subprocess.run(f"pip install {pkg}", shell=True, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
        except Exception as e:
            print(f"Error installing package: {e}")

    def install_tool(self, tool):
        system = platform.system().lower()
        if system == "linux":
            # Assume apt for Debian-based systems like Kali
            cmd = f"apt install {tool}"
            print(Fore.YELLOW + f"Installing {tool} using apt...")
        elif system == "darwin":  # macOS
            cmd = f"brew install {tool}"
            print(Fore.YELLOW + f"Installing {tool} using brew...")
        elif system == "windows":
            cmd = f"winget install {tool}"
            print(Fore.YELLOW + f"Installing {tool} using winget...")
        else:
            print(Fore.RED + f"Unsupported OS: {system}")
            return
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(Fore.GREEN + f"Successfully installed {tool}")
            else:
                print(Fore.RED + f"Failed to install {tool}. Error: {result.stderr}")
                if "permission" in result.stderr.lower() or "sudo" in result.stderr.lower():
                    print(Fore.YELLOW + "Try using 'sudo apt install' or run as administrator.")
        except Exception as e:
            print(Fore.RED + f"Error installing {tool}: {e}")

    def show_logs(self):
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                print(f.read())
        else:
            print("No logs yet.")

    def show_ip(self):
        cmd = "ipconfig" if os.name == "nt" else "ifconfig"
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
        except Exception as e:
            print(f"IP command error: {e}")

    def port_scan_command(self, target):
        self.port_scan(target)

    def loop(self):
        print_banner(self.theme)
        init_history()
        try:
            while True:
                try:
                    prompt_symbol = "#" if self.current_user == "admin" else "$"
                    prompt = Fore.GREEN + f"{self.current_user or 'anon'}@{SHELL_NAME}:{os.getcwd()}{prompt_symbol} " + Style.RESET_ALL
                    cmdline = input(prompt).strip()
                except (KeyboardInterrupt, EOFError):
                    print()
                    cmdline = "exit"

                if cmdline == "":
                    continue
                log_cmd(self.current_user, cmdline)

                parts = cmdline.split()
                cmd = parts[0].lower()

                if cmd == "help":
                    print(Fore.CYAN + "=== DevilShell Commands ===")
                    print(Fore.GREEN + "Available commands (sorted alphabetically):")
                    unique_commands = sorted(set(BUILTIN_COMMANDS))
                    for cmd_name in unique_commands:
                        usage = COMMAND_USAGES.get(cmd_name, "No usage available")
                        print(f"  {cmd_name}: {usage}")
                    print(Fore.YELLOW + "\nTip: Use tab for autocomplete, or type any OS command directly.")
                    print(Style.RESET_ALL)
                elif cmd == "exit":
                    break
                elif cmd == "clear":
                    os.system("cls" if os.name == "nt" else "clear")
                elif cmd == "time":
                    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                elif cmd == "sysinfo":
                    print("OS:", platform.system(), platform.release())
                    print("CPU:", platform.processor())
                    print("PWD:", os.getcwd())
                elif cmd == "echo":
                    print(" ".join(parts[1:]))
                elif cmd == "ls":
                    print("\n".join(os.listdir()))
                elif cmd == "cd":
                    if len(parts) > 1:
                        try:
                            os.chdir(parts[1])
                        except Exception as e:
                            print("cd error:", e)
                    else:
                        print(os.getcwd())
                elif cmd == "calc":
                    try:
                        expr = input("calc> ")
                        print("=", eval(expr))
                    except Exception as e:
                        print("Calc error:", e)
                elif cmd == "ip":
                    self.show_ip()
                elif cmd == "ping":
                    if len(parts) > 1:
                        target = parts[1]
                        subprocess.run(f"ping -c 4 {target}" if os.name != "nt" else f"ping {target}", shell=True)
                    else:
                        print("Usage: ping <host>")
                elif cmd == "run":
                    if len(parts) > 1:
                        self.run_python(parts[1])
                    else:
                        print("run <file.py>")
                elif cmd == "edit":
                    if len(parts) > 1:
                        self.edit_file(parts[1])
                    else:
                        print("edit <file>")
                elif cmd == "scan":
                    if len(parts) > 1:
                        self.port_scan(parts[1])
                    else:
                        print("scan <host>")
                elif cmd == "install":
                    if len(parts) > 1:
                        self.install_pkg(parts[1])
                    else:
                        print("install <pkg>")
                elif cmd == "tool-install":
                    if len(parts) > 1:
                        self.install_tool(parts[1])
                    else:
                        print("tool-install <tool>")
                elif cmd == "logs":
                    self.show_logs()
                elif cmd == "passwd":
                    self.change_password()
                elif cmd == "theme":
                    if len(parts) == 1:
                        print("theme list | theme set <X/Y/Z>")
                    elif parts[1] == "list":
                        print("Available themes:", ", ".join(BANNERS.keys()))
                    elif parts[1] == "set" and len(parts) > 2:
                        self.set_theme(parts[2])
                    else:
                        print("Invalid theme command.")
                elif cmd == "plugin":
                    if len(parts) == 1:
                        print("plugin list | plugin reload")
                    elif parts[1] == "list":
                        print("Loaded:", list_plugins())
                    elif parts[1] == "reload":
                        self.reload_plugins()
                    else:
                        print("Unknown plugin command.")
                elif cmd == "encrypt":
                    if len(parts) > 1:
                        self.encrypt_file(parts[1])
                    else:
                        print("encrypt <file>")
                elif cmd == "decrypt":
                    if len(parts) > 1:
                        self.decrypt_file(parts[1])
                    else:
                        print("decrypt <file.enc>")
                elif cmd == "dir":
                    # Windows dir command, similar to ls
                    try:
                        files = os.listdir(".")
                        for f in files:
                            print(f)
                    except Exception as e:
                        print("dir error:", e)
                elif cmd == "cls":
                    # Clear screen, same as clear
                    os.system("cls" if os.name == "nt" else "clear")
                elif cmd == "copy":
                    if len(parts) >= 3:
                        src, dst = parts[1], parts[2]
                        try:
                            import shutil
                            shutil.copy(src, dst)
                            print(f"Copied {src} to {dst}")
                        except Exception as e:
                            print("copy error:", e)
                    else:
                        print("copy <src> <dst>")
                elif cmd == "del":
                    if len(parts) > 1:
                        for f in parts[1:]:
                            try:
                                os.remove(f)
                                print(f"Deleted {f}")
                            except Exception as e:
                                print(f"del error for {f}:", e)
                    else:
                        print("del <file1> [file2] ...")
                elif cmd == "mkdir":
                    if len(parts) > 1:
                        try:
                            os.mkdir(parts[1])
                            print(f"Created directory {parts[1]}")
                        except Exception as e:
                            print("mkdir error:", e)
                    else:
                        print("mkdir <dir>")
                elif cmd == "rmdir":
                    if len(parts) > 1:
                        try:
                            os.rmdir(parts[1])
                            print(f"Removed directory {parts[1]}")
                        except Exception as e:
                            print("rmdir error:", e)
                    else:
                        print("rmdir <dir>")
                elif cmd == "type":
                    if len(parts) > 1:
                        try:
                            with open(parts[1], "r") as f:
                                print(f.read())
                        except Exception as e:
                            print("type error:", e)
                    else:
                        print("type <file>")
                elif cmd == "find":
                    if len(parts) > 1:
                        pattern = parts[1]
                        try:
                            import fnmatch
                            for root, dirs, files in os.walk("."):
                                for f in files:
                                    if fnmatch.fnmatch(f, pattern):
                                        print(os.path.join(root, f))
                        except Exception as e:
                            print("find error:", e)
                    else:
                        print("find <pattern>")
                elif cmd == "findstr":
                    if len(parts) >= 3:
                        string, file = parts[1], parts[2]
                        try:
                            with open(file, "r") as f:
                                lines = f.readlines()
                                for i, line in enumerate(lines, 1):
                                    if string in line:
                                        print(f"{file}:{i}:{line.strip()}")
                        except Exception as e:
                            print("findstr error:", e)
                    else:
                        print("findstr <string> <file>")
                elif cmd == "tasklist":
                    try:
                        subprocess.run("tasklist" if os.name == "nt" else "ps aux", shell=True)
                    except Exception as e:
                        print("tasklist error:", e)
                elif cmd == "taskkill":
                    if len(parts) > 1:
                        pid = parts[1]
                        try:
                            subprocess.run(f"taskkill /PID {pid} /F" if os.name == "nt" else f"kill -9 {pid}", shell=True)
                        except Exception as e:
                            print("taskkill error:", e)
                    else:
                        print("taskkill <pid>")
                elif cmd == "shutdown":
                    confirm = input("Shutdown system? (y/n): ").lower()
                    if confirm == "y":
                        try:
                            subprocess.run("shutdown /s /t 0" if os.name == "nt" else "shutdown now", shell=True)
                        except Exception as e:
                            print("shutdown error:", e)
                    else:
                        print("Shutdown cancelled.")
                elif cmd == "set":
                    if len(parts) == 1:
                        for k, v in os.environ.items():
                            print(f"{k}={v}")
                    elif len(parts) >= 3:
                        var, val = parts[1], " ".join(parts[2:])
                        os.environ[var] = val
                        print(f"Set {var}={val}")
                    else:
                        print("set [VAR=VALUE]")
                elif cmd == "path":
                    print(os.environ.get("PATH", ""))
                elif cmd == "pwd":
                    print(os.getcwd())
                elif cmd == "mv":
                    if len(parts) >= 3:
                        src, dst = parts[1], parts[2]
                        try:
                            import shutil
                            shutil.move(src, dst)
                            print(f"Moved {src} to {dst}")
                        except Exception as e:
                            print("mv error:", e)
                    else:
                        print("mv <src> <dst>")
                elif cmd == "touch":
                    if len(parts) > 1:
                        try:
                            open(parts[1], 'a').close()
                            print(f"Touched {parts[1]}")
                        except Exception as e:
                            print("touch error:", e)
                    else:
                        print("touch <file>")
                elif cmd == "ln":
                    if len(parts) >= 3:
                        target, link = parts[1], parts[2]
                        try:
                            os.symlink(target, link)
                            print(f"Linked {link} -> {target}")
                        except Exception as e:
                            print("ln error:", e)
                    else:
                        print("ln <target> <link>")
                elif cmd == "man":
                    if len(parts) > 1:
                        try:
                            subprocess.run("man " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("man error:", e)
                    else:
                        print("man <command>")
                elif cmd == "uname":
                    print(platform.uname())
                elif cmd == "whoami":
                    print(getpass.getuser())
                elif cmd == "head":
                    if len(parts) > 1:
                        file = parts[1]
                        n = 10
                        if len(parts) > 2 and parts[2].isdigit():
                            n = int(parts[2])
                        try:
                            with open(file, "r") as f:
                                lines = f.readlines()[:n]
                                print("".join(lines))
                        except Exception as e:
                            print("head error:", e)
                    else:
                        print("head <file> [n]")
                elif cmd == "tail":
                    if len(parts) > 1:
                        file = parts[1]
                        n = 10
                        if len(parts) > 2 and parts[2].isdigit():
                            n = int(parts[2])
                        try:
                            with open(file, "r") as f:
                                lines = f.readlines()[-n:]
                                print("".join(lines))
                        except Exception as e:
                            print("tail error:", e)
                    else:
                        print("tail <file> [n]")
                elif cmd == "diff":
                    if len(parts) >= 3:
                        try:
                            subprocess.run("diff " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("diff error:", e)
                    else:
                        print("diff <file1> <file2>")
                elif cmd == "comm":
                    if len(parts) >= 3:
                        try:
                            subprocess.run("comm " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("comm error:", e)
                    else:
                        print("comm <file1> <file2>")
                elif cmd == "cmp":
                    if len(parts) >= 3:
                        try:
                            subprocess.run("cmp " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("cmp error:", e)
                    else:
                        print("cmp <file1> <file2>")
                elif cmd == "sort":
                    if len(parts) > 1:
                        try:
                            subprocess.run("sort " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("sort error:", e)
                    else:
                        print("sort <file>")
                elif cmd == "export":
                    if len(parts) >= 2:
                        var_val = " ".join(parts[1:])
                        if "=" in var_val:
                            var, val = var_val.split("=", 1)
                            os.environ[var] = val
                            print(f"Exported {var}={val}")
                        else:
                            print("export VAR=VALUE")
                    else:
                        print("export VAR=VALUE")
                elif cmd == "ssh":
                    if len(parts) > 1:
                        try:
                            subprocess.run("ssh " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("ssh error:", e)
                    else:
                        print("ssh <user@host>")
                elif cmd == "service":
                    if len(parts) > 1:
                        try:
                            subprocess.run("service " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("service error:", e)
                    else:
                        print("service <service> <action>")
                elif cmd == "df":
                    try:
                        subprocess.run("df", shell=True)
                    except Exception as e:
                        print("df error:", e)
                elif cmd == "mount":
                    try:
                        subprocess.run("mount", shell=True)
                    except Exception as e:
                        print("mount error:", e)
                elif cmd == "traceroute":
                    if len(parts) > 1:
                        try:
                            subprocess.run("traceroute " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("traceroute error:", e)
                    else:
                        print("traceroute <host>")
                elif cmd == "ufw":
                    try:
                        subprocess.run("ufw " + " ".join(parts[1:]), shell=True)
                    except Exception as e:
                        print("ufw error:", e)
                elif cmd == "iptables":
                    try:
                        subprocess.run("iptables " + " ".join(parts[1:]), shell=True)
                    except Exception as e:
                        print("iptables error:", e)
                elif cmd == "sudo":
                    if len(parts) < 2:
                        print("sudo <command>")
                        continue
                    if parts[1] == "-su":
                        if self.current_user == "admin":
                            print("Already root.")
                        else:
                            admin_pwd = getpass.getpass("Admin password: ")
                            if verify_password(admin_pwd, self.users["admin"]["salt"], self.users["admin"]["hash"]):
                                self.current_user = "admin"
                                print(Fore.GREEN + "Switched to root. You now have full permissions.")
                            else:
                                print(Fore.RED + "Incorrect admin password.")
                    else:
                        if self.current_user == "admin":
                            try:
                                subprocess.run(" ".join(parts[1:]), shell=True)
                            except Exception as e:
                                print("sudo error:", e)
                        else:
                            admin_pwd = getpass.getpass("Admin password: ")
                            if verify_password(admin_pwd, self.users["admin"]["salt"], self.users["admin"]["hash"]):
                                try:
                                    subprocess.run(" ".join(parts[1:]), shell=True)
                                except Exception as e:
                                    print("sudo error:", e)
                            else:
                                print(Fore.RED + "Incorrect admin password.")
                elif cmd == "sudosu":
                    if self.current_user == "admin":
                        print("Already root.")
                    else:
                        admin_pwd = getpass.getpass("Admin password: ")
                        if verify_password(admin_pwd, self.users["admin"]["salt"], self.users["admin"]["hash"]):
                            self.current_user = "admin"
                            print(Fore.GREEN + "Switched to root. You now have full permissions.")
                        else:
                            print(Fore.RED + "Incorrect admin password.")
                elif cmd == "cal":
                    try:
                        subprocess.run("cal " + " ".join(parts[1:]), shell=True)
                    except Exception as e:
                        print("cal error:", e)
                elif cmd == "alias":
                    if len(parts) == 1:
                        print("Aliases: (not implemented yet)")
                    else:
                        print("alias <name>=<command> (not implemented yet)")
                elif cmd == "dd":
                    try:
                        subprocess.run("dd " + " ".join(parts[1:]), shell=True)
                    except Exception as e:
                        print("dd error:", e)
                elif cmd == "whereis":
                    if len(parts) > 1:
                        try:
                            subprocess.run("whereis " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("whereis error:", e)
                    else:
                        print("whereis <command>")
                elif cmd == "whatis":
                    if len(parts) > 1:
                        try:
                            subprocess.run("whatis " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("whatis error:", e)
                    else:
                        print("whatis <command>")
                elif cmd == "top":
                    try:
                        subprocess.run("top", shell=True)
                    except Exception as e:
                        print("top error:", e)
                elif cmd == "useradd":
                    if len(parts) > 1:
                        try:
                            subprocess.run("useradd " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("useradd error:", e)
                    else:
                        print("useradd <username>")
                elif cmd == "usermod":
                    if len(parts) > 1:
                        try:
                            subprocess.run("usermod " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("usermod error:", e)
                    else:
                        print("usermod <options> <username>")
                elif cmd == "less":
                    if len(parts) > 1:
                        try:
                            subprocess.run("less " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("less not available, using cat instead.")
                            if len(parts) > 1:
                                try:
                                    with open(parts[1], "r") as f:
                                        print(f.read())
                                except Exception as e:
                                    print("cat error:", e)
                    else:
                        print("less <file>")
                elif cmd == "killall":
                    if len(parts) > 1:
                        name = parts[1]
                        try:
                            subprocess.run(f"killall {name}", shell=True)
                        except Exception as e:
                            print("killall error:", e)
                    else:
                        print("killall <process_name>")
                elif cmd == "pacman":
                    try:
                        subprocess.run("pacman " + " ".join(parts[1:]), shell=True)
                    except Exception as e:
                        print("pacman error:", e)
                elif cmd == "yum":
                    try:
                        subprocess.run("yum " + " ".join(parts[1:]), shell=True)
                    except Exception as e:
                        print("yum error:", e)
                elif cmd == "rpm":
                    try:
                        subprocess.run("rpm " + " ".join(parts[1:]), shell=True)
                    except Exception as e:
                        print("rpm error:", e)
                elif cmd == "cp":
                    if len(parts) >= 3:
                        src, dst = parts[1], parts[2]
                        try:
                            import shutil
                            shutil.copy(src, dst)
                            print(f"Copied {src} to {dst}")
                        except Exception as e:
                            print("cp error:", e)
                    else:
                        print("cp <src> <dst>")
                elif cmd == "rm":
                    if len(parts) > 1:
                        for f in parts[1:]:
                            try:
                                os.remove(f)
                                print(f"Deleted {f}")
                            except Exception as e:
                                print(f"rm error for {f}:", e)
                    else:
                        print("rm <file1> [file2] ...")
                elif cmd == "cat":
                    if len(parts) > 1:
                        try:
                            with open(parts[1], "r") as f:
                                print(f.read())
                        except Exception as e:
                            print("cat error:", e)
                    else:
                        print("cat <file>")
                elif cmd == "ifconfig":
                    try:
                        cmd_to_run = "ipconfig" if os.name == "nt" else "ifconfig"
                        subprocess.run(cmd_to_run, shell=True)
                    except Exception as e:
                        print("ifconfig error:", e)
                elif cmd == "wget":
                    if len(parts) > 1:
                        try:
                            subprocess.run("wget " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("wget error:", e)
                    else:
                        print("wget <url>")
                elif cmd == "curl":
                    if len(parts) > 1:
                        try:
                            subprocess.run("curl " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("curl error:", e)
                    else:
                        print("curl <url>")
                elif cmd == "htop":
                    try:
                        subprocess.run("htop", shell=True)
                    except Exception as e:
                        print("htop error:", e)
                elif cmd == "ps":
                    try:
                        subprocess.run("ps aux", shell=True)
                    except Exception as e:
                        print("ps error:", e)
                elif cmd == "kill":
                    if len(parts) > 1:
                        pid = parts[1]
                        try:
                            subprocess.run(f"kill -9 {pid}", shell=True)
                        except Exception as e:
                            print("kill error:", e)
                    else:
                        print("kill <pid>")
                elif cmd == "grep":
                    if len(parts) > 1:
                        try:
                            subprocess.run("grep " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("grep error:", e)
                    else:
                        print("grep <pattern>")
                elif cmd == "tar":
                    if len(parts) > 1:
                        try:
                            subprocess.run("tar " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("tar error:", e)
                    else:
                        print("tar <options>")
                elif cmd == "unzip":
                    if len(parts) > 1:
                        try:
                            subprocess.run("unzip " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("unzip error:", e)
                    else:
                        print("unzip <file>")
                elif cmd == "zip":
                    if len(parts) > 1:
                        try:
                            subprocess.run("zip " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("zip error:", e)
                    else:
                        print("zip <file>")
                elif cmd == "chmod":
                    if len(parts) > 2:
                        try:
                            subprocess.run("chmod " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("chmod error:", e)
                    else:
                        print("chmod <mode> <file>")
                elif cmd == "chown":
                    if len(parts) > 2:
                        try:
                            subprocess.run("chown " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("chown error:", e)
                    else:
                        print("chown <user> <file>")
                elif cmd == "sed":
                    if len(parts) > 1:
                        try:
                            subprocess.run("sed " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("sed error:", e)
                    else:
                        print("sed <expression>")
                elif cmd == "awk":
                    if len(parts) > 1:
                        try:
                            subprocess.run("awk " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("awk error:", e)
                    else:
                        print("awk <program>")
                elif cmd == "git":
                    if len(parts) > 1:
                        try:
                            subprocess.run("git " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("git error:", e)
                    else:
                        print("git <command>")
                elif cmd == "nano":
                    if len(parts) > 1:
                        try:
                            subprocess.run("nano " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("nano error:", e)
                    else:
                        print("nano <file>")
                elif cmd == "vim":
                    if len(parts) > 1:
                        try:
                            subprocess.run("vim " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("vim error:", e)
                    else:
                        print("vim <file>")
                elif cmd == "apt":
                    if len(parts) > 1:
                        try:
                            subprocess.run("apt " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("apt error:", e)
                    else:
                        print("apt <command>")
                elif cmd == "pkg":
                    if len(parts) > 1:
                        try:
                            subprocess.run("pkg " + " ".join(parts[1:]), shell=True)
                        except Exception as e:
                            print("pkg error:", e)
                    else:
                        print("pkg <command>")
                else:
                    # fallback to OS shell
                    try:
                        result = subprocess.run(cmdline, shell=True, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except Exception as e:
                        print("Command error:", e)
        finally:
            save_history()
            print(Fore.YELLOW + "Session history saved.")
            print(Fore.RED + "Goodbye Devil! 👋")

# small helper for checking executables
def shutil_which(name):
    import shutil
    return shutil.which(name)

# Entrypoint
def main():
    shell = DevilShell()
    ok = shell.authenticate()
    if not ok:
        return
    print_banner(shell.theme)
    shell.loop()

if __name__ == "__main__":
    main()
