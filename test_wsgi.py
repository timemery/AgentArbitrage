import sys
def application(environ, start_response):
    output = f"Python version: {''.join(str(sys.version))}\n".encode('utf-8')
    start_response('200 OK', [('Content-Type', 'text/plain'), ('Content-Length', str(len(output)))])
    return [output]
