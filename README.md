Google Driver sync tool
====================

How to run
--------------

1. Generate `credentials.json` and `token.json` from this [tutorial](https://developers.google.com/drive/api/v3/quickstart/python) and move to config dir.
2. Specify which directories/files to sync between local storage and gg driver in `driver_controller.py`.
3. Run `python driver_controller.py --op=(sync_remote|sync_local)` to sync between local and remote.