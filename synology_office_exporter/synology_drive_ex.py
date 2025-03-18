from synology_drive_api.drive import SynologyDrive


class SynologyDriveEx(SynologyDrive):
    def shared_with_me(self):
        """
        get shared folder info
        :return: [{'file_id': 'xxx', 'name': 'xxx', 'owner': {'name': 'xxx'}}]
        """
        # {"include_transient":true}
        api_name = 'SYNO.SynologyDrive.Files'
        endpoint = 'entry.cgi'
        params = {'api': api_name, 'version': 2, 'method': 'shared_with_me', 'filter': {}, 'sort_direction': 'asc',
                  'sort_by': 'name', 'offset': 0, 'limit': 1000}
        resp = self.session.http_get(endpoint, params=params)

        if not resp['success']:
            raise Exception('Get shared_with_me info failed.')

        if resp['data']['total'] == 0:
            return {}

        return resp['data']['items']
