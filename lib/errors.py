def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Not found"}, 404

    @app.errorhandler(400)
    def bad_request(e):
        return {"error": "Bad request"}, 400

    @app.errorhandler(500)
    def internal_error(e):
        return {"error": "Internal server error"}, 500
