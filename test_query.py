import sys
import traceback
import io

# Setup to force flush output
with open("err.txt", "w", encoding="utf-8") as f:
    try:
        from Scripts.chatbot_application import generate_response
        res = generate_response('what is encryption', 'Detailed')
        f.write("OK: " + str(res))
    except Exception as e:
        f.write(traceback.format_exc())
