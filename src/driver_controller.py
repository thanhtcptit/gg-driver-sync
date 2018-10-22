from structure import build_local_file_path, build_remote_file_path

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
        fields="nextPageToken, files(id, name, parents)").execute()
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


def upload_media(service, file_path, mimeType, parent_id=None):
    file_name = os.path.split(file_path)[1]
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
        print('File ID: %s' % res.get('id'))
        return res.get('id')
    return None


def create_driver_folder(service, name, parent_id):
    file_metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    file = drive_service.files().create(body=file_metadata,
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
        parent_id = create_driver_folder(service, p, remote_folders)
    return create_driver_folder(service, d, parent_id)


def download_file(service, file_id, save_path, mimeType='application/pdf'):
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(save_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print("- Download %d%%." % int(status.progress() * 100))


def sync_local(service):
    print('Getting remote files and folders.')
    folders = get_all_folders(service)
    files = get_all_files(service)
    print('Build local directory structure..')
    remote_items, _ = build_remote_file_path(folders, files)
    prefix = '/home/nero/'
    for file_id, remote_path in remote_items.items():
        local_path = prefix + remote_path
        if not os.path.exists(local_path):
            path, file_name = os.path.split(local_path)
            if not os.path.exists(path):
                os.makedirs(path)
            print("Downloading '{}' and save to '{}'".format(file_name, path))
            download_file(service, file_id, local_path)


def sync_remote(service):
    print('Getting remote files and folders.')
    folders = get_all_folders(service)
    files = get_all_files(service)
    print('Build remote directory structure..')
    prefix = '/home/nero/Documents'
    local_paths = build_local_file_path(prefix)
    remote_items, remote_folders = build_remote_file_path(folders, files)
    remote_item_paths = list(remote_items.values())
    remote_folders_paths = list(remote_folders.values())

    for path in local_paths:
        remote_path = path[path.find(os.path.split(prefix)[1]):]
        if remote_path not in remote_item_paths:
            folder_path, file_name = os.path.split(remote_path)
            if folder_path not in remote_folders_paths:
                folder_id = create_recursive_folders(
                    service, folder_path, remote_folders)
            else:
                for fid, fpath in remote_folders.items():
                    if folder_path == fpath:
                        folder_id = fid
                        break
            print("Uploading '{}' to driver location: '{}'".format(
                file_name, folder_path))
            res = upload_media(service, path, 'application/pdf', folder_id)
            if res:
                print('- Done.')


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
    # upload_file(service, 'test.pdf', 'application/pdf')


if __name__ == '__main__':
    main()
