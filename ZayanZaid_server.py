# CSEC 201 - Remote File Management Protocol (RFMP)
# Date Created: 20 September 2026

# Zayan Zaid | 410005187
# First Last | UID
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

    def get_current_directory(self): # Note: This function will return a virtual "current directory" rather than the REAL actual directory (of the computer)
        relative_path = self.current_directory.relative_to(self.home_directory)

        if relative_path == Path("."):
            return "/"
        
        return "/" + str(relative_path)

    def make_directory(self, name):
        new_directory = self.current_directory / name

        try:
            new_directory.mkdir()
            return True

        except FileExistsError: # Will stop a directory with the same name from being created (two directories should not have the same name)
            return False

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

# --- MAIN FUNCTION ---
print("")
server = Server()

print("Current directory:", server.get_current_directory())
#/

print("Creating documents directory...")
print("Success:", server.make_directory("documents"))
#/
    #documents/

print("Changing to documents...")
print("Success:", server.change_directory("documents"))
#/
    #documents/
# Current Directoy: documents

print("Current directory:", server.get_current_directory())
# Printing the current directory after changing to documents (making sure it doesnt go above home directory)

print("Changing to parent directory...")
print("Success:", server.change_directory(".."))
# Changing to parent directory (should be home directory)
# Current Directory: /

print("Current directory:", server.get_current_directory())
#Should get home directory (/)

print("Trying to leave home...")
print("Success:", server.change_directory(".."))
# Should fail

print("Current directory:", server.get_current_directory())
# Current Directory: / (should still be home directory)

# --Testing renaming directories--
#Renaming documents to downloads
print("Renaming documents to downloads...")
print("Success:", server.rename_directory("documents", "downloads"))
# Renaming a new directory downloads (should fail)
print("Success:", server.make_directory("downloads"))



