from flask import Flask
from gevent.wsgi import WSGIServer

app = Flask(__name__)


@app.route('/')
def hello_world():
    return "Hello World!"

if __name__ == '__main__':
    app.debug = True
    local_server = WSGIServer(('', 12345), app)
    local_server.serve_forever()
