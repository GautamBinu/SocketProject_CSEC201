# Line-by-Line Explanation — Client & Server

This document explains **every line** of both files: why it exists, what it does, and how it fits into the bigger picture. Written so you can explain it out loud to anyone.

---

# PART 1 — THE CLIENT ([JoshuaJCardoz_pyclient.py](file:///c:/Users/gauta/Downloads/chicken/SocketProject_CSEC201/JoshuaJCardoz_pyclient.py))

---

## Lines 1–6: Imports

```python
import socket as so
```
Imports Python's built-in socket library and renames it `so` to save typing. Sockets are the low-level API for sending and receiving data over TCP.

```python
import struct as st
```
Imports the `struct` module (renamed `st`). This module converts between Python values and C-style binary data. We use it to pack/unpack the 4-byte length header on every frame.

```python
import sys
```
Gives access to `sys.argv` — the command-line arguments. We use it to optionally accept a custom IP address and port when starting the client.

```python
import getpass                    # to get the OS username for the EC packet
```
The `getpass` module has a function `getuser()` that returns the current OS login name (e.g., "gauta"). We send this username to the server inside the EC packet during the secure handshake so the server knows who connected.

```python
import base64                     # needed to encode binary crypto data as text
```
Base64 encoding converts raw binary bytes (like encrypted keys or ciphertext) into a safe ASCII string that can travel inside our comma-separated text packets without breaking anything.

```python
import secrets                    # cryptographically secure random numbers
```
The `secrets` module generates random bytes and integers that are **cryptographically secure** — meaning they're truly unpredictable. We use it to generate AES session keys and Caesar shift values. (`random` module is NOT secure enough for crypto.)

---

## Lines 8–11: Crypto Library Imports

```python
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
```
From the `cryptography` pip package, import:
- `rsa` — functions to generate RSA key pairs
- `padding as asym_padding` — RSA padding schemes. We rename it `asym_padding` so it doesn't clash with anything else. We'll use OAEP padding specifically.

The `hazmat` part stands for "hazardous materials" — it means these are low-level crypto building blocks that you need to use carefully.

```python
from cryptography.hazmat.primitives import hashes, serialization
```
- `hashes` — gives us hash algorithm objects like `SHA256()`. We need SHA-256 for the OAEP padding inside RSA.
- `serialization` — lets us convert key objects to/from bytes (DER format) so we can send them over the network.

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
```
Imports the AES-GCM implementation. AEAD stands for "Authenticated Encryption with Associated Data" — GCM doesn't just encrypt, it also verifies the data wasn't tampered with.

---

## Lines 17–23: `generate_rsa_keypair()`

```python
def generate_rsa_keypair():
```
Defines a function that creates a brand-new RSA key pair (private key + public key).

```python
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
```
- `public_exponent=65537` — This is the "e" value in RSA math. 65537 (which is 2^16 + 1) is the industry standard because it's large enough to be secure but small enough to make encryption fast. Almost every RSA implementation uses this number.
- `key_size=2048` — The key length in bits. 2048-bit RSA is the minimum recommended by NIST (National Institute of Standards and Technology). Shorter keys can be cracked; longer keys (4096) are slower without much practical benefit for a university project.

The function generates both the private key and the public key internally. The public key is mathematically derived from the private key, so we only need to return the private key object.

```python
    return private_key
```
Return the private key. To get the public key later, call `private_key.public_key()`.

---

## Lines 25–31: `public_key_to_b64()`

```python
def public_key_to_b64(public_key):
```
Takes a public key object and turns it into a base64 string that can be sent in a text packet.

```python
    der_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
```
- `Encoding.DER` — DER is a compact binary format for keys. The alternative is PEM (which is base64 with `-----BEGIN...-----` headers), but since we're going to base64-encode it ourselves anyway, DER is more compact.
- `SubjectPublicKeyInfo` — This is the standard structure that includes both the key data and metadata about which algorithm (RSA) is used. It's the format everyone expects.

```python
    return base64.b64encode(der_bytes).decode("ascii")
```
`b64encode` converts raw bytes → base64 bytes, then `.decode("ascii")` converts those bytes → a Python string. The result is something like `"MIIBIjANBgkqh..."` which can safely go inside our comma-separated packet.

---

## Lines 33–36: `public_key_from_b64()`

```python
def public_key_from_b64(b64_string):
    der_bytes = base64.b64decode(b64_string)
    return serialization.load_der_public_key(der_bytes)
```
This is the reverse of `public_key_to_b64`:
1. `b64decode` converts the base64 string back to raw DER bytes.
2. `load_der_public_key` reconstructs the public key object from those bytes.

We use this on the client to reconstruct the **server's** public key after receiving it in the CC packet, and on the server to reconstruct the **client's** public key from the EC packet.

---

## Lines 38–48: `rsa_encrypt_session_key()`

```python
def rsa_encrypt_session_key(public_key, key_bytes):
```
Encrypts a small piece of data (the session key) using someone's RSA public key. Only the holder of the matching private key can decrypt it.

```python
    ciphertext = public_key.encrypt(
        key_bytes,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
```
- `key_bytes` — the data to encrypt (32 bytes for AES, or a few bytes like `b"17"` for Caesar).
- **OAEP** (Optimal Asymmetric Encryption Padding) — This is the **padding scheme** used during RSA encryption. Without padding, RSA is vulnerable to several mathematical attacks. OAEP adds randomness internally, so encrypting the same data twice gives different ciphertext. This is critical for security.
  - The older padding (PKCS#1 v1.5) is vulnerable to "padding oracle attacks" where an attacker can slowly figure out the plaintext by sending modified ciphertexts and watching for error messages.
- `MGF1(SHA256)` — MGF stands for "Mask Generation Function". It's part of the OAEP algorithm that generates a random-looking mask. SHA-256 is used as the underlying hash.
- `algorithm=hashes.SHA256()` — The hash used for the OAEP label. Must match on both sides.
- `label=None` — An optional label that can bind the ciphertext to a specific context. We don't need it.

```python
    return base64.b64encode(ciphertext).decode("ascii")
```
The ciphertext is raw bytes (exactly 256 bytes for 2048-bit RSA), so we base64 it to make it safe for our text-based packet.

---

## Lines 50–61: `rsa_decrypt_session_key()`

```python
def rsa_decrypt_session_key(private_key, b64_string):
    ciphertext = base64.b64decode(b64_string)
```
Reverse the base64 encoding to get back the raw RSA ciphertext.

```python
    plaintext = private_key.decrypt(
        ciphertext,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
```
Decrypt using the private key. The OAEP parameters **must be identical** to what was used during encryption — if they don't match, decryption will fail with an error. This is why both files have identical crypto helper code.

```python
    return plaintext
```
Returns the raw session key bytes (e.g., 32 bytes for AES, or `b"17"` for Caesar).

---

## Lines 63–68: `aes_encrypt()`

```python
def aes_encrypt(key, text):
    aesgcm = AESGCM(key)
```
Create an AES-GCM cipher object using the 32-byte session key. AES-256 means 256-bit key = 32 bytes.

```python
    nonce = secrets.token_bytes(12)
```
Generate 12 random bytes as the **nonce** (Number used ONCE). GCM mode **breaks catastrophically** if you ever reuse a nonce with the same key — an attacker could XOR two ciphertexts together and extract the plaintext. By using `secrets.token_bytes(12)`, each encryption gets a fresh random nonce. With 12 bytes (96 bits) of randomness, the chance of a collision is astronomically small (birthday paradox: ~2^48 encryptions before worry).

```python
    ciphertext = aesgcm.encrypt(nonce, text.encode("utf-8"), None)
```
- `text.encode("utf-8")` — convert the string to bytes (AES works on bytes, not strings).
- `None` — this is the "associated data" parameter. Associated data would be authenticated but not encrypted (like a packet header). We don't need it, so `None`.
- The result includes both the encrypted data AND a 16-byte authentication tag appended at the end. The tag lets the receiver verify nothing was tampered with.

```python
    return base64.b64encode(nonce + ciphertext).decode("ascii")
```
We **prepend the nonce** to the ciphertext before base64-encoding. The receiver needs the nonce to decrypt, and this is the standard way to transmit it — the nonce is not secret, just unique. Wire format: `base64( nonce[12] + ciphertext + tag[16] )`.

---

## Lines 70–77: `aes_decrypt()`

```python
def aes_decrypt(key, b64_text):
    raw = base64.b64decode(b64_text)
```
Decode from base64 back to raw bytes.

```python
    nonce = raw[:12]
    ciphertext = raw[12:]
```
Split: first 12 bytes = nonce, everything after = ciphertext + tag. We know the split point because we always use a 12-byte nonce.

```python
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
```
Decrypt and **verify the authentication tag**. If even one bit of the ciphertext or nonce was modified, this will raise an `InvalidTag` exception instead of returning garbage. This is why GCM is called "authenticated encryption."

```python
    return plaintext.decode("utf-8")
```
Convert the decrypted bytes back to a Python string.

---

## Lines 79–89: `caesar_encrypt()`

```python
def caesar_encrypt(key, text):
    result = []
```
We build the result character by character using a list (more efficient than string concatenation in Python).

```python
    for ch in text:
        if 'A' <= ch <= 'Z':
            result.append(chr((ord(ch) - ord('A') + key) % 26 + ord('A')))
```
For uppercase letters:
1. `ord(ch) - ord('A')` converts the letter to a number 0–25 (A=0, B=1, ..., Z=25).
2. `+ key` shifts it forward by the key amount.
3. `% 26` wraps around so if we go past Z we start back at A.
4. `+ ord('A')` converts the number back to an ASCII code.
5. `chr(...)` converts the ASCII code to a character.

Example: `ch='X'` (23), `key=5` → `(23+5) % 26 = 2` → `'C'`.

```python
        elif 'a' <= ch <= 'z':
            result.append(chr((ord(ch) - ord('a') + key) % 26 + ord('a')))
```
Same logic for lowercase, using `ord('a')` as the base. This preserves the original case.

```python
        else:
            result.append(ch)
```
Anything that's not a letter (digits, spaces, commas, newlines, punctuation) is kept unchanged. This is important because:
- Our packets use commas as delimiters — if we shifted commas, parsing would break.
- Digits and spaces don't benefit meaningfully from Caesar shifting.

```python
    return "".join(result)
```
Join all the characters in the list into a single string.

---

## Lines 91–93: `caesar_decrypt()`

```python
def caesar_decrypt(key, text):
    return caesar_encrypt(-key, text)
```
Decryption is just encryption with the **negative** shift. If we shifted right by 5 to encrypt, we shift left by 5 to decrypt. The `% 26` in `caesar_encrypt` handles negative numbers correctly in Python (e.g., `-5 % 26 = 21`).

---

## Lines 95–113: `encrypt_text()` and `decrypt_text()`

```python
def encrypt_text(session, text):
    if not session["secure"]:
        return text
```
If the session is not secured (unsecured mode), return the text **unchanged**. This is the key to backward compatibility — calling `encrypt_text` on every piece of data is safe because in unsecured mode it's a no-op.

```python
    if session["algorithm"] == "AES":
        return aes_encrypt(session["key"], text)
    if session["algorithm"] == "Caesar":
        return caesar_encrypt(session["key"], text)
    return text
```
Route to the correct algorithm based on what was negotiated during the handshake. The `return text` at the end is a safety fallback that should never be reached.

`decrypt_text` is identical but calls `aes_decrypt` / `caesar_decrypt` instead.

**Why wrappers?** Without them, every place in the code that reads or writes file data would need its own `if secure... if AES... if Caesar...` block. The wrappers centralize that logic in one place.

---

## Lines 119–120: Host & Port Configuration

```python
host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
```
If the user ran `python client.py 192.168.1.5`, use that IP. Otherwise default to `127.0.0.1` (localhost — the same machine).

```python
port = int(sys.argv[2]) if len(sys.argv) > 2 else 9009
```
If a second argument was given, use it as the port. Otherwise default to `9009`. `int()` converts the string argument to an integer because ports must be numbers.

---

## Lines 122–126: `send_frame()`

```python
def send_frame(sock, text):
    data = text.encode("utf-8")
```
Convert the Python string to UTF-8 bytes. Sockets send bytes, not strings.

```python
    length = st.pack("!I", len(data))
```
Pack the byte-length of the data into a 4-byte big-endian unsigned integer:
- `"!"` = network byte order (big-endian — most significant byte first). This ensures both sides agree on byte order regardless of CPU architecture.
- `"I"` = unsigned 32-bit integer (4 bytes). This means frames can be up to ~4 GB.

```python
    sock.sendall(length + data)
```
Send the 4-byte length header followed immediately by the actual data. `sendall` keeps sending until everything is transmitted (unlike `send` which might only send part of it).

Example: sending "Hello" → `[00 00 00 05][48 65 6C 6C 6F]`.

**Why length-prefix framing?** TCP is a *stream* protocol — it doesn't have message boundaries. If we sent two messages back-to-back, the receiver might get them merged together or split in the middle. The 4-byte length tells the receiver exactly how many bytes to read for each message.

---

## Lines 128–137: `recv_exact()`

```python
def recv_exact(sock, n):
    data = b""
```
Start with empty bytes.

```python
    while len(data) < n:
        chunk = sock.recv(n - len(data))
```
Keep calling `recv()` until we have exactly `n` bytes. `recv()` might return fewer bytes than requested (TCP can split data however it wants), so we loop. We ask for `n - len(data)` — only the remaining bytes we still need.

```python
        if chunk == b"":
            raise ConnectionError("Connection closed")
```
If `recv()` returns empty bytes, it means the other side closed the connection. We raise an error so the calling code knows.

```python
        data += chunk
    return data
```
Append each chunk and return when we have all `n` bytes.

---

## Lines 139–143: `recv_frame()`

```python
def recv_frame(sock):
    header = recv_exact(sock, 4)
```
Read exactly 4 bytes — this is the length header.

```python
    length = st.unpack("!I", header)[0]
```
Unpack those 4 bytes into a Python integer. `unpack` returns a tuple, so `[0]` gets the first (and only) value. This tells us how many bytes of actual data follow.

```python
    data = recv_exact(sock, length)
    return data.decode("utf-8")
```
Read exactly that many bytes, then decode from UTF-8 back to a string.

---

## Lines 145–149: `build()` and `parse()`

```python
def build(*fields):
    return ",".join(fields)
```
Takes any number of string arguments and joins them with commas. `build("SS", "RFMP", "v1.0", "1")` → `"SS,RFMP,v1.0,1"`. This creates the wire-format packet.

```python
def parse(raw, maxFields):
    return raw.split(",", maxFields - 1)
```
Splits a comma-separated string into at most `maxFields` pieces. The `-1` is because `split`'s second argument is the **max number of splits**, not the max number of pieces. `parse("SC,Hello,World", 2)` → `["SC", "Hello,World"]` — the second piece keeps any remaining commas, which is important for payloads that might contain commas.

---

## Lines 151–246: `setup()` — The Handshake & Key Exchange

```python
def setup(sock, secure_mode, algorithm_choice):
```
Now takes three parameters:
- `sock` — the TCP connection to the server
- `secure_mode` — `True` if the user wants encryption, `False` for original behavior
- `algorithm_choice` — `"AES"` or `"Caesar"` (ignored when `secure_mode` is `False`)

```python
    session = {
        "secure": False,
        "algorithm": None,
        "key": None,
    }
```
Create the session dictionary with defaults. This dictionary will be passed around to every function that needs to encrypt/decrypt. Starting with `"secure": False` means if anything goes wrong during setup, the session stays unsecured.

```python
    if secure_mode:
        send_frame(sock, build("SS", "RFMP", "v1.0", "1"))
    else:
        send_frame(sock, build("SS", "RFMP", "v1.0", "0"))
```
The **SS (Session Start) packet** is always the first packet sent. The last field is the security flag: `"0"` = unsecured (original behavior), `"1"` = secured (new behavior). The server reads this flag to decide what to do next.

```python
    reply = recv_frame(sock)
    parts = parse(reply, 3)
```
Wait for the server's response and split it into up to 3 parts. In unsecured mode, the server sends just `"CC"`. In secured mode, the server sends `"CC,<base64_public_key>"`.

```python
    if parts[0] == "EE":
        code = parts[1] if len(parts) > 1 else ""
        description = parts[2] if len(parts) > 2 else ""
        print("Error: ", code, description)
        return None
```
If the server rejected the handshake (e.g., wrong protocol version), print the error and return `None` to signal failure.

```python
    if parts[0] != "CC":
        print("Unexpected packet")
        return None
```
If it's not `"CC"` and not `"EE"`, something weird happened. Bail out.

```python
    if not secure_mode:
        print("Handshake complete!")
        return session
```
**Unsecured path ends here.** The session has `secure=False`, so all the encrypt/decrypt wrappers will be no-ops. This preserves the original behavior exactly.

### Secured Setup (lines 187–246):

```python
    if len(parts) < 2:
        print("Error: Server did not send its public key")
        return None
    server_pub_b64 = parts[1]
```
In secured mode, the CC packet should be `CC,<key>`. If there's no second part, the server didn't send its key.

```python
    try:
        server_pub_key = public_key_from_b64(server_pub_b64)
    except Exception:
        print("Error: Invalid server public key")
        return None
```
Deserialize the base64 string back into an RSA public key object. If the base64 is malformed or the bytes don't represent a valid key, this will throw an exception.

```python
    if algorithm_choice == "AES":
        session_key_bytes = secrets.token_bytes(32)
        session_key = session_key_bytes
        key_to_encrypt = session_key_bytes
```
Generate 32 random bytes for AES-256. We keep two references:
- `session_key` — what we'll store in the session dictionary (as bytes)
- `key_to_encrypt` — what we'll send to the server (same bytes, encrypted with RSA)

```python
    else:
        caesar_shift = secrets.randbelow(25) + 1
        session_key = caesar_shift
        key_to_encrypt = str(caesar_shift).encode("utf-8")
```
For Caesar:
- `secrets.randbelow(25)` gives a random integer from 0 to 24, then `+1` makes it 1 to 25.
- `session_key` is stored as an integer (e.g., `17`) for direct use in `caesar_encrypt()`.
- `key_to_encrypt` must be bytes for RSA, so we convert: `17` → `"17"` → `b"17"`.

```python
    client_private_key = generate_rsa_keypair()
    client_pub_b64 = public_key_to_b64(client_private_key.public_key())
```
Generate the **client's** RSA key pair. The server will store the client's public key for identification purposes (it's not used for encryption in our protocol — only the server's public key is used to encrypt the session key).

```python
    enc_key_b64 = rsa_encrypt_session_key(server_pub_key, key_to_encrypt)
```
Encrypt the session key with the **server's** public key. Only the server's private key can decrypt this. This is the core of the key exchange — even if someone intercepts this packet, they can't get the session key without the server's private key.

```python
    username = getpass.getuser()
```
Get the OS username (e.g., `"gauta"`). This is sent to the server for logging/identification.

```python
    ec_packet = build("EC", algorithm_choice, enc_key_b64, username + ":" + client_pub_b64)
    send_frame(sock, ec_packet)
```
Build and send the **EC (Encryption Configuration) packet**:
`EC,AES,<encrypted_key_base64>,gauta:<client_public_key_base64>`

The last field combines the username and client public key with a colon separator. We use colon instead of comma because commas are our packet delimiter.

```python
    reply = recv_frame(sock)
    parts = parse(reply, 3)

    if parts[0] == "SC":
        print("Secured handshake complete! Algorithm:", algorithm_choice)
        session["secure"] = True
        session["algorithm"] = algorithm_choice
        session["key"] = session_key
        return session
```
If the server sends `"SC"` (Success), the key exchange worked. Fill in the session dictionary and return it. From this point on, `encrypt_text(session, ...)` will actually encrypt.

```python
    elif parts[0] == "EE":
        ...
        return None
    else:
        print("Unexpected packet during key exchange")
        return None
```
Any error or unexpected response → return `None` to signal failure.

---

## Lines 265–289: `openRead()` — Reading Files

```python
def openRead(sock, filename, session):
```
Now takes `session` as a parameter so it can decrypt the response.

```python
    send_frame(sock, build("CM", "openRead", filename))
```
Send `CM,openRead,hello.txt` — the command packet is always plaintext (we only encrypt file contents, not commands).

```python
    reply = recv_frame(sock)
    parts = parse(reply, 2)
```
Parse into 2 parts: `["SC", "<file_contents_possibly_encrypted>"]`.

```python
    if parts[0] == "SC":
        if len(parts) > 1:
            try:
                file_contents = decrypt_text(session, parts[1])
            except Exception:
                print("Error: Failed to decrypt file contents")
                return False
            print(file_contents)
        return True
```
**This is the key change:** Before printing the file contents, we pass them through `decrypt_text()`. If the session is unsecured, this returns the text unchanged (backward compatible). If secured with AES, it decodes the base64 and runs AES-GCM decryption. If secured with Caesar, it shifts the letters back.

---

## Lines 291–340: `openWrite()` — Writing Files

```python
def openWrite(sock, filename, session):
    send_frame(sock, build("CM", "openWrite", filename))
```
Send the openWrite command (plaintext — only the file data is encrypted).

After the server confirms with `"SC"`, the user types in the file contents:

```python
    text = "\n".join(lines)
    text = encrypt_text(session, text)
    send_frame(sock, build("DP", text))
```
**The key change:** Before sending the DP (Data Packet), we encrypt the text. In unsecured mode, `encrypt_text` returns it unchanged. In AES mode, it becomes a base64 blob. In Caesar mode, the letters are shifted.

---

## Lines 342–423: `menu()` — The User Interface

```python
def menu(sock, session):
```
Now takes `session` so it can pass it to `openRead` and `openWrite`.

```python
        elif choice == "12":
            ...
            openWrite(sock, filename, session)   # passes session
        elif choice == "11":
            ...
            openRead(sock, filename, session)    # passes session
```
The only changes in the menu are passing `session` to these two functions. All other commands (mkdir, cd, ls, etc.) go through `handle_response()` which doesn't need the session because those commands don't involve file content encryption.

---

## Lines 425–473: Main Entry Point

```python
sock = None
```
Initialize to `None` so the `finally` block doesn't crash with a `NameError` if the connection never opens.

```python
try:
    sock = so.create_connection((host, port))
    print("Connected to server")
```
Open a TCP connection to the server. `create_connection` is a convenience function that creates a socket, connects it, and returns it.

```python
    secure_input = input("Use secured communication? (y/n): ").strip().lower()
    secure_mode = (secure_input == "y")
```
Ask the user whether they want encryption. The comparison `== "y"` returns `True` or `False`.

```python
    algorithm_choice = None
    if secure_mode:
        print("Choose encryption algorithm:")
        print("1) AES")
        print("2) Caesar")
        algo_input = input("Enter 1 or 2: ").strip()
        if algo_input == "1":
            algorithm_choice = "AES"
        elif algo_input == "2":
            algorithm_choice = "Caesar"
        else:
            print("Invalid choice, defaulting to AES.")
            algorithm_choice = "AES"
```
If secured mode, ask which algorithm. Default to AES if the user types something invalid.

```python
    session = setup(sock, secure_mode, algorithm_choice)
    if session is not None:
        menu(sock, session)
```
Run the handshake. If `setup` returns `None` (failure), we don't enter the menu — we fall through to the `finally` block which closes the connection.

```python
except ConnectionRefusedError:
    print("Could not connect to server.")
except ConnectionError:
    print("Server disconnected")
except KeyboardInterrupt:
    print("\nClient stopped.")
```
Handle the three ways a connection can fail.

```python
finally:
    if sock is not None:
        try:
            send_frame(sock, "End")
        except:
            pass
        sock.close()
        print("Connection closed")
```
`finally` always runs, no matter what. It sends `"End"` to tell the server we're disconnecting (wrapped in try/except because the server might already be gone), then closes the socket.

---
---

# PART 2 — THE SERVER ([ZayanZaid_server.py](file:///c:/Users/gauta/Downloads/chicken/SocketProject_CSEC201/ZayanZaid_server.py))

---

## Lines 1–22: Imports

```python
import os
```
For `os.name` — tells us if we're on Windows (`"nt"`) or Linux/Mac (`"posix"`). Used to map shell commands correctly.

```python
import socket
```
The socket library for TCP networking.

```python
import struct
```
For packing/unpacking the 4-byte length header (same as the client).

```python
import subprocess
```
For running system commands (`whoami`, `date`, `ps`) on the host OS.

```python
import threading
```
For creating a new thread per client connection. This lets multiple clients connect simultaneously without blocking each other.

```python
from pathlib import Path
```
`Path` gives us an object-oriented way to work with file paths. It handles slash directions, path joining, and filesystem checks more cleanly than string manipulation.

```python
import base64
import secrets
```
Same as client — base64 for text encoding, secrets for crypto-safe randomness.

Lines 19–22 are the same crypto imports as the client.

---

## Lines 24–124: Crypto Helper Functions

These are **identical** to the client's crypto helpers. They're duplicated here because the project rules say only two files are allowed — no shared module. The server uses:
- `generate_rsa_keypair()` — to create per-connection RSA keys
- `public_key_to_b64()` — to send its public key to the client
- `public_key_from_b64()` — to load the client's public key
- `rsa_decrypt_session_key()` — to decrypt the session key the client encrypted with our public key
- `aes_encrypt/decrypt` and `caesar_encrypt/decrypt` — for file content encryption/decryption
- `encrypt_text/decrypt_text` — the wrapper functions

See the client section above for detailed explanations of each function.

---

## Lines 130–132: Server Initialization

```python
BASE_DIRECTORY = Path(__file__).parent
```
`__file__` is the path to this Python script. `.parent` gets the directory containing it. This is the base from which we create the `home` folder.

```python
HOME_DIRECTORY_NAME = "home"
```
The sandboxed root directory name. Clients can't access anything outside this folder.

---

## Lines 135–401: The `Server` Class

This class handles all file system operations. **Nothing changed here** — it's the same as the original. Key methods:

- `get_current_directory()` — returns a virtual path like `/Documents`
- `change_directory(name)` — cd into a subfolder (with sandbox checks)
- `list_directory()` — ls
- `make_directory(name)` — mkdir
- `rename_directory(old, new)` — ren
- `delete_directory(name)` — rmdir
- `make_file(name)` — touch
- `delete_file(name)` — del
- `open_read(name)` — reads and returns file contents as a string
- `open_write(name)` — opens a file for writing and stores the path
- `write_data(data)` — writes data to the previously opened file

Every method checks `is_relative_to(home_directory)` to prevent sandbox escapes (e.g., `../../etc/passwd`).

---

## Lines 572–601: Networking Functions

`build()`, `parse()`, `recv_exact()`, `recv_frame()`, `send_frame()` are identical to the client's versions.

---

## Lines 604–636: `run_system_command()`

```python
def run_system_command(command_name):
```
Runs an OS command and returns the output. On Windows, maps `ls` → `dir`, `pwd` → `cd`, etc.

```python
    result = subprocess.run(command_to_run, shell=True, capture_output=True, text=True, check=False)
```
- `shell=True` — run through the system shell (cmd.exe on Windows)
- `capture_output=True` — capture stdout and stderr
- `text=True` — return output as string, not bytes
- `check=False` — don't raise an exception on non-zero exit codes

---

## Lines 689–740: `handle_packet()` — Packet Router

```python
def handle_packet(server_obj, packet, session):
```
**Key change:** Now takes a `session` parameter. This is the per-connection dictionary created in `handle_client`.

### SS Packet (lines 700–704):

```python
    if packet_type == "SS":
        if len(fields) >= 4 and fields[1] == "RFMP" and fields[2] == "v1.0" and fields[3] in ("0", "1"):
            return "CC"
        return "EE,0,Invalid handshake"
```
**Change:** The original only accepted `fields[3] == "0"`. Now it accepts `("0", "1")`. But `handle_packet` only returns `"CC"` — the actual secure setup (RSA key generation, EC packet parsing) is done in `handle_client`, not here. This keeps `handle_packet` clean.

### openRead (lines 716–722):

```python
        if action == "openRead":
            data = server_obj.open_read(payload)
            if data is None:
                return "EE,1,File not found or access denied."
            data = encrypt_text(session, data)
            return f"SC,{data}"
```
**Key change:** After reading the file from disk, we encrypt the contents before sending. In unsecured mode, `encrypt_text` returns the text unchanged — identical to before.

### DP Packet (lines 729–738):

```python
    if packet_type == "DP":
        if len(fields) < 2:
            return "EE,3,Failed to write data."
        text = fields[1]
        try:
            text = decrypt_text(session, text)
        except Exception:
            return "EE,3,Failed to write data."
        return "SC" if server_obj.write_data(text) else "EE,3,Failed to write data."
```
**Key change:** Before writing data to the file, we decrypt it first. The `try/except` catches decryption failures (e.g., tampered ciphertext with AES, or corrupted base64) and returns an error using the existing error code 3.

---

## Lines 743–873: `handle_client()` — Per-Connection Handler

This is the **most significantly changed function**.

```python
def handle_client(client_socket, server_obj):
    session = {
        "secure": False,
        "algorithm": None,
        "key": None,
        "username": None,
        "client_pub": None,
    }
```
**Critical design decision:** The `session` dictionary is a **local variable** inside `handle_client`, NOT stored on the `Server` object. This is essential because `Server` is shared across all threads. If we stored session data on `Server`, one client's AES key could overwrite another client's key. Each thread gets its own `session` dict on its own stack.

```python
    handshake = recv_frame(client_socket)
    if handshake == "End":
        return
```
Read the first packet. If it's `"End"`, the client disconnected immediately.

```python
    ss_fields = handshake.split(",", 3)
    secure_flag = ss_fields[3] if len(ss_fields) >= 4 else "0"
```
Parse the SS packet to extract the security flag **before** passing it to `handle_packet`. We need the flag here in `handle_client` to decide whether to run the key exchange, but `handle_packet` only validates the packet format.

```python
    response = handle_packet(server_obj, handshake, session)
    if response == "End":
        return
    if response != "CC":
        send_frame(client_socket, response)
        return
```
If the handshake is invalid, send the error and disconnect.

### Secured Setup (lines 770–847):

```python
    if secure_flag == "1":
```
Only run the key exchange if the client asked for secured mode.

```python
        server_private_key = generate_rsa_keypair()
        server_public_key = server_private_key.public_key()
```
Generate a **fresh** RSA key pair for **this connection only**. Every client gets different RSA keys. If one connection is compromised, other connections aren't affected.

```python
        server_pub_b64 = public_key_to_b64(server_public_key)
        send_frame(client_socket, build("CC", server_pub_b64))
```
Send `CC,<base64_public_key>` to the client. The client will use this key to encrypt the session key.

```python
        ec_raw = recv_frame(client_socket)
        ec_fields = ec_raw.split(",", 3)
```
Read the EC packet from the client. `split(",", 3)` gives at most 4 fields: `["EC", algorithm, encrypted_key, "username:client_pub_key"]`. We use maxsplit=3 because the base64 key and username:pubkey field could theoretically contain other characters.

```python
        if len(ec_fields) < 4 or ec_fields[0] != "EC":
            send_frame(client_socket, build("EE", "0", "Invalid key exchange packet"))
            return
```
Validate the packet structure. If anything is wrong, send error code 0 (handshake error).

```python
        algorithm = ec_fields[1]
        enc_key_b64 = ec_fields[2]
        user_and_pub = ec_fields[3]
```
Extract the three data fields.

```python
        if algorithm not in ("AES", "Caesar"):
            send_frame(client_socket, build("EE", "0", "Unsupported algorithm"))
            return
```
Only accept the two supported algorithms.

```python
        colon_pos = user_and_pub.find(":")
        if colon_pos == -1:
            send_frame(client_socket, build("EE", "0", "Missing client public key"))
            return
        username = user_and_pub[:colon_pos]
        client_pub_b64 = user_and_pub[colon_pos + 1:]
```
Split `"gauta:MIIBIjAN..."` at the **first** colon. We use `find(":")` instead of `split(":")` because base64 can contain `+`, `/`, `=` but not `:`, so we're safe. But using `find` and slicing is explicit about taking only the first colon.

```python
        try:
            raw_key = rsa_decrypt_session_key(server_private_key, enc_key_b64)
        except Exception:
            send_frame(client_socket, build("EE", "0", "Failed to decrypt session key"))
            return
```
Decrypt the session key using our private key. If the client used a different public key, or the data is corrupted, this will fail.

```python
        if algorithm == "AES":
            if len(raw_key) != 32:
                send_frame(client_socket, build("EE", "0", "Invalid AES key length"))
                return
            session_key = raw_key
        else:
            try:
                session_key = int(raw_key.decode("utf-8"))
            except ValueError:
                send_frame(client_socket, build("EE", "0", "Invalid Caesar key"))
                return
```
Convert the raw decrypted bytes to the right type:
- AES: must be exactly 32 bytes, keep as bytes
- Caesar: was sent as `b"17"`, decode to string `"17"`, convert to integer `17`

```python
        try:
            client_pub_key = public_key_from_b64(client_pub_b64)
        except Exception:
            send_frame(client_socket, build("EE", "0", "Invalid client public key"))
            return
```
Deserialize the client's public key just to verify it's valid. We store it but don't use it for encryption.

```python
        session["secure"] = True
        session["algorithm"] = algorithm
        session["key"] = session_key
        session["username"] = username
        session["client_pub"] = client_pub_key
```
Fill in the session dictionary. From now on, `encrypt_text` and `decrypt_text` will actually perform encryption/decryption.

```python
        print(f"Secured connection: user={username}, algorithm={algorithm}")
        print(f"Client public key: {client_pub_b64[:40]}...")
```
Log info about the connection. We print only the first 40 characters of the public key (it's very long). We **never print the session key** — that would be a security violation.

```python
        send_frame(client_socket, "SC")
```
Tell the client the key exchange succeeded.

### Unsecured path (lines 849–851):

```python
    else:
        send_frame(client_socket, "CC")
```
Original behavior — just send `CC` and move on.

### Operation Loop (lines 853–864):

```python
    while True:
        packet = recv_frame(client_socket)
        if packet == "End":
            break
        response = handle_packet(server_obj, packet, session)
        if response == "End":
            break
        if response:
            send_frame(client_socket, response)
```
The command loop is the same for both modes. The `session` dict is passed to `handle_packet`, which passes it to `encrypt_text`/`decrypt_text`. In unsecured mode, those are no-ops.

---

## Lines 877–901: `start_server()` — The Server Entry Point

```python
def start_server(host="127.0.0.1", port=9009, backlog=5):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
```
Create a TCP socket. `AF_INET` = IPv4, `SOCK_STREAM` = TCP (reliable, ordered delivery).

```python
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
```
Allow reusing the port immediately after the server stops. Without this, you'd get "Address already in use" if you restart the server quickly.

```python
    server_socket.bind((host, port))
    server_socket.listen(backlog)
```
Bind to the address/port and start listening. `backlog=5` means the OS will queue up to 5 incoming connections before refusing new ones.

```python
    try:
        while True:
            client_socket, client_address = server_socket.accept()
```
`accept()` blocks until a client connects, then returns a new socket for that specific client and the client's address.

```python
            thread = threading.Thread(
                target=handle_client,
                args=(client_socket, server),
                daemon=True,
            )
            thread.start()
```
Create a new thread for each client. `daemon=True` means these threads die automatically when the main thread exits (e.g., on Ctrl+C). Each thread runs `handle_client` with its own socket but the **shared** `server` object. The session state is safe because it's a local variable in `handle_client`, not on the shared `server` object.

```python
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server_socket.close()
```
Ctrl+C stops the loop, and we close the listening socket.

```python
if __name__ == "__main__":
    start_server()
```
Only run the server when this file is executed directly (not when imported).
