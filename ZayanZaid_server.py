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

    def list_directory(self):
        items_in_directory = [] # Array[String] - Will hold the names of all the items inside the current directory

        for item in self.current_directory.iterdir():
            items_in_directory.append(item.name) # For ls, will just need the name, nothing else

        return items_in_directory
        # The content of item_in_directory can be used by whoever makes the packet/server logic - GAUTUM - DELETE THIS COMMENT WHEN YOU ARE MODIFYING THE CODE
        


    # --- FOLDER FUNCTIONS ---

    def make_directory(self, name):
        new_directory = self.current_directory / name

        try:
            new_directory.mkdir()
            return True

        except FileExistsError: # Will stop a directory with the same name from being created (two directories should not have the same name)
            return False

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

    # --- FILE FUNCTIONS ---
    def make_file(self, name):
        new_file = self.current_directory / name

        try:
            new_file.touch(exist_ok=False) # exist_ok=False needed to stop the code from just creating a new file with that name (doesn't generate an error automatically if the same name)
            return True

        except FileExistsError: # Will stop a file with the same name from being created (two files should not have the same name)
            return False

    def delete_file(self, name):
        file_to_delete = self.current_directory / name

        if not file_to_delete.exists(): #Check if the file exists
            return False

        if file_to_delete.is_dir(): # Check is name is a directory (rather than a file)
            return False

        try:
            file_to_delete.unlink()
            return True
        except OSError:
            return False # File could not be deleted for some reason 




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
print("Changing Directory (Fail):", server.change_directory("..")) # Cannot move beyond the sandbox

print("\n# --- TESTING: Creating 'downloads' and renaming it to 'Downloads' ---")
print("Creating Directory (Success):", server.make_directory("downloads"))
print("Renaming Directory (Success):", server.rename_directory("downloads", "Downloads"))
print("Renaming Directory (Fail):", server.rename_directory("downloads", "Downloads")) # Folder doesnt exist

print("\n# --- TESTING: Creating and removing a 'Desktop' directory ---")
print("Creating Directory (Success):", server.make_directory("Desktop"))
print("Deleting Directory (Success):", server.delete_directory("Desktop"))
print("Deleting Directory (Fail):", server.delete_directory("Desktop")) # Folder doesnt exist

print("\n# --- TESTING: Listing home directory ---")
print("Items inside:", server.get_current_directory())
items = server.list_directory()
for item in items:
    print(item)











