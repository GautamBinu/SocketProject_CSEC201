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


        
        

# --- MAIN FUNCTION ---
server = Server()

