import time

from flask import Flask, Response


app = Flask(__name__)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stream")
def stream():
    def generate():
        for chunk in (b"chunk-one\n", b"chunk-two\n", b"chunk-three\n"):
            yield chunk
            time.sleep(0.2)

    return Response(generate(), mimetype="video/mp2t")
