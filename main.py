import os
import sys
import random
import PIL
import PIL.Image
from PIL import ImageQt
from PySide6 import QtGui, QtCore, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QColorDialog, QSpinBox
from image_scaling import Resizer


class ImageAnnotator(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.setWindowTitle('Simple Image Annotator')
        self._target_height, self._target_width = 1920, 1080
        self._is_saved = True
        self._mode = 'keypoints'
        self._class_colors = []
        self._current_image_index = None
        self._image_filenames = None
        self._dragged_keypoint_index = None
        self._bounding_box_start = None
        self._bounding_box_end = None
        self._dragged_box_index = None
        self._dragged_box_corner = None
        self._dragging_corner = False

    def initUI(self):
        # Create a QGraphicsView to display the image
        self._graphics_view = QtWidgets.QGraphicsView(self)
        self._graphics_view.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.setCentralWidget(self._graphics_view)
        self._scene = QtWidgets.QGraphicsScene(self)
        self._graphics_view.setScene(self._scene)
        self._m_pixmap = QtGui.QPixmap()
        self._image_item = QtWidgets.QGraphicsPixmapItem(self._m_pixmap)
        self._scene.addItem(self._image_item)

        # Create a QDockWidget to hold the keypoints list
        self._coordinates_dock = QtWidgets.QDockWidget("Points and boxes", self)
        self._coordinates_dock.setFixedWidth(250)
        self.addDockWidget(Qt.RightDockWidgetArea, self._coordinates_dock)

        # Create a QListWidget to display the key points
        self._coordinates_list = QtWidgets.QListWidget()
        self._coordinates_list.itemChanged.connect(self.update_image)
        self._coordinates_dock.setWidget(self._coordinates_list)

        # Create a QDockWidget to hold the image list
        self._image_list_dock = QtWidgets.QDockWidget("Image list", self)
        self._image_list_dock.setFixedWidth(250)
        self.addDockWidget(Qt.RightDockWidgetArea, self._image_list_dock)

        # Create a QListWidget to display the image names
        self._image_list = QtWidgets.QListWidget()
        self._image_list_dock.setWidget(self._image_list)

        # Create the left toolbar
        self.create_left_toolbar()

        # Connect events to the appropriate functions for adding and moving key points
        self._graphics_view.mousePressEvent = self.mouse_press
        self._graphics_view.mouseMoveEvent = self.mouse_move
        self._graphics_view.mouseReleaseEvent = self.mouse_release
        self._image_list.itemClicked.connect(self.go_to_image)

        self.show()

    def create_left_toolbar(self):
        self._left_toolbar = QtWidgets.QToolBar("Left Toolbar")
        self._left_toolbar.setIconSize(QtCore.QSize(32, 32))
        self._left_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._left_toolbar.setFloatable(False)
        self._left_toolbar.setMovable(False)
        self.addToolBar(Qt.LeftToolBarArea, self._left_toolbar)

        # Create the "Open dir" action
        self._openDirAction = QAction(QtGui.QIcon(os.path.join("resources", "icons", "open.png")), "Open dir", self)
        self._openDirAction.triggered.connect(self.open_dir)
        self._left_toolbar.addAction(self._openDirAction)

        # Create the "Next image" action
        self._nextImageAction = QAction(QtGui.QIcon(os.path.join("resources", "icons", "next.png")), "Next image", self)
        self._nextImageAction.triggered.connect(self.next_image)
        self._left_toolbar.addAction(self._nextImageAction)

        # Create the "Prev image" action
        self._prevImageAction = QAction(QtGui.QIcon(os.path.join("resources", "icons", "prev.png")), "Prev image", self)
        self._prevImageAction.triggered.connect(self.prev_image)
        self._left_toolbar.addAction(self._prevImageAction)

        # Create the "Save" action
        self._saveAction = QAction(QtGui.QIcon(os.path.join("resources", "icons", "save.png")), "Save", self)
        self._saveAction.triggered.connect(self.save)
        self._left_toolbar.addAction(self._saveAction)

        # Create the "Change color" action
        self._changeColorAction = QAction(QtGui.QIcon(os.path.join("resources", "icons", "color.png")),
                                          "Change point color", self)
        self._changeColorAction.triggered.connect(self._select_point_color)
        self._changeColorAction.setProperty('background-color', QtCore.Qt.red)
        self._left_toolbar.addAction(self._changeColorAction)

        # Create the "Change point size" action
        self._point_size_spinbox = QSpinBox()
        self._point_size_spinbox.setRange(1, 100)
        self._point_size_spinbox.setValue(5)
        self._left_toolbar.addWidget(self._point_size_spinbox)

        # Create the "Switch Mode" action
        self._switchModeAction = QAction(QtGui.QIcon(os.path.join("resources", "icons", "next.png")),
                                         "Switch Mode", self)
        self._switchModeAction.triggered.connect(self.switch_mode)
        self._left_toolbar.addAction(self._switchModeAction)

    def switch_mode(self):
        self._mode = 'keypoints' if self._mode == 'bounding_boxes' else 'bounding_boxes'
        self._switchModeAction.setText(f'Switch Mode (Current: {self._mode})')

    def open_dir(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        directory = QFileDialog.getExistingDirectory(self, "Select a directory", options=options)
        if directory:
            self._coordinates_list.clear()
            with open(os.path.join(directory, "classes.txt"), "r") as file:
                self._class_names = file.readlines()
            self._current_directory = directory
            self._image_filenames = [
                name for name in os.listdir(directory)
                if any(name.endswith(ext) for ext in ['.jpg', '.png', '.gif', '.jpeg'])
            ]
            self._current_image_index = 0
            for i in range(len(self._class_names)):
                color = "#" + "".join([random.choice("0123456789ABCDEF") for _ in range(6)])
                self._class_colors.append(color)
            self._image_list.clear()
            for name in self._image_filenames:
                self._image_list.addItem(name)
            self._current_image_item = self._image_list.item(0)
            self._current_image_item.setSelected(True)
            self.load_image()

    def go_to_image(self, item):
        if not self._is_saved:
            if self._ask_for_saving() == QtWidgets.QMessageBox.Yes:
                self.save()
            self._is_saved = True
        self._current_image_index = self._image_list.row(item)
        self._coordinates_list.clear()
        self._current_image_item = item
        self.load_image()

    def next_image(self):
        if self._current_image_index is None or self._image_filenames is None:
            return
        if self._current_image_index == len(self._image_filenames) - 1:
            return
        if not self._is_saved:
            if self._ask_for_saving() == QtWidgets.QMessageBox.Yes:
                self.save()
            self._is_saved = True
        self._coordinates_list.clear()
        self._current_image_index += 1
        self._current_image_item = self._image_list.item(self._current_image_index)
        self._current_image_item.setSelected(True)
        self.load_image()

    def prev_image(self):
        if self._current_image_index is None or self._image_filenames is None:
            return
        if self._current_image_index == 0:
            return
        if not self._is_saved:
            if self._ask_for_saving() == QtWidgets.QMessageBox.Yes:
                self.save()
            self._is_saved = True
        self._coordinates_list.clear()
        self._current_image_index -= 1
        self._current_image_item = self._image_list.item(self._current_image_index)
        self._current_image_item.setSelected(True)
        self.load_image()

    def save(self):
        current_image_name = self._image_filenames[self._current_image_index]
        default_name = os.path.splitext(current_image_name)[0] + '.txt'
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', default_name, 'Text Files (*.txt)')
        if filename:
            with open(filename, 'w') as file:
                for i in range(self._coordinates_list.count()):
                    item_text = self._coordinates_list.item(i).text().split(',')
                    class_idx = item_text[0]
                    if len(item_text) == 3:  # Keypoint
                        normalized_x, normalized_y = item_text[1], item_text[2]
                        file.write(f"{class_idx}, {normalized_x}, {normalized_y}\n")
                    elif len(item_text) == 5:  # Bounding box
                        normalized_top_left_x, normalized_top_left_y = item_text[1], item_text[2]
                        normalized_bottom_right_x, normalized_bottom_right_y = item_text[3], item_text[4]
                        file.write(
                            f"{class_idx}, {normalized_top_left_x}, {normalized_top_left_y}, {normalized_bottom_right_x}, {normalized_bottom_right_y}\n")
                self._is_saved = True

    def _select_point_color(self):
        class_name, ok = QtWidgets.QInputDialog.getItem(self, "Select class dialog",
                                                        "List of classes", self._class_names, 0, False)
        if ok:
            class_idx = self._class_names.index(class_name)
            color = QColorDialog.getColor(QtGui.QColor(self._class_colors[class_idx]), self, "Select point color")
            if color.isValid():
                self._class_colors[class_idx] = color.name()
                for i in range(self._coordinates_list.count()):
                    item = self._coordinates_list.item(i)
                    item_text = item.text().split(',')
                    item_class_idx = int(item_text[0])
                    if item_class_idx == class_idx:
                        if len(item_text) == 3:  # Keypoint
                            normalized_x, normalized_y = item_text[1], item_text[2]
                            item.setText(f"{item_class_idx}, {normalized_x}, {normalized_y}")
                        elif len(item_text) == 5:  # Bounding box
                            normalized_top_left_x, normalized_top_left_y = item_text[1], item_text[2]
                            normalized_bottom_right_x, normalized_bottom_right_y = item_text[3], item_text[4]
                            item.setText(
                                f"{item_class_idx}, "
                                f"{normalized_top_left_x}, "
                                f"{normalized_top_left_y}, "
                                f"{normalized_bottom_right_x}, "
                                f"{normalized_bottom_right_y}"
                            )

                self.update_image()

    def mouse_press(self, event):
        if event.button() != Qt.LeftButton:
            return

        x = int(self._graphics_view.mapToScene(event.pos()).x())
        y = int(self._graphics_view.mapToScene(event.pos()).y())
        normalized_x, normalized_y = x / self._m_pixmap.width(), y / self._m_pixmap.height()

        # If click is outside the image, just return and ignore the event
        if x < 0 or x >= self._m_pixmap.width() or y < 0 or y >= self._m_pixmap.height():
            return

        if self._mode == 'keypoints':
            # Check if the user clicked on an existing keypoint
            for i in range(self._coordinates_list.count()):
                item = self._coordinates_list.item(i)
                if len(item.text().split(',')) != 3:  # Bounding box
                    continue
                class_idx, item_normalized_x, item_normalized_y = item.text().split(',')
                item_x, item_y = int(float(item_normalized_x) * self._m_pixmap.width()), int(
                    float(item_normalized_y) * self._m_pixmap.height())
                if abs(item_x - x) < 5 and abs(item_y - y) < 5:  # adjust the threshold (5) as needed
                    self._dragged_keypoint_index = i
                    return

            class_name, ok = QtWidgets.QInputDialog.getItem(self, "Select class dialog",
                                                            "List of classes", self._class_names, 0, False)
            if not ok:
                return
            class_idx = self._class_names.index(class_name)
            item = QtWidgets.QListWidgetItem(f"{class_idx}, {normalized_x:.4f}, {normalized_y:.4f}")
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
            self._coordinates_list.addItem(item)
            self.update_image()
            self.update()

        elif self._mode == 'bounding_boxes':
            # Check if the user clicked on a corner of an existing bounding box
            for i in range(self._coordinates_list.count()):
                item = self._coordinates_list.item(i)
                if len(item.text().split(',')) != 5:  # Keypoint
                    continue
                class_idx, normalized_top_left_x, normalized_top_left_y, \
                    normalized_bottom_right_x, normalized_bottom_right_y = item.text().split(',')
                top_left_x, top_left_y = int(float(normalized_top_left_x) * self._m_pixmap.width()), int(
                    float(normalized_top_left_y) * self._m_pixmap.height())
                bottom_right_x, bottom_right_y = int(float(normalized_bottom_right_x) * self._m_pixmap.width()), int(
                    float(normalized_bottom_right_y) * self._m_pixmap.height())

                top_right_x, top_right_y = bottom_right_x, top_left_y
                bottom_left_x, bottom_left_y = top_left_x, bottom_right_y

                if abs(top_left_x - x) < 5 and abs(top_left_y - y) < 5:  # Top left corner
                    self._dragged_box_index = i
                    self._dragged_box_corner = 'top_left'
                    return
                elif abs(bottom_right_x - x) < 5 and abs(bottom_right_y - y) < 5:  # Bottom right corner
                    self._dragged_box_index = i
                    self._dragged_box_corner = 'bottom_right'
                    return
                elif abs(top_right_x - x) < 5 and abs(top_right_y - y) < 5:  # Top right corner
                    self._dragged_box_index = i
                    self._dragged_box_corner = 'top_right'
                    return
                elif abs(bottom_left_x - x) < 5 and abs(bottom_left_y - y) < 5:  # Bottom left corner
                    self._dragged_box_index = i
                    self._dragged_box_corner = 'bottom_left'
                    return

            # Set the start position of the bounding box
            self._bounding_box_start = self._graphics_view.mapToScene(event.pos()).toPoint()

    def mouse_move(self, event):
        x, y = int(self._graphics_view.mapToScene(event.pos()).x()), int(
            self._graphics_view.mapToScene(event.pos()).y())
        normalized_x, normalized_y = x / self._m_pixmap.width(), y / self._m_pixmap.height()

        if self._mode == 'keypoints':
            if self._dragged_keypoint_index is not None:
                item = self._coordinates_list.item(self._dragged_keypoint_index)
                class_idx = item.text().split(',')[0]
                item.setText(f"{class_idx}, {normalized_x:.4f}, {normalized_y:.4f}")
                self.update_image()
        elif self._mode == 'bounding_boxes':
            if self._dragged_box_index is not None:
                self._dragging_corner = True
                item = self._coordinates_list.item(self._dragged_box_index)
                class_idx, top_left_x, top_left_y, bottom_right_x, bottom_right_y = [elem.strip() for elem in item.text().split(',')]
                if self._dragged_box_corner == 'top_left':
                    item.setText(f"{class_idx}, {normalized_x:.4f}, {normalized_y:.4f}, {bottom_right_x}, {bottom_right_y}")
                elif self._dragged_box_corner == 'bottom_right':
                    item.setText(f"{class_idx}, {top_left_x}, {top_left_y}, {normalized_x:.4f}, {normalized_y:.4f}")
                elif self._dragged_box_corner == 'top_right':
                    item.setText(f"{class_idx}, {top_left_x}, {normalized_y:.4f}, {normalized_x:.4f}, {bottom_right_y}")
                elif self._dragged_box_corner == 'bottom_left':
                    item.setText(f"{class_idx}, {normalized_x:.4f}, {top_left_y}, {bottom_right_x}, {normalized_y:.4f}")
                self.update_image()
            else:
                if event.buttons() & QtCore.Qt.LeftButton:
                    # Update the end position of the bounding box
                    self._bounding_box_end = self._graphics_view.mapToScene(event.pos()).toPoint()
                    # Redraw the image
                    self.update_image()

    def mouse_release(self, event):
        if event.button() != Qt.LeftButton:
            return

        if self._mode == 'keypoints':
            if self._dragged_keypoint_index is None:
                return
            x, y = int(self._graphics_view.mapToScene(event.pos()).x()), int(self._graphics_view.mapToScene(event.pos()).y())
            # Check if the keypoint is outside the image
            if x < 0 or x >= self._m_pixmap.width() or y < 0 or y >= self._m_pixmap.height():
                # Remove the keypoint from the QListWidget
                item_to_delete = self._coordinates_list.takeItem(self._dragged_keypoint_index)
                del item_to_delete
                self.update_image()
            self._dragged_keypoint_index = None

        elif self._mode == 'bounding_boxes':
            if self._dragged_box_index is not None:  # Dragging behaviour
                item = self._coordinates_list.item(self._dragged_box_index)
                class_idx, normalized_top_left_x, normalized_top_left_y, normalized_bottom_right_x, normalized_bottom_right_y = item.text().split(',')
                top_left_x, top_left_y = int(float(normalized_top_left_x) * self._m_pixmap.width()), int(
                    float(normalized_top_left_y) * self._m_pixmap.height())
                bottom_right_x, bottom_right_y = int(float(normalized_bottom_right_x) * self._m_pixmap.width()), int(
                    float(normalized_bottom_right_y) * self._m_pixmap.height())
                if top_left_x >= bottom_right_x or top_left_y >= bottom_right_y or \
                        top_left_x < 0 or top_left_y < 0 or bottom_right_x >= self._m_pixmap.width() or bottom_right_y >= self._m_pixmap.height():
                    # Remove the bounding box from the QListWidget
                    item_to_delete = self._coordinates_list.takeItem(self._dragged_box_index)
                    del item_to_delete
                    self.update_image()
                self._dragged_box_index = None
                self._dragged_box_corner = None
            elif not self._bounding_box_start or not self._bounding_box_end:  # There is no dragging or drawing
                return

            # The user ends drawing a new bounding box
            if self._dragging_corner == True:
                self._bounding_box_start = None
                self._bounding_box_end = None
                self._dragging_corner = False
                self.update_image()
                return

            # Get the class_name input from the user
            class_name, ok = QtWidgets.QInputDialog.getItem(self, "Select class dialog",
                                                            "List of classes", self._class_names, 0, False)
            if not ok:
                self._bounding_box_start = None
                self._bounding_box_end = None
                self.update_image()
                self._is_saved = True
                return

            class_idx = self._class_names.index(class_name)

            # Calculate the normalized bounding box coordinates
            top_left = self._bounding_box_start
            bottom_right = self._bounding_box_end
            normalized_top_left = QtCore.QPointF(top_left.x() / self._m_pixmap.width(),
                                                 top_left.y() / self._m_pixmap.height())
            normalized_bottom_right = QtCore.QPointF(bottom_right.x() / self._m_pixmap.width(),
                                                     bottom_right.y() / self._m_pixmap.height())

            # Add the bounding box information to the QListWidget
            item = QtWidgets.QListWidgetItem(
                f"{class_idx}, "
                f"{normalized_top_left.x():.4f}, "
                f"{normalized_top_left.y():.4f}, "
                f"{normalized_bottom_right.x():.4f}, "
                f"{normalized_bottom_right.y():.4f}"
            )
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
            self._coordinates_list.addItem(item)
            self._bounding_box_start = None
            self._bounding_box_end = None
            self.update_image()

    def update_image(self):
        # Clear the old image item from the scene
        self._scene.removeItem(self._image_item)
        self._scene.clear()

        # Create a new pixmap with the updated key points or bounding boxes
        pixmap = self._m_pixmap.copy()
        qp = QtGui.QPainter(pixmap)
        point_size = self._point_size_spinbox.value()

        # Draw
        for i in range(self._coordinates_list.count()):
            item_text = self._coordinates_list.item(i).text().split(',')
            class_idx = int(item_text[0])
            color = self._class_colors[class_idx]
            color = QtGui.QColor(color.strip())

            if len(item_text) == 5:  # Bounding box
                qp.setPen(QtGui.QPen(color, 2, QtCore.Qt.SolidLine))
                normalized_top_left = QtCore.QPointF(float(item_text[1]), float(item_text[2]))
                normalized_bottom_right = QtCore.QPointF(float(item_text[3]), float(item_text[4]))
                top_left = QtCore.QPoint(int(normalized_top_left.x() * pixmap.width()),
                                         int(normalized_top_left.y() * pixmap.height()))
                bottom_right = QtCore.QPoint(int(normalized_bottom_right.x() * pixmap.width()),
                                             int(normalized_bottom_right.y() * pixmap.height()))
                qp.drawRect(QtCore.QRect(top_left, bottom_right).normalized())

            elif len(item_text) == 3:  # Keypoint
                qp.setPen(QtGui.QPen(color, point_size))
                normalized_x, normalized_y = float(item_text[1]), float(item_text[2])
                x, y = int(normalized_x * pixmap.width()), int(normalized_y * pixmap.height())
                qp.drawPoint(QtCore.QPoint(x, y))

        # Draw the bounding box being created
        if self._mode == 'bounding_boxes' and self._bounding_box_start and self._bounding_box_end:
            qp.setPen(QtGui.QPen(QtGui.QColor(QtCore.Qt.green), 1, QtCore.Qt.SolidLine))
            bounding_box_rect = QtCore.QRect(self._bounding_box_start, self._bounding_box_end)
            qp.drawRect(bounding_box_rect.normalized())
        qp.end()

        # Create a new image item with the updated pixmap and add it to the scene
        self._image_item = QtWidgets.QGraphicsPixmapItem(pixmap)
        self._scene.addItem(self._image_item)
        self._scene.update()

        # There are changes waiting
        self._is_saved = False

    def load_image(self):
        image_path = os.path.join(self._current_directory, self._image_filenames[self._current_image_index])
        image = PIL.Image.open(image_path)
        resizer = Resizer(self._target_height, self._target_width)
        image = resizer.resize(image)
        self._img = PIL.ImageQt.ImageQt(image)
        self._m_pixmap = QtGui.QPixmap.fromImage(self._img)
        self._image_item = QtWidgets.QGraphicsPixmapItem(self._m_pixmap)
        self._scene.setSceneRect(0, 0, self._m_pixmap.width(), self._m_pixmap.height())
        self._graphics_view.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        txt_file = os.path.join(self._current_directory,
                                self._image_filenames[self._current_image_index].split(".")[0] + ".txt")
        if os.path.exists(txt_file):
            with open(txt_file, "r") as file:
                for line in file:
                    line_elements = line.strip().split(',')
                    class_idx = int(line_elements[0])
                    if len(line_elements) == 3:  # Keypoint
                        normalized_x, normalized_y = line_elements[1], line_elements[2]
                        item = QtWidgets.QListWidgetItem(f"{class_idx}, {normalized_x}, {normalized_y}")
                    elif len(line_elements) == 5:  # Bounding box
                        normalized_top_left_x, normalized_top_left_y = line_elements[1], line_elements[2]
                        normalized_bottom_right_x, normalized_bottom_right_y = line_elements[3], line_elements[4]
                        item = QtWidgets.QListWidgetItem(
                            f"{class_idx}, "
                            f"{normalized_top_left_x}, "
                            f"{normalized_top_left_y}, "
                            f"{normalized_bottom_right_x}, "
                            f"{normalized_bottom_right_y}"
                        )
                    item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
                    self._coordinates_list.addItem(item)
        self.update_image()
        self.update()
        self._is_saved = True

    def zoom(self, event):
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        # Set anchors
        self._graphics_view.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)

        # Get the current scale factor
        current_scale = self._graphics_view.transform().m11()

        # Calculate the new scale factor based on the mouse wheel delta
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        new_scale = current_scale * zoom_factor

        # Limit the scale factor to a reasonable range between "min_scale" and "max_scale"
        new_scale = max(min(new_scale, 10.0), 0.1)

        # Set the new scale factor
        self._graphics_view.setTransform(QtGui.QTransform.fromScale(new_scale, new_scale))

    def wheelEvent(self, event):
        self.zoom(event)

    def _ask_for_saving(self):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Question)
        msg.setText("Do you want to save the changes?")
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        retval = msg.exec_()
        return retval


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = ImageAnnotator()
    sys.exit(app.exec_())
