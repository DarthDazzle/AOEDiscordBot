import os
from os import walk

f = []
dir_path = os.path.dirname(os.path.realpath(__file__))
files = {}
for (dirpath, dirnames, filenames) in walk(dir_path):
    
    for f in filenames:
        if f.split(".")[1] == "ogg":
            number = f.split("_")[0]
            files[number] = f
