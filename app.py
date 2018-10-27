import atexit
from flask import Flask, render_template, request
from get_proxy import ListMaker
from datetime import datetime

app = Flask(__name__)
index_list_maker = ListMaker(limit=0)
index_list_maker.start()


@app.route("/")
def index():
    index_list_maker.update_proxies()
    index_list = index_list_maker.get_simple_list()
    index_list = reversed(index_list)
    current_time = datetime.now().astimezone()
    tzname = current_time.tzname()
    return render_template(
        'index.html', **locals()
    )


def exit_handler():
    index_list_maker.stop()


atexit.register(exit_handler)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
