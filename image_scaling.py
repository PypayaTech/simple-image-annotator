from PIL import Image
import PIL.ImageQt


class Resizer:
    def __init__(self, target_height, target_width):
        self._target_height = target_height
        self._target_width = target_width

    def _resize_factor(self, image):
        height_ratio = image.size[1] / self._target_height
        width_ratio = image.size[0] / self._target_width
        return max(height_ratio, width_ratio)

    def scaled_image_dims(self, image):
        r_factor = self._resize_factor(image)
        return round(image.size[1] / r_factor), round(image.size[0] / r_factor)

    def resize(self, image: PIL.Image.Image):
        scaled_h, scaled_w = self.scaled_image_dims(image)
        image = image.resize(size=(scaled_w, scaled_h))
        return image
