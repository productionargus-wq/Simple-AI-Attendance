from app import app

if __name__ == '__main__':
    print("==================================================")
    print("Starting ARGUS CNC™ - Argus Attendance Intelligence version 2.0.0")
    print("URL: http://127.0.0.1:5000")
    print("==================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
