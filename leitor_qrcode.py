import cv2
from pyzbar.pyzbar import decode

def leitor_qrcode():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("❌ Não foi possível acessar a câmera")
        return

    while True:
        ret, frame = cap.read()

        if not ret:
            continue

        for codigo in decode(frame):
            dados = codigo.data.decode('utf-8')
            print(f'QR Code detectado: {dados}')
            cap.release()
            cv2.destroyAllWindows()
            return

        cv2.imshow('Leitor de QR Code', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    leitor_qrcode()
