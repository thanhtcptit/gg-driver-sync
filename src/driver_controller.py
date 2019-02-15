from utils import *

from googleapiclient.discovery import build, MediaFileUpload

from httplib2 import Http
from oauth2client import file, client, tools
from apiclient.http import MediaIoBaseDownload

import os
import io
import argparse


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--op',
        choices=('list_files', 'list_folders',
                 'sync_local', 'sync_remote'))

    return parser.parse_args()


# If modifying these scopes, delete the file token.json.
SCOPES = 'https://www.googleapis.com/auth/drive'
SYNC_FOLDER = '/home/nero/Documents/Driver'
ROOT_FOLDER = os.path.split(SYNC_FOLDER)[1]
ACCEPT_EXT = ['.pdf', '.epub', '.doc', '.docx', '.odt', '.pptx']


def build_drive():
    store = file.Storage('../config/token.json')
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets(
            '../config/credentials.json', SCOPES)
        creds = tools.run_flow(flow, store)
    service = build('drive', 'v3', http=creds.authorize(Http()))
    return service


def get_list_items(service, query):
    results = service.files().list(
        q=query,
        pageSize=300,
        fields="nextPageToken, files(id, name, parents, size)").execute()
    items = results.get('files', [])
    return items


def get_all_files(service):
    items = get_list_items(
        service,
        query="mimeType!='application/vnd.google-apps.folder' " +
              "and modifiedTime >='2018-09-01T12:00:00-08:00'")
    return items


def get_all_folders(service):
    items = get_list_items(
        service,
        query="mimeType='application/vnd.google-apps.folder' " +
              "and modifiedTime >='2018-09-01T12:00:00-08:00'")
    return items


def list_files(service):
    items = get_all_files(service)

    if not items:
        print('No files found.')
    else:
        print('Files:')
        for item in items:
            if 'parents' not in item:
                item.update({'parents': 'None'})
            print("{} ({}) - Parent's ID: {}".format(
                item['name'], item['id'], item['parents']))


def list_folders(service):
    items = get_all_folders(service)

    if not items:
        print('No files found.')
    else:
        print('Folders:')
        for item in items:
            print("{} ({}) - Parent's ID: {}".format(
                item['name'], item['id'], item['parents']))


def compare_file(local_path, remote_file):
    local_size = os.path.getsize(local_path)
    remote_size = remote_file['size']
    if int(local_size) != int(remote_size):
        print('Diff: {}'.format(local_path))
        print('- Local : {} - Remote: {}'.format(local_size, remote_size))
        return -1
    return 1


def upload_media(service, file_path, mimeType, parent_id=None):
    file_name = os.path.split(file_path)[1]
    _, ext = os.path.splitext(file_name)
    if ext not in ACCEPT_EXT:
        print('- Skip ')
        return

    if parent_id:
        metadata = {
            'name': file_name,
            'parents': [parent_id]
        }
    else:
        metadata = {
            'name': file_name,
        }

    media = MediaFileUpload(
        file_path, mimetype=mimeType, resumable=True)
    res = service.files().create(
        body=metadata, media_body=media, fields='id').execute()

    if res:
        print('- File ID: %s.' % res.get('id'))
    else:
        print('- Error.')


def delete_media(service, remote_file):
    print('Delete ', remote_file['name'])
    try:
        service.files().delete(fileId=remote_file['id']).execute()
        print('- Done.')
        return 1
    except Exception as e:
        print('- Error: %s' % e)
    return 0


def update_media(service, file_path, mime_type, folder_id, remote_file):
    print("Update '{}' to driver".format(file_path))
    res = delete_media(service, remote_file)
    if res:
        upload_media(service, file_path, mime_type, folder_id)


def create_driver_folder(service, name, parent_id):
    file_metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    file = service.files().create(body=file_metadata,
                                  fields='id').execute()
    print('Folder ID: %s' % file.get('id'))
    return file.get('id')


def create_recursive_folders(service, folder_path, remote_folders):
    p, d = os.path.split(folder_path)
    is_exist = False
    for fid, folder in remote_folders.items():
        if p == folder:
            is_exist = True
            parent_id = fid
            break
    if not is_exist:
        parent_id = create_recursive_folders(service, p, remote_folders)
    return create_driver_folder(service, d, parent_id)


def download_file(service, file_id, local_path, mimeType='application/pdf'):
    path, file_name = os.path.split(local_path)
    _, ext = os.path.splitext(file_name)
    if ext not in ACCEPT_EXT:
        print('- Skip ', local_path)
        return
    if not os.path.exists(path):
        os.makedirs(path)

    print("Downloading '{}' and save to '{}'".format(file_name, path))
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(local_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print("- Download %d%%." % int(status.progress() * 100))
    except Exception as e:
        print('- Error', e)


def sync_local(service):
    print('Getting remote files and folders.')
    folders = get_all_folders(service)
    files = get_all_files(service)
    print('Build local directory structure..')
    remote_items, _ = build_remote_file_path(folders, files)
    prefix = os.path.split(SYNC_FOLDER)[0]
    for file_id, file_content in remote_items.items():
        remote_path, remote_item = file_content
        local_path = os.path.join(prefix, remote_path)
        if not os.path.exists(local_path):
            download_file(service, file_id, local_path)
        else:
            res = compare_file(local_path, remote_item)
            if res == -1:
                os.remove(local_path)
                download_file(service, file_id, local_path)


def sync_remote(service):
    print('Getting remote files and folders.')
    folders = get_all_folders(service)
    files = get_all_files(service)
    print('Build remote directory structure..')
    local_paths = build_local_file_path(SYNC_FOLDER)
    remote_items, remote_folders = build_remote_file_path(folders, files)
    remote_item_paths = {p: i for p, i in remote_items.values()}
    remote_folders_paths = set(remote_folders.values())

    for path in local_paths:
        remote_path = path[path.find(os.path.split(SYNC_FOLDER)[1]):]
        folder_path, file_name = os.path.split(remote_path)
        if remote_path not in remote_item_paths:
            if folder_path not in remote_folders_paths:
                folder_id = create_recursive_folders(
                    service, folder_path, remote_folders)
                remote_folders_paths.add(folder_path)
            else:
                for fid, fpath in remote_folders.items():
                    if folder_path == fpath:
                        folder_id = fid
                        break
            print("Uploading '{}' to driver location: '{}'".format(
                file_name, folder_path))
            upload_media(service, path, 'application/pdf', folder_id)
        else:
            res = compare_file(path, remote_item_paths[remote_path])
            if res == -1:
                for fid, fpath in remote_folders.items():
                    if folder_path == fpath:
                        folder_id = fid
                        break
                update_media(
                    service, path, 'application/pdf', folder_id,
                    remote_item_paths[remote_path])


def main():
    args = _parse_args()
    service = build_drive()
    if args.op == 'list_files':
        list_files(service)
    elif args.op == 'list_folders':
        list_folders(service)
    elif args.op == 'sync_local':
        sync_local(service)
    else:
        sync_remote(service)


if __name__ == '__main__':
    main()
