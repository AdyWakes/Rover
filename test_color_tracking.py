import cv2
import numpy as np

cap = cv2.VideoCapture(0)

# HSV range for RED (you can adjust later)
lower = np.array([0, 120, 70])
upper = np.array([10, 255, 255])

while True:
    ret, frame = cap.read()
    if not ret:
        break

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower, upper)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        center_x = x + w // 2

        cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,0), 2)

        frame_center = frame.shape[1] // 2

        if center_x < frame_center - 50:
            print("TURN LEFT")
        elif center_x > frame_center + 50:
            print("TURN RIGHT")
        else:
            print("FORWARD")

    cv2.imshow("Tracking Test", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()