from datetime import datetime


def get_time():
    now = datetime.now()

    return {
        "success": True,
        "time": now.strftime("%H:%M:%S")
    }