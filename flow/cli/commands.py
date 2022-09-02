import fire
from flow.config.conf import PROJECT_FILES, APP_FILES
import os
from http.server import HTTPServer
from flow.http.server import Server
from fconfig.fsettings import SERVER_PORT, SERVER_HOST


class Command:
    def initproject(self):
        for file in PROJECT_FILES:
            if not os.path.exists(file.dirname):
                os.mkdir(file.dirname)

            if os.path.exists(file.dirname):
                with open(os.path.join(file.dirname, file.filename), 'w+') as f:
                    with open(file.filepath, 'r') as sf:
                        f.write(sf.read())

    def startserver(self):
        web_server = HTTPServer((SERVER_HOST, SERVER_PORT), Server)
        print(f"Server started http://{SERVER_HOST}:{SERVER_PORT}\nType ctrl+c to stoping.")

        try:
            web_server.serve_forever()
        except KeyboardInterrupt:
            pass

        web_server.server_close()
        print("Server stopped.")

    def createapp(self, app_name: str):
        for appfile in APP_FILES:
            if not os.path.exists(app_name):
                os.mkdir(app_name)

            if os.path.exists(app_name):
                with open(os.path.join(app_name, appfile.filename), 'w+') as f:
                    if appfile.filepath:
                        with open(appfile.filepath, 'r') as sf:
                            f.write(sf.read())


fire.Fire(Command())