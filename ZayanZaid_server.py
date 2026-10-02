# CSEC 201 - Remote File Management Protocol (RFMP)
# Date Created: 20 September 2026

# Zayan Zaid | 410005187
# Joshua Joseph Cardoz | 753003560
# First Last | UID
# First Last | UID

# --- IMPORTS ---
import os
import socket
import struct
import subprocess
import threading
from pathlib import Path
import base64                     # needed to encode binary crypto data as text
import secrets                    # cryptographically secure random numbers

# --- CRYPTO IMPORTS ---
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding  # RSA key gen and OAEP padding
from cryptography.hazmat.primitives import hashes, serialization                     # SHA-256 and key serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM                      # AES-256-GCM authenticated encryption

# ============================================================
# CRYPTO HELPER FUNCTIONS  (identical copy lives in the client)
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
            result.append(ch)         # digits, spaces, commas, etc. stay the same
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

# --- INITIALIZATION ---
BASE_DIRECTORY = Path(__file__).parent # Get the directory of the current file
HOME_DIRECTORY_NAME = "home" # Name of the folder where the server will store the files (cannot access outside of here)


class Server:
    def __init__(self):
        self.home_directory = BASE_DIRECTORY / HOME_DIRECTORY_NAME # Define the root directory for the server
        self.home_directory.mkdir(exist_ok=True) # Create the home directory if it doesn't exist
        self.current_directory = self.home_directory
        self.write_file = None # This will hold the file created/accessed by the open_write function so that when the data packet is recieved, it's contents can be put in the file
        self.write_started = False # Allows us to know if we should write or append to a file

    # pwd (extra function) | Gives the current directory (where is it)
    def get_current_directory(self): # Note: This function will return a virtual "current directory" rather than the REAL actual directory (of the computer)
        relative_path = self.current_directory.relative_to(self.home_directory)

        if relative_path == Path("."):
            return "/"
        
        return "/" + str(relative_path)

    # cd
    def change_directory(self, name):
        new_directory = self.current_directory / name

        if not new_directory.exists(): # Check if the directory exists
            return False # Error: Directory does not exist

        if not new_directory.is_dir(): # Check if name is a directory (rather than a file)
            return False # Error: Not a directory

        # Check to see if the user is trying to get out of the root directory (home directory)
        new_directory = new_directory.resolve()
        home_directory = self.home_directory.resolve()
        if not new_directory.is_relative_to(home_directory): # Check if the user is trying to get out of the root directory (home directory)
            return False

        self.current_directory = new_directory # Actually chnage the directory
        return True # Successfully changed the directory

    # ls (extra function) | Gives a list of all the items in the current directory
    def list_directory(self):
        items_in_directory = [] # Array[String] - Will hold the names of all the items inside the current directory

        for item in self.current_directory.iterdir():
            items_in_directory.append(item.name) # For ls, will just need the name, nothing else

        return items_in_directory
        # The content of item_in_directory can be used by whoever makes the packet/server logic - GAUTUM - DELETE THIS COMMENT WHEN YOU ARE MODIFYING THE CODE  

    # count (extra functions) | Will list the number of items in the current directory
    def count_items(self):
        count = 0 # Integer
        for item in self.current_directory.iterdir():
            count += 1
        return count

    # file (extra function) | Will check to see if it a file or directory
    def check_type(self, name):
        name_to_check = self.current_directory / name
        name_to_check = name_to_check.resolve()

        if not name_to_check.is_relative_to(self.home_directory.resolve()):
            return False

        if not name_to_check.exists():
            return False # Doesn't exist

        if name_to_check.is_dir(): # Directory check
            return "directory"

        if name_to_check.is_file(): # File check
            return "file"

        return None  # Not a file or directory

    # wc (extra function) | returns the no. of lines, words, and bytes in a file
    def word_count(self, name):
        file_to_count = self.current_directory / name

        if not file_to_count.is_relative_to(self.home_directory.resolve()):
            return False # Outisde sandbox
        if not file_to_count.exists():
            return False # Doesn't exist
        if file_to_count.is_dir():
            return False # Is a directory

        try:
            with open(file_to_count, 'r') as file:
                lines = file.readlines() # Will read all the lines of the file into the lines list

            line_count = len(lines)
            word_count = sum(len(line.split()) for line in lines)
            byte_count = file_to_count.stat().st_size  # Gets the file size in bytes

            return line_count, word_count, byte_count # Returns a tuple
        except OSError:
            return False

#DO GIT PULL - Dont del this line, just remove the comment (make the line blank)

    # --- FOLDER FUNCTIONS ---

    # mkdir
    def make_directory(self, name):
        new_directory = self.current_directory / name

        new_directory = new_directory.resolve()
        if not new_directory.is_relative_to(self.home_directory.resolve()): # Check if the path escapes the sandbox.
            return False

        try:
            new_directory.mkdir()
            return True

        except FileExistsError: # Will stop a directory with the same name from being created (two directories should not have the same name)
            return False

    # ren
    def rename_directory(self, oldName, newName):
        old_directory = self.current_directory / oldName
        new_directory = self.current_directory / newName

        old_directory = old_directory.resolve()
        new_directory = new_directory.resolve()
        if not old_directory.is_relative_to(self.home_directory.resolve()):
            return False
        if not new_directory.is_relative_to(self.home_directory.resolve()):
            return False

        if not old_directory.exists(): # Check if the directory exists
            return False # Error: Directory does not exist

        if not old_directory.is_dir(): # Check if name is a directory (rather than a file)
            return False # Error: Not a directory

        try:
            old_directory.rename(new_directory)
            return True

        except FileExistsError:
            return False # Error: A directory with the new name already exists (two directories should not have the same name)

    # rmdir
    def delete_directory(self, name):
        directory_to_delete = self.current_directory / name

        directory_to_delete = directory_to_delete.resolve()
        if not directory_to_delete.is_relative_to(self.home_directory.resolve()):
            return False

        if not directory_to_delete.exists(): # Check if the directory exists
            return False # Error: Directory does not exist

        if not directory_to_delete.is_dir(): # Check if name is a directory (rather than a file)
            return False # Error: Not a directory

        try:
            directory_to_delete.rmdir() # Remove the directory (only works if the directory is empty)
            return True

        except OSError:
            return False # Error: Directory is not empty (cannot delete non-empty directories)

    # --- FILE FUNCTIONS ---

    # touch (extra function) | will create a new file if it doesn't exist (but does not open it for reading)
    def make_file(self, name):
        new_file = self.current_directory / name

        new_file = new_file.resolve()
        if not new_file.is_relative_to(self.home_directory.resolve()):
            return False

        try:
            new_file.touch(exist_ok=False) # exist_ok=False needed to stop the code from just creating a new file with that name (doesn't generate an error automatically if the same name)
            return True

        except FileExistsError: # Will stop a file with the same name from being created (two files should not have the same name)
            return False

    # del
    def delete_file(self, name):
        file_to_delete = self.current_directory / name

        file_to_delete = file_to_delete.resolve()
        if not file_to_delete.is_relative_to(self.home_directory.resolve()):
            return False


        if not file_to_delete.exists(): # Check if the file exists
            return False

        if file_to_delete.is_dir(): # Check is name is a directory (rather than a file)
            return False

        try:
            file_to_delete.unlink()
            return True
        except OSError:
            return False # File could not be deleted for some reason 

    # openRead
    def open_read(self, name):
        file_to_read = self.current_directory / name

        file_to_read = file_to_read.resolve() # When opening the file using open, need to give the actual path rather than the virtual one

        if not file_to_read.is_relative_to(self.home_directory.resolve()): # Prevent the file from being outside the virtual sandbox
            return None
        if not file_to_read.exists(): # Checks if the file exists
            return None
        if file_to_read.is_dir(): # Check if name is a directory (rather than a file)
            return None

        try:
            with open(file_to_read, 'r') as file: # Opens file in read mode
                file_contents = file.read()
            return file_contents
        except OSError:
            return None

    # openWrite
    def open_write(self, name):
            file_to_write = self.current_directory / name
    
            file_to_write = file_to_write.resolve() # When opening the file using open, need to give the actual path rather than the virtual one

            # IMPORTANT: The order of these checks matter. is_dir has to come before .exists
            if not file_to_write.is_relative_to(self.home_directory.resolve()): # Prevent the file from being outside the virtual sandbox
                return False
            if file_to_write.is_dir(): # Check if name is a directory (rather than a file)
                return False
            if file_to_write.exists(): # Checks if the file exists
                self.write_file = file_to_write
                self.write_started = False
                return True 

    
            try:
                with open(file_to_write, 'w') as file: # Used incase file doesn't exist
                    self.write_file = file_to_write
                    self.write_started = False
                return True
            except OSError:
                return False

    # Data Packet (DP)
    def write_data(self, data):
        if self.write_file is None: # No file to put data in
            return False
        if not self.write_file.exists(): # Checks to make sure file wasnt deleted after using open_write()
            return False
        if self.write_file.is_dir(): # Check if the file was deleted and a directory was made with the same name
            return False
        if not self.write_file.is_relative_to(self.home_directory.resolve()):
            return False

        try:
            if self.write_started: # This is not the first data packet
                mode = 'a'
            else:  # This is the first data packet after open_write.
                mode = 'w'
            
            with open(self.write_file, mode) as file:
                file.write(data)

            self.write_started = True  # Remember that data has now been written during this session.
            return True  # Report that the data was successfully written.
        except OSError:
            return False


# --- TESTING BLOCK --- | Please don't delete these. I worked very hard on these.
def testing_the_code():
    print("\n# --- TESTING: Initial Current Directory ---")
    print("Current Directory:", server.get_current_directory())
    # Expected: /

    print("\n# --- TESTING: get_current_directory() ---")
    print("Current Directory:", server.get_current_directory())
    # Expected: /

    print("\n# --- TESTING: make_directory() ---")
    print("Creating Documents:", server.make_directory("Documents"))
    # Expected: True
    print("Creating Downloads:", server.make_directory("Downloads"))
    # Expected: True
    print("Creating Documents Again:", server.make_directory("Documents"))
    # Expected: False
    print("Trying to create a folder outside the sandbox:", server.make_directory("../../Da No Good Bad Bad Folder"))
    # Expected: False

    print("\n# --- TESTING: list_directory() ---")
    print("Items in Home Directory:")
    items = server.list_directory()
    for item in items:
        print(item)
    # Expected:
    # Documents
    # Downloads

    print("\n# --- TESTING: count_items() ---")
    print("Number of Items:", server.count_items())
    # Expected: 2

    print("\n# --- TESTING: current_directory() ---")
    print("Changing to Documents:", server.change_directory("Documents"))
    # Expected: True
    print("Current Directory:", server.get_current_directory())
    # Expected: /Documents
    print("Changing to DatRandomFolder:", server.change_directory("DatRandomFolder"))
    # Expected: False
    print("Trying to leave the virtual sandbox:", server.change_directory("../../"))
    # Expected: False
    print("Returning to Home:", server.change_directory(".."))
    # Expected: True
    print("Current Directory:", server.get_current_directory())
    # Expected: /

    print("\n# --- TESTING: make_file() ---")
    print("Creating DaTest.txt:", server.make_file("DaTest.txt"))
    # Expected: True
    print("Creating DaTest.txt Again:", server.make_file("DaTest.txt"))
    # Expected: False
    print("Trying to create a file outside the sandbox:", server.make_file("../../NaughtyNaughty.txt"))
    # Expected: False

    print("\n# --- TESTING: check_type() ---")
    print("Checking Test.txt:", server.check_type("Test.txt"))
    # Expected: file
    print("Checking Documents:", server.check_type("Documents"))
    # Expected: directory
    print("Checking WhereIsIt.txt:", server.check_type("WhereIsIt.txt"))
    # Expected: False
    print("Checking Another Naughty File:", server.check_type("../../NaughtyAgain.txt"))
    # Expected: False

    print("\n# --- TESTING: open_write() ---")
    print("Opening Output.txt:", server.open_write("Output.txt"))
    # Expected: True
    print("Opening Documents as a file:", server.open_write("Documents"))
    # Expected: False
    print("Opening Output.txt Again:", server.open_write("Output.txt"))
    # Expected: True
    print("Trying to escape sandbox:", server.open_write("../../TooMuchNaughty.txt"))
    # Expected: False

    print("\n# --- TESTING: write_data() ---")

    print("Writing First DP:", server.write_data("Halloo?"))
    # Expected: True
    print("Writing Second DP:", server.write_data(" New Phone"))
    # Expected: True
    print("Writing Third DP:", server.write_data(" Who Dis?"))
    # Expected: True
    print("Output.txt Contents:", server.open_read("Output.txt"))
    # Expected: Halloo? New Phone Who Dis?

    print("\n# --- TESTING: open_read() ---")
    print("Reading Output.txt:", server.open_read("Output.txt"))
    # Expected: Halloo? New Phone Who Dis?
    print("Reading Documents:", server.open_read("Documents"))
    # Expected: None
    print("Reading PeekABoo.txt:", server.open_read("PeekABoo.txt"))
    # Expected: None
    print("Trying to read outside sandbox:", server.open_read("../../NaughtyIDK_howMuch.txt"))
    # Expected: None

    print("\n# --- TESTING: New open_write() ---")
    print("Opening Output.txt Again:", server.open_write("Output.txt"))
    # Expected: True
    print("Writing New Data:", server.write_data("Imma put in some more yap here"))
    # Expected: True
    print("Output.txt Contents:", server.open_read("Output.txt"))
    # Expected: Imma put in some more yap here

    print("\n# --- TESTING: word_count() ---")
    print("Opening WCTest.txt:", server.open_write("WCTest.txt"))
    # Expected: True
    print("Writing First Line:", server.write_data("Hello!\n"))
    # Expected: True
    print("Writing Second Line:", server.write_data("New Phone.\n"))
    # Expected: True
    print("Writing Third Line:", server.write_data("Who dis?"))
    # Expected: True
    print("WCTest.txt Counts:", server.word_count("WCTest.txt"))
    # Expected: (3, 5, [just some random val])
    print("WC on Documents:", server.word_count("Documents"))
    # Expected: False
    print("WC on NonExistent.txt:", server.word_count("NonExistent.txt"))
    # Expected: False
    print("WC Outside Sandbox:", server.word_count("../../HorridHenry.txt"))
    # Expected: False

    print("\n# --- TESTING: rename_directory() ---")
    print("Renaming Downloads to Files:", server.rename_directory("Downloads", "Files"))
    # Expected: True
    print("Renaming WhereDaFolder:", server.rename_directory("WhereDaFolder", "BabaYaga"))
    # Expected: False
    print("Renaming Files to already existing Documents:", server.rename_directory("Files", "Documents"))
    # Expected: False
    print("Trying to rename outside sandbox:", server.rename_directory("Files", "../../DontBeHorridHenry"))
    # Expected: False
    print("Checking Files:", server.check_type("Files"))
    # Expected: directory

    print("\n# --- TESTING: remove_directory() ---")
    print("Deleting Files:", server.delete_directory("Files"))
    # Expected: True
    print("Deleting Files Again:", server.delete_directory("Files"))
    # Expected: False
    print("Deleting Documents:", server.delete_directory("Documents"))
    # Expected: False because Documents still exists and contains no files
    print("Trying to delete outside sandbox:", server.delete_directory("../../"))
    # Expected: False

    print("\n# --- TESTING: delete_file() ---")
    print("Deleting Test.txt:", server.delete_file("Test.txt"))
    # Expected: True
    print("Deleting Test.txt Again:", server.delete_file("Test.txt"))
    # Expected: False
    print("Trying to delete a directory:", server.delete_file("Documents"))
    # Expected: False
    print("Trying to delete outside the sandbox:", server.delete_file("../../StopBeingHorridHenry.txt"))
    # Expected: False

    print("\n# --- TESTING: Da Directory After My Shenanigins ---")
    print("Current Directory:", server.get_current_directory())
    print("Items Remaining:")
    items = server.list_directory()
    for item in items:
        print(item)
    print("Final Item Count:", server.count_items())       
        

# --- MAIN FUNCTION ---
server = Server() # Just need to create the object that will have all the neccessary functions in them

# --- RFMP NETWORKING & PACKET LOGIC ---

def build(*fields):
    return ",".join(fields)


def parse(raw, maxFields):
    return raw.split(",", maxFields - 1)


def recv_exact(sock, n):
    data = b""

    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if chunk == b"":
            raise ConnectionError("Connection closed")
        data += chunk
    return data


def recv_frame(sock):
    header = recv_exact(sock, 4)
    length = struct.unpack("!I", header)[0]
    data = recv_exact(sock, length)
    return data.decode("utf-8")


def send_frame(sock, text):
    data = text.encode("utf-8")
    length = struct.pack("!I", len(data))
    sock.sendall(length + data)


def run_system_command(command_name):
    command_name = command_name.strip()
    if not command_name:
        return "EE,4,No system command provided"

    try:
        if os.name == "nt":
            command_map = {
                "whoami": "whoami",
                "date": "date /T",
                "ps": "tasklist",
                "ls": "dir",
                "pwd": "cd",
            }
            command_to_run = command_map.get(command_name.lower(), command_name)
        else:
            command_to_run = command_name

        result = subprocess.run(
            command_to_run,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stdout or "").strip()
        if not output and result.stderr:
            output = result.stderr.strip()
        if not output:
            output = "Command completed successfully"
        return f"SC,{output}"
    except Exception as exc:
        return f"EE,4,{exc}"


def route_prompt_command(server_obj, command_text):
    if command_text is None:
        return "EE,4,No command provided"

    text = command_text.strip()
    if text == "":
        return "EE,4,No command provided"

    command_parts = text.split(None, 2)
    command = command_parts[0].lower()

    if command == "mkdir":
        if len(command_parts) < 2:
            return "EE,4,Missing directory name"
        return "SC,Directory created" if server_obj.make_directory(command_parts[1]) else "EE,4,Failed to create directory"

    if command == "cd":
        if len(command_parts) < 2:
            return "EE,4,Missing directory name"
        return "SC,Directory changed" if server_obj.change_directory(command_parts[1]) else "EE,4,Failed to change directory"

    if command == "rmdir":
        if len(command_parts) < 2:
            return "EE,4,Missing directory name"
        return "SC,Directory deleted" if server_obj.delete_directory(command_parts[1]) else "EE,4,Failed to delete directory"

    if command == "del":
        if len(command_parts) < 2:
            return "EE,4,Missing file name"
        return "SC,File deleted" if server_obj.delete_file(command_parts[1]) else "EE,4,Failed to delete file"

    if command == "ren":
        if len(command_parts) < 3:
            return "EE,4,Missing old and new names"
        old_name, new_name = command_parts[1], command_parts[2]
        return "SC,File renamed" if server_obj.rename_directory(old_name, new_name) else "EE,4,Failed to rename"

    if command == "ls":
        items = server_obj.list_directory()
        return "SC," + ("\n".join(items) if items else "")

    if command == "pwd":
        return f"SC,{server_obj.get_current_directory()}"

    if command in {"whoami", "date", "ps"}:
        return run_system_command(command)

    return "EE,4,Unknown command"


def handle_packet(server_obj, packet, session):
    # session parameter added so we can encrypt/decrypt file data when secure
    if packet == "":
        return "EE,4,Empty packet"

    if packet == "End":
        return "End"

    fields = packet.split(",", 3)
    packet_type = fields[0]

    if packet_type == "SS":
        # accept both "0" (unsecured) and "1" (secured) as valid flags
        if len(fields) >= 4 and fields[1] == "RFMP" and fields[2] == "v1.0" and fields[3] in ("0", "1"):
            return "CC"  # the actual secure setup is handled in handle_client
        return "EE,0,Invalid handshake"

    if packet_type == "CM":
        if len(fields) < 3:
            return "EE,4,Malformed command packet"

        action = fields[1]
        payload = fields[2]

        if action == "prompt":
            return route_prompt_command(server_obj, payload)

        if action == "openRead":
            data = server_obj.open_read(payload)  # read the raw file contents
            if data is None:
                return "EE,1,File not found or access denied."
            # if secure mode is on, encrypt the file contents before sending
            data = encrypt_text(session, data)
            return f"SC,{data}"

        if action == "openWrite":
            return "SC" if server_obj.open_write(payload) else "EE,2,Cannot open file for writing."

        return "EE,4,Unknown command packet"

    if packet_type == "DP":
        if len(fields) < 2:
            return "EE,3,Failed to write data."
        text = fields[1]  # the raw or encrypted text from the client
        # if secure mode is on, decrypt the text before writing to disk
        try:
            text = decrypt_text(session, text)  # decrypt (or pass-through if unsecured)
        except Exception:
            return "EE,3,Failed to write data."  # decryption failed
        return "SC" if server_obj.write_data(text) else "EE,3,Failed to write data."

    return "EE,4,Unknown packet type"


def handle_client(client_socket, server_obj):
    # each client gets its own session dictionary so threads don't interfere
    session = {
        "secure": False,       # whether encryption is active for this connection
        "algorithm": None,     # "AES" or "Caesar"
        "key": None,           # the session key (bytes for AES, int for Caesar)
        "username": None,      # the client's OS username
        "client_pub": None,    # the client's public key (stored, not used to encrypt)
    }

    try:
        handshake = recv_frame(client_socket)  # first packet from client
        if handshake == "End":
            return

        # parse the SS packet to check the security flag
        ss_fields = handshake.split(",", 3)  # split into at most 4 fields
        secure_flag = ss_fields[3] if len(ss_fields) >= 4 else "0"  # default unsecured

        response = handle_packet(server_obj, handshake, session)  # validate the handshake
        if response == "End":
            return

        if response != "CC":
            send_frame(client_socket, response)  # send back the error
            return

        if secure_flag == "1":
            # --- SECURED SETUP PHASE ---
            # step 1: generate a fresh RSA key pair just for this connection
            server_private_key = generate_rsa_keypair()
            server_public_key = server_private_key.public_key()  # derive the public key

            # step 2: send CC,<server_public_key_b64> to the client
            server_pub_b64 = public_key_to_b64(server_public_key)  # serialize to base64
            send_frame(client_socket, build("CC", server_pub_b64))

            # step 3: read the EC packet from the client
            ec_raw = recv_frame(client_socket)  # expecting EC,<algo>,<enc_key>,<user:pubkey>
            ec_fields = ec_raw.split(",", 3)  # split into at most 4 fields (maxsplit 3)

            # validate the EC packet structure
            if len(ec_fields) < 4 or ec_fields[0] != "EC":
                send_frame(client_socket, build("EE", "0", "Invalid key exchange packet"))
                return

            algorithm = ec_fields[1]          # "AES" or "Caesar"
            enc_key_b64 = ec_fields[2]        # the encrypted session key in base64
            user_and_pub = ec_fields[3]        # "username:client_public_key_b64"

            # validate the algorithm choice
            if algorithm not in ("AES", "Caesar"):
                send_frame(client_socket, build("EE", "0", "Unsupported algorithm"))
                return

            # split the last field at the first colon to get username and client pub key
            colon_pos = user_and_pub.find(":")  # find the first colon
            if colon_pos == -1:
                send_frame(client_socket, build("EE", "0", "Missing client public key"))
                return

            username = user_and_pub[:colon_pos]             # everything before the colon
            client_pub_b64 = user_and_pub[colon_pos + 1:]   # everything after the colon

            try:
                # decrypt the session key using the server's private RSA key
                raw_key = rsa_decrypt_session_key(server_private_key, enc_key_b64)
            except Exception:
                send_frame(client_socket, build("EE", "0", "Failed to decrypt session key"))
                return

            # convert the raw key bytes into the right type for the algorithm
            if algorithm == "AES":
                if len(raw_key) != 32:  # AES-256 needs exactly 32 bytes
                    send_frame(client_socket, build("EE", "0", "Invalid AES key length"))
                    return
                session_key = raw_key  # keep as bytes for AES
            else:
                # Caesar key was sent as str(int).encode(), so decode it back
                try:
                    session_key = int(raw_key.decode("utf-8"))  # convert back to integer
                except ValueError:
                    send_frame(client_socket, build("EE", "0", "Invalid Caesar key"))
                    return

            # store the client's public key (just for logging, not used for encryption)
            try:
                client_pub_key = public_key_from_b64(client_pub_b64)  # deserialize to verify it is valid
            except Exception:
                send_frame(client_socket, build("EE", "0", "Invalid client public key"))
                return

            # fill in the session dictionary with the negotiated values
            session["secure"] = True
            session["algorithm"] = algorithm
            session["key"] = session_key
            session["username"] = username
            session["client_pub"] = client_pub_key

            # print info about the connection (but never print the session key!)
            print(f"Secured connection: user={username}, algorithm={algorithm}")
            print(f"Client public key: {client_pub_b64[:40]}...")  # show just a snippet

            # step 4: tell the client the setup was successful
            send_frame(client_socket, "SC")

        else:
            # --- UNSECURED MODE (original behavior) ---
            send_frame(client_socket, "CC")  # simple handshake complete

        # --- OPERATION PHASE (same loop for both modes) ---
        while True:
            packet = recv_frame(client_socket)  # wait for the next command
            if packet == "End":
                break

            response = handle_packet(server_obj, packet, session)  # pass session along
            if response == "End":
                break

            if response:
                send_frame(client_socket, response)  # send the result back

    except (ConnectionError, OSError, TimeoutError):
        pass
    finally:
        try:
            client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        client_socket.close()



def start_server(host="127.0.0.1", port=9009, backlog=5):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(backlog)
    print(f"RFMP server listening on {host}:{port}")

    try:
        while True:
            client_socket, client_address = server_socket.accept()
            print(f"Client connected: {client_address}")
            thread = threading.Thread(
                target=handle_client,
                args=(client_socket, server),
                daemon=True,
            )
            thread.start()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server_socket.close()


if __name__ == "__main__":
    start_server()