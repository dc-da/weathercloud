from app import create_app

app = create_app()

if __name__ == "__main__":
    cfg = app.config["WS"]
    app.run(
        host=cfg["app"]["host"],
        port=cfg["app"]["port"],
        debug=cfg["app"]["debug"],
    )
