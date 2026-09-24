import socket as so
import struct as st
import sys 

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

def setup(sock):
    send_frame(sock, build("SS", "RFMP", "v1.0", "0")) #this sends SS,RFMP,v1.0,0
    
    reply = recv_frame(sock) #waits for server reply
    parts = parse(reply, 3) #parses server reply and breaks it into at most 3 pieces

    if parts[0] == "CC": #checks the first element if CC -> success code
        print("Handshake complete!")
        return True
    elif parts[0] == "EE": #checks the first element if EE -> error code (something went wrong)
        code = parts[1] if len(parts) > 1 else "" #extracts error code 
        description = parts[2] if len(parts) > 2 else "" #extracts description
        print("Error: ", code, description)
        return False
    else: #if the server sends anything else
        print("Unexpected packet")
        return False

def handle_response(sock): #default response handler after sending commands
    reply = recv_frame(sock) 
    parts = parse(reply, 3)

    if parts[0] == "SC": #checks first element if "SC" -> success
        if len(parts) > 1: #checks for payload 
            print(parts[1])
        return True
    elif parts[0] == "EE": #checks first element if "EE" -> error code
        code = parts[1] if len(parts) > 1 else "" #extracts error code
        description = parts[2] if len(parts) > 2 else "" #extracts description
        print("Error: ", code, description)
        return False
    else:
        print("Unexpected error")
        return False

def openRead(sock, filename): #takes input of socket and filename
    send_frame(sock, build("CM", "openRead", filename)) #if filename is hello.txt this sends CM,openRead,hello.txt

    reply = recv_frame(sock) #waits for server reply
    parts = parse(reply, 2) #parses server reply and breaks into at most 2 parts

    if parts[0] == "SC": #if success it prints the file which is parts[1]
        if len(parts) > 1:
            print(parts[1])
        return True

    elif parts[0] == "EE": #if error it outputs the error code
        code = parts[1] if len(parts) > 1 else ""
        print("Error", code)
        return False

    else: #if the server sends anything else it outputs this
        print("Unexpected error")
        return False

def openWrite(sock, filename): #takes input of sock and filename
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
    print("Type \'.\' in a new line when finished.")

    lines = [] 

    while True:
        line = input() #keeps collecting lines
        if line == ".": #breaks if input is "."
            break
        lines.append(line)

    text = "\n".join(lines) #joins the message new lines into a single message
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

def menu(sock): #main user interface options
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
        print("1. mkdir")
        print("2. cd")
        print("3. rmdir")
        print("4. del")
        print("5. ren")
        print("6. ls")
        print("7. pwd")
        print("8. whoami")
        print("9. date")
        print("10. ps")
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

            openWrite(sock, filename)

        elif choice == "11":
            filename = input("Filename: ").strip()
            if filename == "":
                print("Filename cannot be empty")
                continue

            openRead(sock, filename)

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

    if setup(sock):
        menu(sock)

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
