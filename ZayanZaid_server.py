# CSEC 201 - Remote File Management Protocol (RFMP)
# Date Created: 20 September 2026

# Zayan Zaid | 410005187
# Joshua Joseph Cardoz | 753003560
# First Last | UID
# First Last | UID

# --- IMPORTS ---
from pathlib import Path

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

    # pwd (extra function)
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

    # ls (extra function)
    def list_directory(self):
        items_in_directory = [] # Array[String] - Will hold the names of all the items inside the current directory

        for item in self.current_directory.iterdir():
            items_in_directory.append(item.name) # For ls, will just need the name, nothing else

        return items_in_directory
        # The content of item_in_directory can be used by whoever makes the packet/server logic - GAUTUM - DELETE THIS COMMENT WHEN YOU ARE MODIFYING THE CODE  

    # --- FOLDER FUNCTIONS ---

    # mkdir
    def make_directory(self, name):
        new_directory = self.current_directory / name

        try:
            new_directory.mkdir()
            return True

        except FileExistsError: # Will stop a directory with the same name from being created (two directories should not have the same name)
            return False

    # ren
    def rename_directory(self, oldName, newName):
        old_directory = self.current_directory / oldName
        new_directory = self.current_directory / newName

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

    # REDUNDANT - Can remove later when cleaning up the code - Keep it in jic rn
    def make_file(self, name):
        new_file = self.current_directory / name

        try:
            new_file.touch(exist_ok=False) # exist_ok=False needed to stop the code from just creating a new file with that name (doesn't generate an error automatically if the same name)
            return True

        except FileExistsError: # Will stop a file with the same name from being created (two files should not have the same name)
            return False

    # del
    def delete_file(self, name):
        file_to_delete = self.current_directory / name

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


        
        

# --- MAIN FUNCTION ---
server = Server()

print("\n# --- TESTING: Creating a folder called 'Documents' ---")
print("Making Directory (Success):", server.make_directory("Documents"))

print("\n# --- TESTING: Making a file called 'Testing.txt' in Documents ---")
print("Changing Directory (Success):", server.change_directory("Documents"))
print("Making File (Success):", server.make_file("Testing.txt"))
print("Making File (Fail):", server.make_file("Testing.txt")) # Cannot create another file with the same name in the same folder

print("\n# --- TESTING: Moving back to home directory ---")
print("Changing Directory (Success):", server.change_directory("..")) # Move to home folder
print("Currently in:", server.get_current_directory())
# print("Changing Directory (Fail):", server.change_directory("..")) # Cannot move beyond the sandbox

# print("\n# --- TESTING: Creating 'downloads' and renaming it to 'Downloads' ---")
# print("Creating Directory (Success):", server.make_directory("downloads"))
# print("Renaming Directory (Success):", server.rename_directory("downloads", "Downloads"))
# print("Renaming Directory (Fail):", server.rename_directory("Random", "Downloads")) # Folder doesnt exist

# print("\n# --- TESTING: Creating and removing a 'Desktop' directory ---")
# print("Creating Directory (Success):", server.make_directory("Desktop"))
# print("Deleting Directory (Success):", server.delete_directory("Desktop"))
# print("Deleting Directory (Fail):", server.delete_directory("Desktop")) # Folder doesnt exist

# print("\n# --- TESTING: Listing home directory ---")
# print("Items inside:", server.get_current_directory())
# items = server.list_directory()
# for item in items:
#     print(item)

print("\n# --- TESTING: Reading a file ---")
print("Moving directory to Documents (Success):", server.change_directory("Documents"))
contents = server.open_read("Testing.txt")
print("File contents:", contents)

print("\n# --- TESTING: Testing the open_write function ---")
print("Creating Output.txt:", server.open_write("Output.txt"))
print("Reading Output.txt:", server.open_read("Output.txt"))
print("Creating Output.txt again:", server.open_write("Output.txt"))  # Trying to create the file again.
print("Trying to escape sandbox:", server.open_write("../../outside.txt"))  # Testing by trying to create a file outside the home directory

print("\n# --- TESTING: DATA PACKETS ---")
print("Opening DataTest.txt:", server.open_write("DataTest.txt"))
print("First DP:", server.write_data("Hello"))  # Write the first piece of data.
print("Second DP:", server.write_data(" World"))  # Write the second piece of data.
print("Third DP:", server.write_data("!"))  # Write the third piece of data.
print("Final contents:", server.open_read("DataTest.txt"))  # Read the file to verify all data was stored.

print("\n# --- TESTING: NEW WRITE SESSION ---")
print("Opening DataTest.txt again:", server.open_write("DataTest.txt"))  # Start another writing session.
print("New first DP:", server.write_data("Fresh data"))  # Send the first DP of the new session.
print("Final contents:", server.open_read("DataTest.txt"))  # Read the file to verify that the previous contents were replaced.
