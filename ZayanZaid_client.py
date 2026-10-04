import socket as so
import struct as st
import sys 
import getpass                    # to get the OS username for the EC packet
import base64                     # needed to encode binary crypto data as text
import secrets                    # cryptographically secure random numbers

# --- CRYPTO IMPORTS ---
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding  # RSA key gen and OAEP padding
from cryptography.hazmat.primitives import hashes, serialization                     # SHA-256 and key serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM                      # AES-256-GCM authenticated encryption

# ============================================================
# CRYPTO HELPER FUNCTIONS  (identical copy lives in the server)
# ============================================================

def generate_rsa_keypair():
    # generate a 2048-bit RSA private key with public exponent 65537
    private_key = rsa.generate_private_key(
        public_exponent=65537,  # standard public exponent, fast and secure
        key_size=2048,          # 2048 bits is the minimum recommended size
    )
    return private_key  # the public key can be derived from the private key

def public_key_to_b64(public_key):
    # serialize the public key to DER (binary) format, then base64-encode it
    der_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,                        # compact binary format
        format=serialization.PublicFormat.SubjectPublicKeyInfo,      # standard public key structure
    )
    return base64.b64encode(der_bytes).decode("ascii")  # return a plain text string

def public_key_from_b64(b64_string):
    # reverse of public_key_to_b64: decode base64, then load the DER public key
    der_bytes = base64.b64decode(b64_string)  # turn the text back into raw bytes
    return serialization.load_der_public_key(der_bytes)  # reconstruct the key object

def rsa_encrypt_session_key(public_key, key_bytes):
    # encrypt a small piece of data (the session key) with the recipient's public key
    ciphertext = public_key.encrypt(
        key_bytes,
        asym_padding.OAEP(                                # OAEP is the modern, secure RSA padding
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),  # mask generation uses SHA-256
            algorithm=hashes.SHA256(),                         # hash algorithm for OAEP label
            label=None,                                        # no label needed
        ),
    )
    return base64.b64encode(ciphertext).decode("ascii")  # return base64 text so it fits in a packet

def rsa_decrypt_session_key(private_key, b64_string):
    # decrypt the session key that was encrypted with our public key
    ciphertext = base64.b64decode(b64_string)  # decode the base64 text back to raw bytes
    plaintext = private_key.decrypt(
        ciphertext,
        asym_padding.OAEP(                                # must use the same padding as encryption
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return plaintext  # raw bytes of the session key

def aes_encrypt(key, text):
    # encrypt a string using AES-256-GCM with a fresh random nonce
    aesgcm = AESGCM(key)                        # create an AES-GCM cipher with the 32-byte key
    nonce = secrets.token_bytes(12)              # GCM needs a unique 12-byte nonce every time
    ciphertext = aesgcm.encrypt(nonce, text.encode("utf-8"), None)  # encrypt; tag is appended automatically
    return base64.b64encode(nonce + ciphertext).decode("ascii")     # pack nonce+ciphertext together as base64

def aes_decrypt(key, b64_text):
    # decrypt base64(nonce + ciphertext_with_tag) back into a string
    raw = base64.b64decode(b64_text)   # decode from base64 to raw bytes
    nonce = raw[:12]                   # first 12 bytes are the nonce
    ciphertext = raw[12:]              # the rest is ciphertext + authentication tag
    aesgcm = AESGCM(key)              # recreate the cipher with the same key
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)  # decrypt and verify tag
    return plaintext.decode("utf-8")   # convert bytes back to a string

def caesar_encrypt(key, text):
    # shift every letter by 'key' positions, wrapping around the alphabet
    result = []                        # we will build the output character by character
    for ch in text:
        if 'A' <= ch <= 'Z':          # uppercase letter
            result.append(chr((ord(ch) - ord('A') + key) % 26 + ord('A')))  # shift within A-Z
        elif 'a' <= ch <= 'z':        # lowercase letter
            result.append(chr((ord(ch) - ord('a') + key) % 26 + ord('a')))  # shift within a-z
        else:
            result.append(ch)         # digits, spaces, commas, newlines stay the same
    return "".join(result)            # combine the list into one string

def caesar_decrypt(key, text):
    # decrypting Caesar is just encrypting with the negative shift
    return caesar_encrypt(-key, text)  # shifting back undoes the original shift

def encrypt_text(session, text):
    # top-level wrapper: encrypts text based on the session settings
    if not session["secure"]:         # unsecured mode, do nothing
        return text
    if session["algorithm"] == "AES":
        return aes_encrypt(session["key"], text)   # AES-256-GCM encryption
    if session["algorithm"] == "Caesar":
        return caesar_encrypt(session["key"], text)  # Caesar shift encryption
    return text  # fallback, should never happen

def decrypt_text(session, text):
    # top-level wrapper: decrypts text based on the session settings
    if not session["secure"]:         # unsecured mode, do nothing
        return text
    if session["algorithm"] == "AES":
        return aes_decrypt(session["key"], text)   # AES-256-GCM decryption
    if session["algorithm"] == "Caesar":
        return caesar_decrypt(session["key"], text)  # Caesar shift decryption
    return text  # fallback, should never happen

# ============================================================
# END OF CRYPTO HELPERS
# ============================================================

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1" #expects input of ip-address otherwise defaults to "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 9009 #expects input of port number otherwise defaults to 9009 

def send_frame(sock, text): #takes sock and text as input
    data = text.encode("utf-8") #encodes data as utf-8
    length = st.pack("!I", len(data)) #packs the length of the data into a 4-byte integer
    #"!I": "!" means a network byte order and "I" specified an unsigned integer of 4 bytes. This converts integer values into 4-byte big-endian binary.
    sock.sendall(length + data) #sends the data as [length][message]. for eg: [00 00 00 05][Hello] -> 00 00 00 05 H e l l o

def recv_exact(sock, n): #takes input of sock and n; n is an integer value which means the number of bytes to accept
    data = b"" #empty bytes

    while len(data) < n: #check if the length of the current data is less than the length of the data specified to recieve
        chunk = sock.recv(n - len(data)) #asks for how many bytes are remaining
        if chunk == b"": #if chunk is empty it means the connection has been closed
            raise ConnectionError("Connection closed")

        data += chunk #adds the chunk to the data. 
    return data

def recv_frame(sock): #takes input of sock. (does the exact opposite of send_frame(sock, text))
    header = recv_exact(sock, 4) #this gets the length of the message
    length = st.unpack("!I", header)[0] #this unpacks the 4-byte big endian binary into an integer value. The [0] means its looking at the first element of the data sent
    data = recv_exact(sock, length) #recieves the exact amount of data specified in the length
    return data.decode("utf-8") #decodes the data from utf-8

def build(*fields): #protocol pracket creater. "*fields" means that this function can revieve multiple arguments
    return ",".join(fields) #for eg: build("A", "B", "C D") returns A,B,C D

def parse(raw, maxFields): #this does the reverse of the build(*fields) function
    return raw.split(",", maxFields - 1) #for eg: parse("A,B,C,D", 2) runs "A,B,C,D".split(",", 1) which returns ["A", "B,C,D"]

def setup(sock, secure_mode, algorithm_choice):
    # secure_mode: True if user wants encryption, False for original unsecured mode
    # algorithm_choice: "AES" or "Caesar" (only matters when secure_mode is True)

    # build the session dictionary that will be used throughout the connection
    session = {
        "secure": False,       # will be set to True after a successful key exchange
        "algorithm": None,     # "AES" or "Caesar"
        "key": None,           # session key (bytes for AES, int for Caesar)
    }

    if secure_mode:
        # step 1: send the handshake with security flag "1"
        send_frame(sock, build("SS", "RFMP", "v1.0", "1"))
    else:
        # original unsecured handshake with flag "0"
        send_frame(sock, build("SS", "RFMP", "v1.0", "0"))  #this sends SS,RFMP,v1.0,0

    reply = recv_frame(sock) #waits for server reply
    parts = parse(reply, 3) #parses server reply and breaks it into at most 3 pieces

    if parts[0] == "EE": #checks the first element if EE -> error code (something went wrong)
        code = parts[1] if len(parts) > 1 else "" #extracts error code 
        description = parts[2] if len(parts) > 2 else "" #extracts description
        print("Error: ", code, description)
        return None  # return None to signal failure

    if parts[0] != "CC": #if the server sends anything unexpected
        print("Unexpected packet")
        return None

    if not secure_mode:
        # unsecured mode: CC means handshake complete, same as before
        print("Handshake complete!")
        return session  # session with secure=False

    # --- SECURED SETUP (only runs when secure_mode is True) ---

    # step 2: the server sent CC,<server_public_key_b64>
    if len(parts) < 2:
        print("Error: Server did not send its public key")
        return None

    server_pub_b64 = parts[1]  # the server's public key in base64
    try:
        server_pub_key = public_key_from_b64(server_pub_b64)  # deserialize the server's public key
    except Exception:
        print("Error: Invalid server public key")
        return None

    # step 3a: generate a session key for the chosen algorithm
    if algorithm_choice == "AES":
        session_key_bytes = secrets.token_bytes(32)  # 32 random bytes for AES-256
        session_key = session_key_bytes              # keep as bytes
        key_to_encrypt = session_key_bytes           # this is what we encrypt with RSA
    else:
        # Caesar: random integer from 1 to 25
        caesar_shift = secrets.randbelow(25) + 1     # randbelow(25) gives 0-24, +1 gives 1-25
        session_key = caesar_shift                   # store as int
        key_to_encrypt = str(caesar_shift).encode("utf-8")  # convert to bytes for RSA encryption

    # step 3b: generate the client's own RSA key pair
    client_private_key = generate_rsa_keypair()
    client_pub_b64 = public_key_to_b64(client_private_key.public_key())  # serialize client's public key

    # step 3c: encrypt the session key with the server's public key
    enc_key_b64 = rsa_encrypt_session_key(server_pub_key, key_to_encrypt)

    # step 3d: get the OS username
    username = getpass.getuser()  # returns the current OS username

    # step 3e: send the EC packet: EC,<algorithm>,<enc_key>,<username>:<client_pub_key>
    ec_packet = build("EC", algorithm_choice, enc_key_b64, username + ":" + client_pub_b64)
    send_frame(sock, ec_packet)

    # step 4: wait for the server's response (expecting SC)
    reply = recv_frame(sock)
    parts = parse(reply, 3)

    if parts[0] == "SC":
        # key exchange was successful
        print("Secured handshake complete! Algorithm:", algorithm_choice)
        session["secure"] = True
        session["algorithm"] = algorithm_choice
        session["key"] = session_key
        return session  # return the fully configured session

    elif parts[0] == "EE":
        code = parts[1] if len(parts) > 1 else ""
        description = parts[2] if len(parts) > 2 else ""
        print("Error: ", code, description)
        return None  # key exchange failed

    else:
        print("Unexpected packet during key exchange")
        return None

def print_server_block(data):
    text = str(data).strip()
    print() 
    print("=======")
    print("Server Response:")
    print("=======")
    print()
    print()
    print(text if text else "")
    print()
    print()
    print("=======")
    print()


def handle_response(sock): #default response handler after sending commands
    reply = recv_frame(sock) 
    parts = parse(reply, 3)

    if parts[0] == "SC": #checks first element if "SC" -> success
        if len(parts) > 1: #checks for payload 
            print_server_block(parts[1])
        return True
    elif parts[0] == "EE": #checks first element if "EE" -> error code
        code = parts[1] if len(parts) > 1 else "" #extracts error code
        description = parts[2] if len(parts) > 2 else "" #extracts description
        print("Error: ", code, description)
        return False
    else:
        print("Unexpected error")
        return False

def openRead(sock, filename, session): #takes input of socket, filename, and session
    send_frame(sock, build("CM", "openRead", filename)) #if filename is hello.txt this sends CM,openRead,hello.txt

    reply = recv_frame(sock) #waits for server reply
    parts = parse(reply, 2) #parses server reply and breaks into at most 2 parts

    if parts[0] == "SC": #if success it prints the file which is parts[1]
        if len(parts) > 1:
            # if secure mode is on, the server encrypted the file contents
            try:
                file_contents = decrypt_text(session, parts[1])  # decrypt (or pass-through)
            except Exception:
                print("Error: Failed to decrypt file contents")
                return False
            print_server_block(file_contents)
        return True

    elif parts[0] == "EE": #if error it outputs the error code
        code = parts[1] if len(parts) > 1 else ""
        print("Error", code)
        return False

    else: #if the server sends anything else it outputs this
        print("Unexpected error")
        return False

def openWrite(sock, filename, session): #takes input of sock, filename, and session
    send_frame(sock, build("CM", "openWrite", filename)) #if filename is hello.txt this sends CM,openWrite,hello.txt

    reply = recv_frame(sock) #waits for server reply
    parts = parse(reply, 3) #parses server reply and breaks into at most of 3 pieces

    if parts[0] == "EE": #if error it outputs error code and description
        code = parts[1] if len(parts) > 1 else ""
        description = parts[2] if len(parts) > 2 else ""
        print("Error: ", code, description)
        return False

    elif parts[0] != "SC": #if the server sends not "SC" it still stops
        print("Unexpected packet")
        return False
    #only after recieveing SC does it ask the user for file contents
    print("Enter file contents")
    print("Type '.' in a new line when finished.")

    lines = [] 

    while True:
        line = input() #keeps collecting lines
        if line == ".": #breaks if input is "."
            break
        lines.append(line)

    text = "\n".join(lines) #joins the message new lines into a single message

    # if secure mode is on, encrypt the text before sending
    text = encrypt_text(session, text)  # encrypt (or pass-through if unsecured)

    send_frame(sock, build("DP", text))

    reply = recv_frame(sock)
    parts = parse(reply, 3)

    if parts[0] == "SC":
        print("File written successfully")
        return True

    elif parts[0] == "EE":
        code = parts[1] if len(parts) > 1 else ""
        description = parts[2] if len(parts) > 2 else ""
        print("Error: ", code, description)
        return False

    else: 
        print("Unexpected packet")
        return False

def menu(sock, session): #main user interface options, now takes session as a parameter
    commands = { #dictionary that connects numbers to commands
        "1": "mkdir",
        "2": "cd",
        "3": "rmdir",
        "4": "del",
        "5": "ren",
        "6": "ls",
        "7": "pwd",
        "8": "whoami",
        "9": "date",
        "10": "ps"
    }

    while True: #menu runs forever until quit or something breaks
        print("\n--- Client Menu ---")
        print("1. Create a Directory (mkdir)")
        print("2. Change Directory (cd)")
        print("3. Remove a Directory (rmdir)")
        print("4. Delete a File (del)")
        print("5. Rename a File (ren)")
        print("6. List Files (ls)")
        print("7. Print Working Directory (pwd)")
        print("8. Print User Name (whoami)")
        print("9. Print Date (date)")
        print("10. Print Processes (ps)")
        print("11. openRead")
        print("12. openWrite")
        print("13. Quit")

        choice = input("Choose an option: ")

        if choice == "13": #only exits menu. does not close connection; that is handled by the "finally" block
            break

        #openRead and openWrite require user input for the filename
        elif choice == "12": 
            filename = input("Filenmae: ").strip()
            if filename == "":
                print("Filename cannot be empty.")
                continue

            openWrite(sock, filename, session)  # pass session so it knows whether to encrypt

        elif choice == "11":
            filename = input("Filename: ").strip()
            if filename == "":
                print("Filename cannot be empty")
                continue

            openRead(sock, filename, session)  # pass session so it knows whether to decrypt

        elif choice in commands:
            command = commands[choice]

            if command in ["ls", "pwd", "whoami", "date", "ps"]: #commands that dont require an argument and can be send directly
                full_command = command

            elif command == "ren": #if command is "ren" it required oldName and newName
                oldName = input("Enter old name: ").strip()
                newName = input("Enter new name: ").strip()

                if oldName == "" or newName == "": #names cannot be empty
                    print("Both names are required.")
                    continue

                full_command = command + " " + oldName + " " + newName #creates the full command with the oldName and newName

            else: #commands that do require an argument besides "ren". [mkdir, cd, rmdir, del] these commands require only 1 argument
                argument = input("Argument: ").strip()

                if argument == "":
                    print("Argument cannot be empty.")
                    continue

                full_command = command + " " + argument #creates the full command with the one argument

            send_frame(sock, build("CM", "prompt", full_command)) #sends CM,prompt,full_command
            handle_response(sock)

        else:
            print("Invalid choice.")

sock = None #to prevent the chance that something goes wrong before sock gets assigned. 
#for eg: if the "create_connection" never creates the connection. this is to prevent NameError

try:
    sock = so.create_connection((host, port)) #opens a TCP connection
    print("Connected to server")

    # ask the user if they want secured communication
    secure_input = input("Use secured communication? (y/n): ").strip().lower()
    secure_mode = (secure_input == "y")  # True if user typed "y"

    algorithm_choice = None  # only used in secure mode
    if secure_mode:
        # ask which encryption algorithm to use
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

    session = setup(sock, secure_mode, algorithm_choice)  # returns session dict or None
    if session is not None:
        menu(sock, session)  # pass session so openRead/openWrite can encrypt/decrypt

#error handling
except ConnectionRefusedError: #if no server listening
    print("Could not connect to server.")

except ConnectionError: #if server disconnects
    print("Server disconnected")

except KeyboardInterrupt: #if user presses Ctrl+C
    print("\nClient stopped.")

finally: #runs no matter how the "try-expect" block ran
    if sock is not None:
        try: #another try because if the server crashed the "End" message might not reach
            send_frame(sock, "End") #tells the server "End"
        except:
            pass

        sock.close()
        print("Connection closed")
