import cv2

def resize_image(img, size):
    try:
        w_final, h_final = size
        imgmat = cv2.imread(img)
        if imgmat is None:
            return None
        if h_final < 1:
            h, w, d = imgmat.shape
            scale = w_final / float(w)
            h_final = int(h * scale)
        res = cv2.resize(imgmat, (w_final, h_final))
        return res
    except cv2.error as exc:
        return None
