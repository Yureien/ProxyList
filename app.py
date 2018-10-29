import atexit
from flask import Flask, render_template
from get_proxy import ListMaker
from datetime import datetime

app = Flask(__name__)
index_http_list_maker = ListMaker(limit=0, types=['HTTP'])
index_http_list_maker.start()
index_https_list_maker = ListMaker(limit=0, types=['HTTPS'])
index_https_list_maker.start()
index_socks5_list_maker = ListMaker(limit=0, types=['SOCKS5'])
index_socks5_list_maker.start()


@app.route("/")
def index():
    index_http_list_maker.update_proxies()
    index_https_list_maker.update_proxies()
    index_socks5_list_maker.update_proxies()
    index_list = (index_http_list_maker.get_simple_list() +
                  index_https_list_maker.get_simple_list() +
                  index_socks5_list_maker.get_simple_list())
    index_list = reversed(index_list)
    current_time = datetime.now().astimezone()
    tzname = current_time.tzname()
    return render_template(
        'index.html', **locals()
    )


def exit_handler():
    index_http_list_maker.stop()
    index_https_list_maker.stop()
    index_socks5_list_maker.stop()


atexit.register(exit_handler)


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, use_reloader=False)
