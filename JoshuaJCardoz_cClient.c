#include <sys/socket.h> //socket(), connect(), send(), recv()
#include <arpa/inet.h> //sockaddr_in, inet_pton(), htons(), htonl(), ntohl()
#include <stdlib.h> //atoi()
#include <string.h> //strlen(), memset(), strchr(), strncmp(), snprintf(), strcspn()
#include <stdint.h> //uint32_t, uint16_t
#include <unistd.h> //close()
#include <signal.h> //signal, SIGPIPE
#include <stdio.h> //printf(), fgets()

#define BUFFSIZE 4096 //max packet/message size willing to receive
#define MIN_SEPARATOR 20 //shortest "=" line, so tiny files still look like a block
#define MAX_SEPARATOR 80 //longest "=" line, so it does not wrap in a normal terminal

//this function sends 'len' bytes and keeps sending until all the bytes are sent
int send_all(int fd, const void *buff, size_t len) {
    size_t total = 0; //number of bytes successfully sent
    const char *data = buff; //convert the void buff pointer to a char pointer to read the buffer byte by byte

    while (total < len) { //loops till the total bytes is exactly 'len' bytes
        ssize_t sent = send(fd, data + total, len - total, 0);
        /*
        fd : socket,
        data + total : where in the buffer to start sending
        len - total : how many bytes remaining
        0 : no special flag*/

        if (sent <= 0) { //if the send() returns a 0 or any negative value, it means the operation failed
            return -1;
        }
        total += (size_t)sent; //add the number of bytes successfully sent
    }
    return 0; //0 means success
}

//this function receives 'len' bytes and keeps receiving until all the bytes are receieved
int recv_all(int fd, void *buff, size_t len) {
    size_t total = 0; //number of bytes received so far
    char *data = buff; //convert the void buffer pointer to a char pointer so the buffer can be read byte by byte

    while (total < len) { //loops till the total bytes is exactly 'len' bytes
        ssize_t got = recv(fd, data + total, len - total, 0);
        /*
        fd : which socket to receive from
        data + total : where to store the next bytes
        len - total : how many missing bytes to still receive
        0 : no special flags*/

        if (got <= 0) { //if recv() sends 0 or any negative value means an error occurred
            return -1;
        }
        total += (size_t)got; //add the number of bytes successfully received
    }
    return 0;
}

/*
sends one framed RFMP packet
format: [4-byte length][actual text]
for eg: text -> hello 
message: [00 00 00 05][hello]*/
int send_packet(int fd, const char *text) {
    size_t len = strlen(text); //finds how many bytes are in the string
    uint32_t netlen = htonl((uint32_t)len); //convert the length to a 32 bit integer and then convert it into a network byte order
    //htonl -> Host to Network Long

    if (send_all(fd, &netlen, sizeof netlen) < 0) return -1; //first send the 4-byte message length

    return send_all(fd, text, len); //then send the actual message
}

/*
receives one framed packet
expected format: [4-byte length][message]*/
int recv_packet(int fd, char *out, size_t outsize) {
    uint32_t netlen; //length as received from the network
    uint32_t len; //length after converting it back to the machines byte order
    //converting from network byte order to machine byte order

    if (recv_all(fd, &netlen, sizeof netlen) < 0) return -1; //first received exactly 4-byte of the header

    len = ntohl(netlen); //converts the network byte order integer back into the normal integer representation used by the machine
    //ntohl -> Network to Host Long

    if (len >= outsize) { //we need the one extra space for '\0'. so received message must be smaller than the outsize
        printf("[!] message too big: %u bytes \n", len);
        return -1;
    }

    if (recv_all(fd, out, len) < 0) return -1; //receive exactly 'len' bytes of actual message data 

    out[len] = '\0'; //recv() give us raw bytes so i had to manually add the '\0' so it becomes a logically valid C string.
    return 0;
}

/*
measures the longest line in a block of text.
used to decide how many '=' characters the separator needs, so the separator is
exactly as wide as the widest line of the file contents and no wider.*/
size_t longest_line(const char *text) {
    size_t longest = 0; //longest line found so far
    size_t current = 0; //length of the line currently being measured
    size_t i;

    for (i = 0; text[i] != '\0'; i++) {
        if (text[i] == '\n') { //reached the end of a line
            if (current > longest) {
                longest = current;
            }
            current = 0; //reset and start measuring the next line
        } else {
            current++;
        }
    }

    if (current > longest) { //the final line has no '\n' after it, so check it here
        longest = current;
    }
    return longest;
}

//prints one line made of 'length' equals signs, used above and below the file contents
void print_separator(size_t length) {
    size_t i;

    for (i = 0; i < length; i++) {
        putchar('=');
    }
    putchar('\n');
}

int main(int argc, char *argv[]) {
    int sock; //socket descriptor
    struct sockaddr_in server; //stores IPv4 server address and port
    char packet[BUFFSIZE]; //used for packets we create before sending
    char reply[BUFFSIZE]; //used for packets received from the server
    char input[256]; //used only if the user has to manually enter a file name. 256 character limit

    char *host; //cli information
    char *port; //cli information
    char *body; //used to point to the payload portion of a response
    char *filename; //file we want to read from the server

    int attempt = 0; //how many openRead commands were sent. incremented after every attempt
    int success = 0; //acts like a boolean. 0: no successful openRead yet, 1: successful openRead happened. success when received "SC"
    int connected = 1; //tracks if the connection is still live. becomes 0 if the sending or receiving fails later

    //checks whether the program has the appropriate amount of character for execution 
    //at minimum 3 argument required by default
    if (argc != 3 && argc != 4) {
        printf("Usage: %s <ip> <port> [filename]\n", argv[0]);
        return 1;
    }

    host = argv[1]; //this contains the hostname
    port = argv[2]; //this contains the port number

    signal(SIGPIPE, SIG_IGN); //Ignore SIGPIPE so sending to a closed socket returns an error instead of terminating the client. 
    //prevents the generation of a signal called SIGPIPE, which can terminate the whole program
    //SIGPIPE is generated when the client tries to send() when the server is killed

    //1. connect to server
    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) { //socket() return a negative number if creation failed
        printf("[!] could not create socket\n");
        return 1;
    }

    memset(&server, 0, sizeof server); //clears the entire server structure first, to prevent unused fields from holding garbage values
    server.sin_family = AF_INET; //AF_INET = IPv4
    server.sin_port = htons((uint16_t)atoi(port)); //the argument give the port number as a text. atoi() converts it to integer and htons converts it into network byte order.

    //converts the human readable IP address into binary IPv4 format required by sockaddr_in
    if (inet_pton(AF_INET, host, &server.sin_addr) <= 0) {
        printf("[!] bad ip address: %s: \n", host);

        //closing the already created socket (bad socket)
        close(sock);
        return 1;
    }

    /*
    attempt to make the TCP connection
    conect() expects struct sockaddr *, so sockaddr_in is cast to the generic type 
    */
    if (connect(sock, (struct sockaddr *)&server, sizeof server) < 0) {
        printf("[!] could not connect to %s:%s\n", host, port);
        close(sock);
        return 1;
    }

    //if no errors triggered, connect() succeeded
    printf("[*] connected to %s:%s\n", host, port);

    //2. setup - send start packet
    //send the RFMP startup packet, sent at the beginning by default
    if (send_packet(sock, "SS,RFMP,v1.0,0") < 0) {
        printf("[!] failed to send start packet\n");
        close(sock);
        return 1;
    }
    printf("[>] SS,RFMP,V1.0,0\n");

    //3. setup - receive confirm-connection-packet
    //waiting server to respond with framed reply
    //waiting for message beginning with CC
    if (recv_packet(sock,reply, BUFFSIZE) < 0) {
        printf("[!] no reply from server\n");
        close(sock);
        return 1;
    }

    if (strncmp(reply, "CC", 2) != 0) { //strncmp compares the first 2 character with "CC"
        printf("[!] expected CC, got %s\n", reply);
        close(sock);
        return 1;
    }
    printf("[<] CC - setup complete\n");

    for (;;) { //infinite loop. keeps running until break
        if (attempt == 0 && argc == 4) {  //if first attempt AND filename supplied in command line, use that filename
            filename = argv[3];
        } else {
            printf("\nEnter a filename to read (or press Enter to quit): "); //asks user for another filename

            //if no line could be read, stop the loop
            if(fgets(input, sizeof(input), stdin) == NULL) { //fgets reads a line from the keyboard and stores it in input 
                printf("\nNo more input\n");
                break;
            }

            //removes the extra newLine fgets() stores
            input[strcspn(input, "\n")] = '\0'; //replaces the newLine character '\n' with the termination character '\0'
            if (input[0] == '\0') { //check if the string is empty 
                printf("Done\n");
                break;
            }
            filename = input;
        }
        attempt++; //after filename acquired, the attempt counter is incremented 
        
        //4. operation: send openRead
        //creates the "CM,openRead,<filename>"
        snprintf(packet, BUFFSIZE, "CM,openRead,%s", filename); //snprintf() prevents packet from overflowing
        
        //sends the command using the framed packet system
        if (send_packet(sock,packet) < 0) {
            printf("[!] failed to send command\n");
            connected = 0;
            break;
        }
        
        //shows the packet we sent
        printf("[>] %s\n", packet);
        
        //5. operation: read reply
        //receive the openRead response
        if (recv_packet(sock, reply, BUFFSIZE) < 0) {
            printf("[!] no reply from server\n");
            connected = 0;
            break;
        }
        
        //strchr finds the first comma
        /*
        for eg: 
        reply: SC, hello world
        the body points to , hello world*/
        body = strchr(reply, ','); 
        if (body != NULL) {
            body++;
        }
        
        //if the first two character match SC its a success response
        if (strncmp(reply, "SC", 2) == 0) {
            const char *contents = body ? body : ""; //short version of if body != NULL use body else use ""
            size_t width = longest_line(contents); //separator is as wide as the widest line

            //keep the separator readable: not shorter than MIN, not wider than MAX
            if (width < MIN_SEPARATOR) {
                width = MIN_SEPARATOR;
            }
            if (width > MAX_SEPARATOR) {
                width = MAX_SEPARATOR;
            }

            printf("[<] SC - contents of %s:\n", filename);
            print_separator(width); //top border
            printf("%s", contents);

            //only add a newline if the contents do not already end with one, otherwise
            //the bottom border would be pushed down by a blank line
            if (contents[0] != '\0' && contents[strlen(contents) - 1] != '\n') {
                putchar('\n');
            }

            print_separator(width); //bottom border
            success = 1;
            break;
        } else if (strncmp(reply, "EE", 2) == 0) { //error response
            char *desc = (body != NULL) ? strchr(body, ',') : NULL; //if body exists, look inside for next comma, else set desc to null
            
            if (desc != NULL) {
                *desc = '\0'; //replaces second comma with '\0'
                desc++; //moves past the '\0'(original comma) and moves to error description
                printf("[!] EE - error %s: %s\n", body, desc);
            } else {
                printf("[!] EE - %s\n", body ? body : "unspecified error"); //EE packet sent but does not contain an error code or description
            }
            printf("[*] the connection is still open - try again\n");
        } else { //anything but "SC" or "EE" is unexpected 
            printf("[!] unexpected reply: %s\n", reply);
            break;
        }
    }

    //6. closing
    //tell server that client is closing session
    if (connected) { //if connected == 1, client sends "End"
        send_packet(sock, "End");
        printf("[>] End\n");
    }

    close(sock);
    printf("[*] session closed after %d attempt(s).\n", attempt);

    return success ? 0 : 1; //shorter version of if(success) return 0 or else return 1
}

//old main function ##DO NOT USE##
// int main(int argc, char *argv[]) {
//     if (argc != 4) {
//         printf("Usage: %s <hostname> <port> <filename>", argv[0]);
//         return 1;
//     }

//     char *host = argv[1];
//     char *port = argv[2];
//     char *filename = argv[3];

//     int sock ;
//     struct sockaddr_in server;
//     sock = socket(AF_INET, SOCK_STREAM, 0);

//     if (sock < 0) {
//         printf("Socket creation failed\n");
//         return 1;
//     }

//     server.sin_family = AF_INET;
//     server.sin_port = htons(atoi(port));

//     if (inet_pton(AF_INET, host, &server.sin_addr) <= 0) {
//         printf("Invalid  IP address\n");
//         close(sock);
//         return 1;
//     }

//     if (connect(sock, (struct sockaddr *)&server, sizeof(server)) < 0) {
//         printf("Connection failed\n");
//         close(sock);
//         return 1;
//     }
    
//     printf("Host: %s\n", host);
//     printf("Port: %s\n", port);
//     printf("Filename: %s\n", filename);

//     printf("Connected to %s:%s\n", host, port);
//     printf("Filename: %s\n", filename);

//     close(sock);

//     return 0;
// }