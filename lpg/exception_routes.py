from lpg import app


@app.errorhandler(405)
def error405(error):
    return "Method Not allowed "


@app.errorhandler(500)
def error500(error):
    return "my custom 500 error"


@app.errorhandler(404)
def error404(error):
    return "402 Not Found"
