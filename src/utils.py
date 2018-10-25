from driver_controller import ROOT_FOLDER

import os


class GDFile:
    def __init__(self, name, parent):
        self._name = name
        self._parent = parent

    def get_name(self):
        return self._name

    def get_parent(self):
        return self._parent


def get_remote_absolute_path(file, folders):
    curr_file = file
    path = [file['name'].strip()]
    while 'parents' in curr_file:
        stop = True
        parent_id = curr_file['parents'][0]
        if curr_file['name'] == ROOT_FOLDER:
            break
        for folder in folders:
            if parent_id == folder['id']:
                path.append(folder['name'].strip())
                curr_file = folder
                stop = False
                break
        if stop:
            break
    path = reversed(path)
    return '/'.join(path)


def build_remote_file_path(folders, files):
    file_paths = {}
    folder_paths = {}
    for f in files:
        path = get_remote_absolute_path(f, folders)
        file_paths[f['id']] = path
    for f in folders:
        path = get_remote_absolute_path(f, folders)
        folder_paths[f['id']] = path
    return file_paths, folder_paths


def build_local_file_path(local_path):
    paths = []

    for f in os.listdir(local_path):
        fpath = os.path.join(local_path, f)
        if os.path.isdir(fpath):
            p = build_local_file_path(fpath)
            paths.extend(p)
        else:
            paths.append(fpath)
    return paths
