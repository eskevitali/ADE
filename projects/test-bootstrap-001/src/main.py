from http.server import BaseHTTPRequestHandler, HTTPServer


class HelloHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"hello")


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8000), HelloHandler).serve_forever()