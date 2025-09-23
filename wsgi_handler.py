def application(environ, start_response):
    status = '200 OK'
    output = b'Hello World! If you see this, the WSGI handler is working.'
    response_headers = [('Content-type', 'text/plain'),
                        ('Content-Length', str(len(output)))]
    start_response(status, response_headers)
    return [output]
