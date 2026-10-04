# SocketProject_CSEC201

Remote File Management Protocol (RFMP) is a client/server project for securely managing files inside a sandboxed `home/` directory. The server exposes a small command set for directory and file operations, while the Python client provides an interactive menu for sending those commands over TCP.

## Features

- Sandboxed file management rooted at `home/`
- Create, rename, delete, and list directories
- Create, read, write, and delete files
- Basic system queries such as `pwd`, `whoami`, `date`, and `ps`
- Optional secure communication mode
- Two secure algorithms supported for the session key exchange:
	- AES-256-GCM for encrypted file data
	- Caesar cipher for lightweight encrypted text
- Length-prefixed framed packets for reliable message exchange

## Project Files

- `ZayanZaid_server.py` - RFMP server implementation
- `ZayanZaid_client.py` - Python interactive client
- `ZayanZaid_client.c` and `ZayanZaid_cClient(windows).c` - C client variants
- `home/` - server sandbox directory used for all file operations

## Requirements

- Python 3.10 or newer
- `cryptography` Python package
- A local TCP connection between the client and server

## Installation

If you do not already have the dependency installed, run:

```bash
python -m pip install cryptography
```

If your system uses `python3`, you can substitute that command instead.

## Running the Server

Start the server from the project root:

```bash
python ZayanZaid_server.py
```

By default, the server listens on `127.0.0.1:9009`.

## Running the Client

In a second terminal, start the client:

```bash
python ZayanZaid_client.py
```

The client prompts for:

1. Server host and port, if provided on the command line
2. Whether to use secured communication
3. The encryption algorithm when secure mode is enabled

Example with explicit host and port:

```bash
python ZayanZaid_client.py 127.0.0.1 9009
```

## Client Menu

The interactive client supports the following actions:

- `mkdir` - create a directory
- `cd` - change directory
- `rmdir` - remove an empty directory
- `del` - delete a file
- `ren` - rename a file or directory
- `ls` - list items in the current directory
- `pwd` - print the current virtual directory
- `whoami` - show the current user name
- `date` - show the current date
- `ps` - show running processes
- `openRead` - read a file from the sandbox
- `openWrite` - write text into a file in the sandbox

## Secure Mode

When secure mode is enabled, the client and server perform an RSA-based key exchange during setup. After that:

- File contents sent with `openRead` are encrypted before transmission
- Text written with `openWrite` is encrypted before sending
- The server decrypts incoming data before saving it

AES mode uses a random 32-byte session key and AES-256-GCM for confidentiality and integrity. Caesar mode uses a random shift value from 1 to 25 and is intended mainly for coursework comparison, not real security.

## File Sandbox

All file operations are restricted to the `home/` directory next to the server script. The server checks paths so the client cannot escape that sandbox with `..` or absolute paths.

## Stopping the Program

- To close the client, choose `Quit` in the menu
- To stop the server, press `Ctrl+C` or `Ctrl+Fn+B` in the server terminal

## Notes

- The server uses length-prefixed frames to send and receive packets safely over TCP
- The server binds to `127.0.0.1` by default, so it is intended for local testing
- The repository also includes a line-by-line explanation file for coursework support

## Example Workflow

1. Start the server
2. Start the client
3. Choose secure or unsecured communication
4. Create or enter a directory
5. Use `openWrite` to create a file
6. Use `openRead` to verify the contents
7. Quit the client when finished
8. Stop the server with `Ctrl+C`

## Project Purpose

This project demonstrates:

- TCP client/server communication
- Custom packet framing
- Sandboxed filesystem access
- RSA key exchange
- Symmetric encryption for application data
- Basic command routing for file-management tasks

Made by Gautam, Zayan, Joshua and Snikitha.